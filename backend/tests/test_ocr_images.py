"""上传图片解码：先按头部尺寸拒绝，再解像素；各业务把超限 / 解不开映射成 400。"""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.articles.errors import ArticleError
from app.services.articles.store import sniff_article_image_ext
from app.services.articles.texteller import _open_rgb_image
from app.services.avatar_store import encode_avatar_jpeg
from app.services.ocr.images import ImageDecodeError, ImageTooLarge, open_bounded_image
from app.services.tarkov import key_ocr, raid_prep_ocr


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _png_header_only(width: int, height: int) -> bytes:
    """IHDR 声明大尺寸，IDAT 只有几字节：真去解像素会报截断。"""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(b"\x00" * 16))
        + _chunk(b"IEND", b"")
    )


def _png(width: int = 120, height: int = 90) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 60, 90)).save(buf, format="PNG")
    return buf.getvalue()


def test_open_bounded_image_decodes_normal_png() -> None:
    image = open_bounded_image(_png(120, 90))
    assert image.size == (120, 90)
    assert image.getpixel((0, 0)) == (30, 60, 90)


def test_rejects_declared_size_before_decoding_pixels() -> None:
    with pytest.raises(ImageTooLarge):
        open_bounded_image(_png_header_only(6000, 6000))
    with pytest.raises(ImageDecodeError) as truncated:
        open_bounded_image(_png_header_only(200, 200))
    assert not isinstance(truncated.value, ImageTooLarge)


def test_pillow_bomb_error_maps_to_too_large() -> None:
    with pytest.raises(ImageTooLarge):
        open_bounded_image(_png_header_only(20000, 20000))


def test_max_pixels_is_per_call() -> None:
    assert open_bounded_image(_png(100, 50), max_pixels=5000).size == (100, 50)
    with pytest.raises(ImageTooLarge):
        open_bounded_image(_png(100, 51), max_pixels=5000)


def test_garbage_and_unlisted_formats_are_decode_errors() -> None:
    with pytest.raises(ImageDecodeError):
        open_bounded_image(b"not-an-image")
    eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n"
    with pytest.raises(ImageDecodeError):
        open_bounded_image(eps)
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="TIFF")
    with pytest.raises(ImageDecodeError):
        open_bounded_image(buf.getvalue())


def test_callers_map_bomb_to_their_400() -> None:
    bomb = _png_header_only(6000, 6000)
    with pytest.raises(HTTPException) as avatar:
        encode_avatar_jpeg(bomb)
    assert (avatar.value.status_code, avatar.value.detail) == (400, "图片尺寸过大")
    with pytest.raises(HTTPException) as article:
        sniff_article_image_ext(bomb)
    assert (article.value.status_code, article.value.detail) == (400, "图片尺寸过大")
    with pytest.raises(ArticleError) as formula:
        _open_rgb_image(bomb)
    assert (formula.value.status_code, formula.value.message) == (400, "图片尺寸过大")
    with pytest.raises(key_ocr.TarkovKeyOcrError) as keys:
        key_ocr.load_image(bomb)
    assert keys.value.status_code == 400
    assert keys.value.message.startswith("图片尺寸过大")
    with pytest.raises(raid_prep_ocr.TarkovRaidPrepOcrError) as prep:
        raid_prep_ocr.load_image(bomb)
    assert prep.value.status_code == 400
    assert prep.value.message.startswith("图片尺寸过大")


def test_callers_map_truncated_image_to_unreadable() -> None:
    broken = _png_header_only(200, 200)
    with pytest.raises(HTTPException) as avatar:
        encode_avatar_jpeg(broken)
    assert avatar.value.detail == "无法识别的图片文件"
    with pytest.raises(ArticleError) as formula:
        _open_rgb_image(broken)
    assert formula.value.message == "无法识别该图片"
    with pytest.raises(key_ocr.TarkovKeyOcrError) as keys:
        key_ocr.load_image(broken)
    assert keys.value.message == "无法读取截图"
