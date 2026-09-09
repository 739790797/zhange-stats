"""酒馆文章配图与附件落盘。类型/魔数/大小在本域；写盘与流水号走 user_files。"""

from __future__ import annotations

import io
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.user_files.store import StoredUserFile, UserFileError, public_file_url, store_bytes

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 20_000_000

ALLOWED_ATTACHMENT_EXTS = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".rtf",
    ".json",
    ".lml",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".tgz",
}
_ZIP_EXTS = {".zip", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}
_OLE_EXTS = {".doc", ".xls", ".ppt"}
_TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".lml"}
_HTMLISH = (b"<html", b"<!doctype", b"<script", b"<svg")

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
    return public_file_url(f"articles/{rel.lstrip('/')}")


def sniff_article_image_ext(raw: bytes) -> str:
    """用文件内容判断扩展名；粘贴/拖拽时常没有可靠 Content-Type。"""
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="无法识别的图片文件") from exc
    except Image.DecompressionBombError as exc:
        raise HTTPException(status_code=400, detail="图片尺寸过大") from exc
    fmt = (img.format or "").upper()
    ext = _EXT.get(fmt)
    if ext is None:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF 图片")
    return ext


def write_article_image(
    raw: bytes,
    *,
    db: Session,
    owner_user_id: int | None,
    filename: str = "",
) -> StoredUserFile:
    ext = sniff_article_image_ext(raw)
    return _write_asset(
        db,
        raw,
        ext,
        owner_user_id=owner_user_id,
        filename=filename,
        content_type=_image_content_type(ext),
    )


def attachment_ext_from_name(filename: str) -> str:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name.endswith(".tar.gz"):
        return ".tgz"
    return Path(name).suffix.lower()


def looks_like_article_image(raw: bytes) -> bool:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if raw.startswith(b"\xff\xd8\xff"):
        return True
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return True
    return len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"


def _looks_like_htmlish(raw: bytes) -> bool:
    head = raw.lstrip()[:256].lower()
    return head.startswith(_HTMLISH)


def _looks_like_text(raw: bytes) -> bool:
    sample = raw[:8192]
    if b"\x00" in sample or _looks_like_htmlish(sample):
        return False
    return True


def attachment_magic_matches(raw: bytes, ext: str) -> bool:
    if raw.startswith(b"MZ"):
        return False
    if ext == ".pdf":
        return raw.startswith(b"%PDF")
    if ext in _ZIP_EXTS:
        return raw.startswith(b"PK")
    if ext == ".7z":
        return raw.startswith(b"7z\xbc\xaf'\x1c")
    if ext == ".rar":
        return raw.startswith(b"Rar!")
    if ext in {".gz", ".tgz"}:
        return raw.startswith(b"\x1f\x8b")
    if ext == ".tar":
        return raw[257:262] == b"ustar"
    if ext in _OLE_EXTS:
        return raw.startswith(b"\xd0\xcf\x11\xe0")
    if ext == ".rtf":
        return raw.lstrip().startswith(b"{\\rtf")
    if ext == ".json":
        head = raw.lstrip()[:1]
        return head in {b"{", b"["} and _looks_like_text(raw)
    if ext in _TEXT_EXTS:
        return _looks_like_text(raw)
    return False


def sniff_article_attachment_ext(raw: bytes, filename: str) -> str:
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="附件不能超过 10MB")
    ext = attachment_ext_from_name(filename)
    if ext not in ALLOWED_ATTACHMENT_EXTS:
        raise HTTPException(status_code=400, detail="不支持的附件类型")
    if not attachment_magic_matches(raw, ext):
        raise HTTPException(status_code=400, detail="附件内容与扩展名不符")
    return ext


def write_article_attachment(
    raw: bytes,
    filename: str,
    *,
    db: Session,
    owner_user_id: int | None,
) -> StoredUserFile:
    ext = sniff_article_attachment_ext(raw, filename)
    return _write_asset(
        db,
        raw,
        ext,
        owner_user_id=owner_user_id,
        filename=filename,
        content_type=_attachment_content_type(ext),
    )


def _image_content_type(ext: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")


def _attachment_content_type(ext: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".zip": "application/zip",
    }.get(ext, "application/octet-stream")


def _write_asset(
    db: Session,
    raw: bytes,
    ext: str,
    *,
    owner_user_id: int | None,
    filename: str,
    content_type: str,
) -> StoredUserFile:
    try:
        return store_bytes(
            db,
            namespace="articles",
            raw=raw,
            ext=ext,
            original_name=filename,
            content_type=content_type,
            owner_user_id=owner_user_id,
        )
    except UserFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def is_rejected_image_content_type(content_type: str) -> bool:
    declared = (content_type or "").lower()
    if not declared or declared == "application/octet-stream":
        return False
    return declared not in ALLOWED_CONTENT_TYPES


async def save_article_image(
    file: UploadFile,
    *,
    db: Session,
    owner_user_id: int | None,
) -> StoredUserFile:
    if is_rejected_image_content_type(file.content_type or ""):
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / WebP / GIF 图片")
    return write_article_image(
        await file.read(),
        db=db,
        owner_user_id=owner_user_id,
        filename=file.filename or "",
    )


def save_article_bytes(
    raw: bytes,
    filename: str = "",
    *,
    db: Session,
    owner_user_id: int | None,
) -> StoredUserFile:
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    name = filename or ""
    if name.lower().endswith(".svg") or _looks_like_htmlish(raw):
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    if looks_like_article_image(raw):
        return write_article_image(
            raw, db=db, owner_user_id=owner_user_id, filename=name
        )
    return write_article_attachment(
        raw, name, db=db, owner_user_id=owner_user_id
    )


async def save_article_asset(
    file: UploadFile,
    *,
    db: Session,
    owner_user_id: int | None,
) -> StoredUserFile:
    return save_article_bytes(
        await file.read(),
        file.filename or "",
        db=db,
        owner_user_id=owner_user_id,
    )
