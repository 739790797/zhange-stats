"""Minecraft 服内文件：经 Pelican Client API 代操。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.services import pelican_client as pelican
from app.services.integrations_config import get_pelican_credentials

MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_EDIT_BYTES = 2 * 1024 * 1024
ARCHIVE_EXTENSIONS = ("zip", "tar.gz", "tgz", "tar.xz", "txz", "tar.bz2", "tbz2")


class MinecraftFilesError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def require_pelican(db: Session) -> tuple[str, str, str]:
    base, token, uuid = get_pelican_credentials(db)
    if not pelican.pelican_configured(base, token, uuid):
        raise MinecraftFilesError("未配置 Pelican", status_code=400)
    return base, token, uuid


def normalize_mode(mode: str) -> str:
    text = (mode or "").strip()
    if len(text) == 4 and text.isdigit() and text.startswith("0"):
        return text
    if len(text) == 3 and text.isdigit():
        return text
    raise MinecraftFilesError("权限须为 644 或 0755 这类八进制")


def _pull_url(url: str) -> str:
    text = (url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MinecraftFilesError("拉取地址须为 http(s) URL")
    return text


def _sorted_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (bool(row.get("is_file")), str(row.get("name") or "").lower()))


def list_directory(db: Session, directory: str) -> dict[str, Any]:
    base, token, uuid = require_pelican(db)
    path = pelican.normalize_remote_directory(directory)
    entries = _sorted_entries(pelican.list_files(base, token, uuid, path))
    return {"directory": path, "entries": entries}


def read_file(db: Session, path: str) -> dict[str, Any]:
    base, token, uuid = require_pelican(db)
    full = pelican.normalize_remote_file_path(path)
    content = pelican.get_file_contents(base, token, uuid, full)
    return {"path": full, "content": content}


def write_file(db: Session, path: str, content: str) -> None:
    base, token, uuid = require_pelican(db)
    full = pelican.normalize_remote_file_path(path)
    raw = content.encode("utf-8")
    if len(raw) > MAX_EDIT_BYTES:
        raise MinecraftFilesError(f"文件内容超过 {MAX_EDIT_BYTES // (1024 * 1024)}MB，请改为上传")
    pelican.write_file(base, token, uuid, full, raw)


def download_url(db: Session, path: str) -> dict[str, str]:
    base, token, uuid = require_pelican(db)
    full = pelican.normalize_remote_file_path(path)
    return {"path": full, "url": pelican.get_download_url(base, token, uuid, full)}


def upload_file(db: Session, directory: str, filename: str, content: bytes) -> dict[str, str]:
    if not content:
        raise MinecraftFilesError("文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise MinecraftFilesError("上传不能超过 64MB")
    base, token, uuid = require_pelican(db)
    full = pelican.join_remote_path(directory, pelican.sanitize_filename(filename, allow_path=True))
    pelican.write_file(base, token, uuid, full, content)
    return {"path": full, "name": pelican.split_remote_path(full)[1]}


def create_folder(db: Session, directory: str, name: str) -> None:
    base, token, uuid = require_pelican(db)
    pelican.create_folder(
        base,
        token,
        uuid,
        root=directory,
        name=name,
        ignore_exists=False,
    )


def create_file(db: Session, directory: str, name: str, content: str = "") -> dict[str, str]:
    base, token, uuid = require_pelican(db)
    full = pelican.join_remote_path(directory, name)
    pelican.write_file(base, token, uuid, full, content)
    return {"path": full}


def rename_entry(db: Session, directory: str, src: str, dest: str) -> None:
    base, token, uuid = require_pelican(db)
    pelican.rename_files(base, token, uuid, root=directory, files=[(src, dest)])


def copy_entry(db: Session, path: str) -> None:
    base, token, uuid = require_pelican(db)
    pelican.copy_file(base, token, uuid, path)


def delete_entries(db: Session, directory: str, names: list[str]) -> None:
    if not names:
        raise MinecraftFilesError("请选择要删除的文件")
    base, token, uuid = require_pelican(db)
    pelican.delete_files(base, token, uuid, root=directory, files=names)


def compress_entries(
    db: Session,
    directory: str,
    names: list[str],
    archive_name: str | None = None,
    extension: str | None = None,
) -> dict[str, Any] | None:
    if not names:
        raise MinecraftFilesError("请选择要压缩的文件")
    ext = (extension or "zip").strip().lower()
    if ext not in ARCHIVE_EXTENSIONS:
        raise MinecraftFilesError("不支持的压缩格式")
    base, token, uuid = require_pelican(db)
    return pelican.compress_files(
        base,
        token,
        uuid,
        root=directory,
        files=names,
        name=archive_name,
        extension=ext,
    )


def decompress_entry(db: Session, directory: str, name: str) -> None:
    base, token, uuid = require_pelican(db)
    pelican.decompress_file(base, token, uuid, root=directory, name=name)


def chmod_entries(db: Session, directory: str, names: list[str], mode: str) -> None:
    if not names:
        raise MinecraftFilesError("请选择要改权限的文件")
    bits = normalize_mode(mode)
    base, token, uuid = require_pelican(db)
    pelican.chmod_files(
        base,
        token,
        uuid,
        root=directory,
        files=[{"file": n, "mode": bits} for n in names],
    )


def pull_remote(db: Session, directory: str, url: str, filename: str) -> None:
    remote = _pull_url(url)
    name = (filename or "").strip()
    if not name:
        parsed = urlparse(remote)
        name = parsed.path.rsplit("/", 1)[-1] or "download"
    base, token, uuid = require_pelican(db)
    pelican.pull_file(
        base,
        token,
        uuid,
        url=remote,
        directory=directory,
        filename=name,
    )
