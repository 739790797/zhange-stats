"""酒馆配图按文件内容识别，不依赖声明的 Content-Type。"""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.articles.store import (
    attachment_ext_from_name,
    attachment_magic_matches,
    is_rejected_image_content_type,
    looks_like_article_image,
    sniff_article_attachment_ext,
    sniff_article_image_ext,
)


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def test_sniff_article_image_ext_png() -> None:
    assert sniff_article_image_ext(_png()) == ".png"


def test_sniff_article_image_ext_rejects_empty_and_garbage() -> None:
    with pytest.raises(HTTPException) as empty:
        sniff_article_image_ext(b"")
    assert empty.value.status_code == 400
    with pytest.raises(HTTPException) as garbage:
        sniff_article_image_ext(b"not-an-image")
    assert garbage.value.status_code == 400


def test_attachment_ext_and_magic() -> None:
    assert attachment_ext_from_name(r"C:\\tmp\\note.TAR.GZ") == ".tgz"
    assert attachment_ext_from_name("pack.lml") == ".lml"
    assert attachment_magic_matches(b"%PDF-1.7\n", ".pdf") is True
    assert attachment_magic_matches(b"PK\x03\x04rest", ".docx") is True
    assert attachment_magic_matches(b"hello\nworld", ".txt") is True
    assert attachment_magic_matches(b'{"a":1}', ".json") is True
    assert attachment_magic_matches(b"MZ\x90\x00", ".pdf") is False
    assert attachment_magic_matches(b"<html>x</html>", ".txt") is False
    assert looks_like_article_image(_png()) is True
    assert looks_like_article_image(b"%PDF-1.7\n") is False


def test_sniff_article_attachment_ext() -> None:
    assert sniff_article_attachment_ext(b"%PDF-1.4\n%", "a.pdf") == ".pdf"
    with pytest.raises(HTTPException) as exe:
        sniff_article_attachment_ext(b"MZ\x90\x00", "a.exe")
    assert exe.value.status_code == 400
    with pytest.raises(HTTPException) as spoof:
        sniff_article_attachment_ext(b"MZ\x90\x00", "a.pdf")
    assert spoof.value.status_code == 400


def test_is_rejected_image_content_type() -> None:
    assert is_rejected_image_content_type("") is False
    assert is_rejected_image_content_type("application/octet-stream") is False
    assert is_rejected_image_content_type("image/png") is False
    assert is_rejected_image_content_type("image/svg+xml") is True
    assert is_rejected_image_content_type("text/plain") is True
