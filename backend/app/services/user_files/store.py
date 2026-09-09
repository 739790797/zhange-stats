"""用户附件落盘与登记。业务域负责类型/大小/魔数；本模块只管相对路径、写盘、流水号。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import now_naive
from app.models.user_files import UserFile

NS_ARTICLES = "articles"
NS_AVATARS = "avatars"
NAMESPACES = frozenset({NS_ARTICLES, NS_AVATARS})
APPEND_NAMESPACES = frozenset({NS_ARTICLES})
VISIBILITY_PUBLIC = "public"
STATUS_STORED = "stored"
STATUS_DELETED = "deleted"
SERIAL_PREFIX = "UF"
SERIAL_WIDTH = 8
_MAX_REL_LEN = 512
_MAX_NAME_LEN = 255


class UserFileError(ValueError):
    """路径 / 命名空间 / 登记失败。"""


@dataclass(frozen=True)
class StoredUserFile:
    id: int
    serial: str
    rel_path: str
    url: str


def upload_root() -> Path:
    path = get_settings().upload_dir_path
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_serial(file_id: int) -> str:
    if file_id < 1:
        raise UserFileError("附件编号无效")
    return f"{SERIAL_PREFIX}{file_id:0{SERIAL_WIDTH}d}"


def normalize_rel_path(rel: str) -> str:
    raw = (rel or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or ":" in raw.split("/", 1)[0]:
        raise UserFileError("附件路径无效")
    parts: list[str] = []
    for piece in raw.split("/"):
        if piece in {"", "."}:
            continue
        if piece == ".." or "\x00" in piece:
            raise UserFileError("附件路径无效")
        parts.append(piece)
    if not parts:
        raise UserFileError("附件路径无效")
    out = "/".join(parts)
    if len(out) > _MAX_REL_LEN:
        raise UserFileError("附件路径过长")
    return out


def public_file_url(rel_path: str) -> str:
    return f"/uploads/{normalize_rel_path(rel_path)}"


def _sanitize_original_name(name: str | None) -> str | None:
    if not name:
        return None
    base = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not base or base in {".", ".."} or "\x00" in base:
        return None
    return base[:_MAX_NAME_LEN]


def _normalize_ext(ext: str) -> str:
    value = (ext or "").strip().lower()
    if not value.startswith("."):
        value = f".{value}" if value else ""
    if not value or "/" in value or "\\" in value or "\x00" in value or len(value) > 16:
        raise UserFileError("附件扩展名无效")
    return value


def _assert_namespace(namespace: str) -> str:
    ns = (namespace or "").strip()
    if ns not in NAMESPACES:
        raise UserFileError("不支持的附件命名空间")
    return ns


def _assert_append_namespace(namespace: str) -> str:
    ns = _assert_namespace(namespace)
    if ns not in APPEND_NAMESPACES:
        raise UserFileError("该命名空间不支持追加写入")
    return ns


def _assert_visibility(visibility: str) -> str:
    value = (visibility or "").strip()
    if value != VISIBILITY_PUBLIC:
        raise UserFileError("不支持的附件可见性")
    return value


def _rel_under_namespace(rel_path: str, namespace: str) -> str:
    rel = normalize_rel_path(rel_path)
    prefix = f"{namespace}/"
    if not rel.startswith(prefix) or rel == namespace:
        raise UserFileError("附件路径不在命名空间内")
    return rel


def _resolve_in_upload(rel_path: str, *, root: Path | None = None) -> Path:
    base = (root or upload_root()).resolve()
    rel = normalize_rel_path(rel_path)
    dest = (base / rel).resolve()
    try:
        dest.relative_to(base)
    except ValueError as exc:
        raise UserFileError("附件路径越界") from exc
    return dest


def _assign_serial(row: UserFile) -> str:
    row.serial = format_serial(int(row.id))
    return row.serial


def get_by_serial(db: Session, serial: str) -> UserFile | None:
    key = (serial or "").strip().upper()
    if not key:
        return None
    return db.query(UserFile).filter(UserFile.serial == key).first()


def get_by_rel_path(db: Session, rel_path: str) -> UserFile | None:
    try:
        rel = normalize_rel_path(rel_path)
    except UserFileError:
        return None
    return db.query(UserFile).filter(UserFile.rel_path == rel).first()


def _insert_row(
    db: Session,
    *,
    namespace: str,
    rel_path: str,
    original_name: str | None,
    content_type: str | None,
    size_bytes: int,
    owner_user_id: int | None,
    visibility: str,
    created_at: datetime,
    commit: bool,
) -> UserFile:
    row = UserFile(
        serial=uuid.uuid4().hex,
        namespace=namespace,
        rel_path=rel_path,
        original_name=_sanitize_original_name(original_name),
        content_type=(content_type or "").strip()[:128] or None,
        size_bytes=int(size_bytes),
        owner_user_id=owner_user_id,
        visibility=visibility,
        status=STATUS_STORED,
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    _assign_serial(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def store_bytes(
    db: Session,
    *,
    namespace: str,
    raw: bytes,
    ext: str,
    original_name: str | None = None,
    content_type: str | None = None,
    owner_user_id: int | None = None,
    visibility: str = VISIBILITY_PUBLIC,
    root: Path | None = None,
) -> StoredUserFile:
    ns = _assert_append_namespace(namespace)
    vis = _assert_visibility(visibility)
    suffix = _normalize_ext(ext)
    if not raw:
        raise UserFileError("文件为空")
    stamp = now_naive()
    rel = f"{ns}/{stamp.year:04d}/{stamp.month:02d}/{uuid.uuid4().hex}{suffix}"
    dest = _resolve_in_upload(rel, root=root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    try:
        row = _insert_row(
            db,
            namespace=ns,
            rel_path=rel,
            original_name=original_name,
            content_type=content_type,
            size_bytes=len(raw),
            owner_user_id=owner_user_id,
            visibility=vis,
            created_at=stamp,
            commit=True,
        )
    except Exception:
        dest.unlink(missing_ok=True)
        db.rollback()
        raise
    return StoredUserFile(
        id=int(row.id),
        serial=row.serial,
        rel_path=row.rel_path,
        url=public_file_url(row.rel_path),
    )


def register_existing(
    db: Session,
    *,
    namespace: str,
    rel_path: str,
    original_name: str | None = None,
    content_type: str | None = None,
    size_bytes: int = 0,
    owner_user_id: int | None = None,
    visibility: str = VISIBILITY_PUBLIC,
    created_at: datetime | None = None,
    commit: bool = False,
) -> UserFile:
    """为已在盘上的文件补一行；rel_path 已存在则返回原行。"""
    ns = _assert_namespace(namespace)
    vis = _assert_visibility(visibility)
    rel = _rel_under_namespace(rel_path, ns)
    found = get_by_rel_path(db, rel)
    if found is not None:
        return found
    return _insert_row(
        db,
        namespace=ns,
        rel_path=rel,
        original_name=original_name,
        content_type=content_type,
        size_bytes=max(0, int(size_bytes)),
        owner_user_id=owner_user_id,
        visibility=vis,
        created_at=created_at or now_naive(),
        commit=commit,
    )


def _apply_stored_meta(
    row: UserFile,
    *,
    original_name: str | None,
    content_type: str | None,
    size_bytes: int,
    owner_user_id: int | None,
    visibility: str,
) -> None:
    name = _sanitize_original_name(original_name)
    if name:
        row.original_name = name
    ctype = (content_type or "").strip()[:128] or None
    if ctype:
        row.content_type = ctype
    row.size_bytes = int(size_bytes)
    if owner_user_id is not None:
        row.owner_user_id = owner_user_id
    row.visibility = visibility
    row.status = STATUS_STORED


def replace_bytes(
    db: Session,
    *,
    namespace: str,
    rel_path: str,
    raw: bytes,
    original_name: str | None = None,
    content_type: str | None = None,
    owner_user_id: int | None = None,
    visibility: str = VISIBILITY_PUBLIC,
    root: Path | None = None,
    commit: bool = False,
) -> StoredUserFile:
    """按固定相对路径覆盖写盘并 upsert 登记（头像等一人一文件）。"""
    ns = _assert_namespace(namespace)
    vis = _assert_visibility(visibility)
    if not raw:
        raise UserFileError("文件为空")
    rel = _rel_under_namespace(rel_path, ns)
    dest = _resolve_in_upload(rel, root=root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.tmp")
    try:
        tmp.write_bytes(raw)
        tmp.replace(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    found = get_by_rel_path(db, rel)
    try:
        if found is not None:
            _apply_stored_meta(
                found,
                original_name=original_name,
                content_type=content_type,
                size_bytes=len(raw),
                owner_user_id=owner_user_id,
                visibility=vis,
            )
            if commit:
                db.commit()
                db.refresh(found)
            row = found
        else:
            row = _insert_row(
                db,
                namespace=ns,
                rel_path=rel,
                original_name=original_name,
                content_type=content_type,
                size_bytes=len(raw),
                owner_user_id=owner_user_id,
                visibility=vis,
                created_at=now_naive(),
                commit=commit,
            )
    except Exception:
        if found is None:
            dest.unlink(missing_ok=True)
        db.rollback()
        raise
    return StoredUserFile(
        id=int(row.id),
        serial=row.serial,
        rel_path=row.rel_path,
        url=public_file_url(row.rel_path),
    )


def mark_deleted(
    db: Session,
    rel_path: str,
    *,
    unlink: bool = True,
    commit: bool = False,
    root: Path | None = None,
) -> UserFile | None:
    """标 deleted；默认同时删盘。无登记行时仍可清盘。"""
    rel = normalize_rel_path(rel_path)
    dest = _resolve_in_upload(rel, root=root)
    row = get_by_rel_path(db, rel)
    if row is not None:
        row.status = STATUS_DELETED
    if unlink:
        dest.unlink(missing_ok=True)
    if commit:
        db.commit()
        if row is not None:
            db.refresh(row)
    return row
