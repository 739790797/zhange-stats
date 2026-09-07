"""酒馆文章配图落盘。"""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.timeutil import now_naive

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000

_EXT = {
    "JPEG": ".jpg",
    "JPG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}


def articles_dir() -> Path:
    path = get_settings().upload_dir_path / "articles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_asset_url(rel: str) -> str:
    return f"/uploads/articles/{rel.lstrip('/')}"


async def save_article_image(file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF 图片")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="无法识别的图片文件") from exc

    fmt = (img.format or "JPEG").upper()
    ext = _EXT.get(fmt, ".jpg")
    stamp: datetime = now_naive()
    rel = f"{stamp.year:04d}/{stamp.month:02d}/{uuid.uuid4().hex}{ext}"
    dest = articles_dir() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return public_asset_url(rel)
