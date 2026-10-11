"""上传图片解码：先按文件头里的尺寸拒掉超大图，再解像素（防解压炸弹）。

``Image.open`` 只读文件头；像素在 ``load()`` 才解。各业务把本模块的错误换成自己的文案。
"""

from __future__ import annotations

import io

from PIL import Image

MAX_DECODE_PIXELS = 20_000_000
# 只放截图 / 头像 / 配图会用到的格式；EPS 等会拉起外部解释器或自带炸弹的格式一律不认。
UPLOAD_FORMATS = ("PNG", "JPEG", "WEBP", "GIF", "BMP")


class ImageDecodeError(Exception):
    """解不开、格式不认或尺寸超限。"""


class ImageTooLarge(ImageDecodeError):
    """文件头声明的像素数超过上限，没有解像素。"""


def open_bounded_image(
    raw: bytes,
    *,
    max_pixels: int = MAX_DECODE_PIXELS,
    formats: tuple[str, ...] = UPLOAD_FORMATS,
) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw), formats=formats)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageTooLarge(str(exc)) from exc
    except Exception as exc:
        raise ImageDecodeError(str(exc)) from exc
    width, height = image.size
    if width < 1 or height < 1:
        image.close()
        raise ImageDecodeError("图片尺寸无效")
    if width * height > max_pixels:
        image.close()
        raise ImageTooLarge(f"{width}x{height} 超过 {max_pixels} 像素")
    try:
        image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        image.close()
        raise ImageTooLarge(str(exc)) from exc
    except Exception as exc:
        image.close()
        raise ImageDecodeError(str(exc)) from exc
    return image
