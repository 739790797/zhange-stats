"""扫盘补登记：存量 articles/、avatars/ 按相对路径插入，不改公开 URL。

应用启动（成员同步之后）会跑 ``ensure_user_files_registered``。也可在 backend/ 下手动：

    python -m app.services.user_files.backfill
    python -m app.services.user_files.backfill --namespace avatars
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.timeutil import BEIJING
from app.models.member import Member
from app.models.user_files import UserFile
from app.services.user_files.store import (
    NAMESPACES,
    NS_AVATARS,
    UserFileError,
    normalize_rel_path,
    register_existing,
    upload_root,
)

logger = logging.getLogger("zhange.user_files")

_EXT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".zip": "application/zip",
    ".7z": "application/x-7z-compressed",
    ".rar": "application/vnd.rar",
    ".gz": "application/gzip",
    ".tgz": "application/gzip",
    ".tar": "application/x-tar",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def guess_content_type(name: str) -> str | None:
    lower = name.lower()
    if lower.endswith(".tar.gz"):
        return _EXT_TYPES[".tgz"]
    ext = Path(lower).suffix
    return _EXT_TYPES.get(ext)


def _mtime_naive(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, BEIJING).replace(tzinfo=None)


def owner_user_id_for_rel(db: Session, namespace: str, rel_path: str) -> int | None:
    """avatars/{member_id}.jpg 尽量反查 members.user_id；对不上则无主。"""
    if namespace != NS_AVATARS:
        return None
    name = rel_path.rsplit("/", 1)[-1]
    if not name.lower().endswith(".jpg"):
        return None
    stem = name[:-4]
    if not stem.isdigit():
        return None
    member = db.query(Member).filter(Member.id == int(stem)).first()
    if member is None or member.user_id is None:
        return None
    return int(member.user_id)


def iter_namespace_files(namespace: str, *, root: Path | None = None) -> list[Path]:
    base = (root or upload_root()).resolve()
    ns_root = (base / namespace).resolve()
    try:
        ns_root.relative_to(base)
    except ValueError as exc:
        raise UserFileError("附件路径越界") from exc
    if not ns_root.is_dir():
        return []
    out: list[Path] = []
    for path in ns_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.endswith(".tmp"):
            continue
        try:
            path.resolve().relative_to(ns_root)
        except ValueError:
            continue
        out.append(path)
    out.sort(key=lambda item: item.as_posix())
    return out


def backfill_namespace(
    db: Session,
    namespace: str = "articles",
    *,
    root: Path | None = None,
) -> dict[str, int]:
    if namespace not in NAMESPACES:
        raise UserFileError("不支持的附件命名空间")
    base = (root or upload_root()).resolve()
    existing = {
        rel
        for (rel,) in db.query(UserFile.rel_path).filter(UserFile.namespace == namespace)
    }
    added = 0
    skipped = 0
    for path in iter_namespace_files(namespace, root=base):
        try:
            rel = normalize_rel_path(path.relative_to(base).as_posix())
        except UserFileError as exc:
            logger.warning("user_files backfill skip path=%s err=%s", path, exc)
            continue
        if rel in existing:
            skipped += 1
            continue
        try:
            register_existing(
                db,
                namespace=namespace,
                rel_path=rel,
                original_name=path.name,
                content_type=guess_content_type(path.name),
                size_bytes=path.stat().st_size,
                owner_user_id=owner_user_id_for_rel(db, namespace, rel),
                created_at=_mtime_naive(path),
                commit=False,
            )
        except (UserFileError, OSError) as exc:
            logger.warning("user_files backfill skip rel=%s err=%s", rel, exc)
            continue
        existing.add(rel)
        added += 1
    owners_filled = 0
    if namespace == NS_AVATARS:
        owners_filled = fill_missing_avatar_owners(db, commit=False)
    db.commit()
    logger.info(
        "user_files backfill namespace=%s added=%s skipped=%s owners_filled=%s",
        namespace,
        added,
        skipped,
        owners_filled,
    )
    return {"added": added, "skipped": skipped}


def fill_missing_avatar_owners(db: Session, *, commit: bool = True) -> int:
    """已登记但无主的头像，按 avatars/{member_id}.jpg 补 owner_user_id。"""
    rows = (
        db.query(UserFile)
        .filter(
            UserFile.namespace == NS_AVATARS,
            UserFile.owner_user_id.is_(None),
        )
        .all()
    )
    filled = 0
    for row in rows:
        owner = owner_user_id_for_rel(db, NS_AVATARS, row.rel_path)
        if owner is None:
            continue
        row.owner_user_id = owner
        filled += 1
    if commit:
        db.commit()
    if filled:
        logger.info("user_files filled avatar owners=%s", filled)
    return filled


def backfill_all(db: Session, *, root: Path | None = None) -> dict[str, dict[str, int]]:
    return {
        namespace: backfill_namespace(db, namespace, root=root)
        for namespace in sorted(NAMESPACES)
    }


def ensure_user_files_registered(
    db: Session, *, root: Path | None = None
) -> dict[str, dict[str, int]]:
    """启动钩子：扫盘把存量附件纳入登记，幂等，不改公开 URL。"""
    stats = backfill_all(db, root=root)
    logger.info("user_files ensure registered %s", stats)
    return stats


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="回填 user_files：扫描 UPLOAD_DIR 下已有附件")
    parser.add_argument(
        "--namespace",
        default="",
        help="articles / avatars；省略则扫全部命名空间",
    )
    args = parser.parse_args(argv)
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        ns = (args.namespace or "").strip()
        if ns:
            stats = backfill_namespace(db, namespace=ns)
        else:
            stats = backfill_all(db)
        logger.info("done %s", stats)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
