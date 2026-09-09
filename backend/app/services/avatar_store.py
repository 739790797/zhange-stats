"""本地头像：裁剪为正方形 JPEG，覆盖写 avatars/{member_id}.jpg 并登记 user_files。"""

from __future__ import annotations

import io
import time

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.services.user_files.store import (
    NS_AVATARS,
    UserFileError,
    mark_deleted,
    public_file_url,
    replace_bytes,
)

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


def avatar_rel_path(member_id: int) -> str:
    mid = int(member_id)
    if mid < 1:
        raise UserFileError("头像路径无效")
    return f"{NS_AVATARS}/{mid}.jpg"


def public_avatar_url(member_id: int) -> str:
    # 带版本查询，避免浏览器缓存旧图；流水号不进路径
    return f"{public_file_url(avatar_rel_path(member_id))}?v={int(time.time())}"


def encode_avatar_jpeg(raw: bytes) -> bytes:
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="头像不能超过 5MB")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="无法识别的图片文件") from exc

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

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


def save_avatar_bytes(
    db: Session,
    member_id: int,
    raw: bytes,
    *,
    owner_user_id: int | None,
    original_name: str | None = None,
) -> str:
    jpeg = encode_avatar_jpeg(raw)
    try:
        replace_bytes(
            db,
            namespace=NS_AVATARS,
            rel_path=avatar_rel_path(member_id),
            raw=jpeg,
            original_name=original_name or f"{member_id}.jpg",
            content_type="image/jpeg",
            owner_user_id=owner_user_id,
            commit=False,
        )
    except UserFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return public_avatar_url(member_id)


def delete_avatar_file(member_id: int, *, db: Session, commit: bool = False) -> None:
    try:
        rel = avatar_rel_path(member_id)
    except UserFileError:
        return
    mark_deleted(db, rel, unlink=True, commit=commit)


async def save_avatar_upload(
    member_id: int,
    file: UploadFile,
    *,
    db: Session,
    owner_user_id: int | None,
) -> str:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF 图片")

    raw = await file.read()
    return save_avatar_bytes(
        db,
        member_id,
        raw,
        owner_user_id=owner_user_id,
        original_name=file.filename,
    )
