"""本地头像上传存储（裁剪为正方形 JPEG）。"""

from __future__ import annotations

import io
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB
AVATAR_SIZE = 256
# 限制解压后像素，降低恶意图片 DoS
Image.MAX_IMAGE_PIXELS = 20_000_000


def is_custom_avatar_url(url: str | None) -> bool:
    return bool(url and url.startswith("/uploads/avatars/"))


def avatar_dir() -> Path:
    path = get_settings().upload_dir_path / "avatars"
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_avatar_url(member_id: int) -> str:
    # 带版本查询，避免浏览器缓存旧图
    import time

    return f"/uploads/avatars/{member_id}.jpg?v={int(time.time())}"


def avatar_file_path(member_id: int) -> Path:
    return avatar_dir() / f"{member_id}.jpg"


def delete_avatar_file(member_id: int) -> None:
    path = avatar_file_path(member_id)
    if path.exists():
        path.unlink(missing_ok=True)


async def save_avatar_upload(member_id: int, file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF 图片")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="头像不能超过 5MB")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="无法识别的图片文件") from exc

    # 统一转 RGB，裁剪居中正方形并缩放
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")

    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)

    out = avatar_file_path(member_id)
    img.save(out, format="JPEG", quality=88, optimize=True)
    return public_avatar_url(member_id)
