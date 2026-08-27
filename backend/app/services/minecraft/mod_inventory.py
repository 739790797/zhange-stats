"""Minecraft jar 库存：指纹对账 + 增量拆包认亲。

权威在战鸽库；Pelican 只当网盘。打开页列目录对账，只下载 fingerprint 变过的包。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.core.timeutil import now
from app.services.integrations_config import get_pelican_credentials
from app.services.minecraft import pelican as pelican
from app.services.minecraft.jar_manifest import JarManifestError, parse_jar_bytes
from app.services.minecraft.mod_registry import (
    SPECS,
    ModToolSpec,
    _compact,
    jar_matches_spec,
)

logger = logging.getLogger(__name__)

LOCK_KEY = "minecraft:modtools:identify:lock"
STATUS_KEY = "minecraft:modtools:identify:status"
LOCK_TTL_SEC = 8 * 60
STATUS_TTL_SEC = 8 * 60
MAX_JAR_BYTES = 96 * 1024 * 1024


def empty_store() -> dict[str, Any]:
    return {"jars": [], "scanned_at": ""}


def jar_path(directory: str, filename: str) -> str:
    folder = (directory or "/").rstrip("/") or ""
    name = (filename or "").lstrip("/")
    return f"{folder}/{name}"


def can_persist(db: Any) -> bool:
    return isinstance(db, Session)


def normalize_store(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return empty_store()
    jars = raw.get("jars")
    rows = [dict(row) for row in jars if isinstance(row, dict)] if isinstance(jars, list) else []
    return {"jars": rows, "scanned_at": str(raw.get("scanned_at") or "")}


def load_store(db: Any) -> tuple[dict[str, Any], bool]:
    if not can_persist(db):
        return empty_store(), False
    from app.services.minecraft.profile import get_or_create_profile

    row = get_or_create_profile(db)
    return normalize_store(getattr(row, "mod_inventory_json", None)), True


def save_store(db: Session, store: dict[str, Any]) -> None:
    from app.services.minecraft.profile import get_or_create_profile

    row = get_or_create_profile(db)
    row.mod_inventory_json = {
        "jars": [dict(item) for item in (store.get("jars") or []) if isinstance(item, dict)],
        "scanned_at": str(store.get("scanned_at") or ""),
    }
    db.add(row)
    db.commit()


def _int_size(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def placeholder_from_disk(disk: dict[str, Any], *, path: str, prev: dict[str, Any] | None = None) -> dict[str, Any]:
    filename = str(disk.get("filename") or "")
    directory = str(disk.get("directory") or "/mods")
    kind = str(disk.get("kind") or ("plugin" if directory.rstrip("/") == "/plugins" else "mod"))
    return {
        "path": path,
        "directory": directory,
        "filename": filename,
        "kind": kind,
        "size": _int_size(disk.get("size")),
        "modified_at": str(disk.get("modified_at") or ""),
        "sha512": "",
        "mod_ids": [],
        "mod_names": [],
        "mod_version": "",
        "identified": False,
        "identify_error": "",
        "source": str((prev or {}).get("source") or "scan"),
        "project_id": "",
        "version_id": "",
        "icon_url": "",
        "tool_id": "",
    }


def same_fingerprint(prev: dict[str, Any] | None, disk: dict[str, Any], *, force: bool) -> bool:
    if force or not prev:
        return False
    return _int_size(prev.get("size")) == _int_size(disk.get("size")) and str(
        prev.get("modified_at") or ""
    ) == str(disk.get("modified_at") or "")


def apply_fingerprint(
    stored: dict[str, Any],
    disk_jars: list[dict[str, Any]],
    *,
    force: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """对账目录：指纹相同沿用；库有盘无直接删；变过的进增量队列。"""
    old = {
        str(row.get("path") or ""): row
        for row in (stored.get("jars") or [])
        if isinstance(row, dict) and row.get("path")
    }
    now_jars: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for disk in disk_jars:
        if not isinstance(disk, dict):
            continue
        filename = str(disk.get("filename") or "")
        if not filename:
            continue
        directory = str(disk.get("directory") or "/mods")
        path = jar_path(directory, filename)
        prev = old.get(path)
        if same_fingerprint(prev, disk, force=force) and prev is not None:
            now_jars.append(prev)
            if not prev.get("identified") and not prev.get("identify_error"):
                pending.append(prev)
            continue
        entry = placeholder_from_disk(disk, path=path, prev=prev)
        now_jars.append(entry)
        pending.append(entry)
    return (
        {"jars": now_jars, "scanned_at": now().isoformat(timespec="seconds")},
        pending,
    )


def entry_matches_spec(entry: dict[str, Any], spec: ModToolSpec) -> bool:
    ids = [_compact(str(row)) for row in (entry.get("mod_ids") or [])]
    names = [_compact(str(row)) for row in (entry.get("mod_names") or [])]
    for excl in spec.exclude_names:
        token = _compact(excl)
        if token and (token in ids or token in names):
            return False
    project = str(entry.get("project_id") or "").strip()
    wanted_project = (spec.links.modrinth_id or "").strip()
    if project and wanted_project and project == wanted_project:
        return True
    wanted = {_compact(name) for name in spec.match_names if name}
    for token in ids:
        if token and token in wanted:
            return True
    if entry.get("identified"):
        return False
    return jar_matches_spec(str(entry.get("filename") or ""), spec)


def matched_tool_id(entry: dict[str, Any]) -> str:
    for spec in SPECS:
        if entry_matches_spec(entry, spec):
            return spec.id
    return ""


def stamp_tool_ids(store: dict[str, Any]) -> dict[str, Any]:
    jars = []
    for row in store.get("jars") or []:
        if not isinstance(row, dict):
            continue
        entry = dict(row)
        entry["tool_id"] = matched_tool_id(entry)
        jars.append(entry)
    return {**store, "jars": jars}


def hits_for_spec(jars: list[dict[str, Any]], spec: ModToolSpec) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for entry in jars:
        if not isinstance(entry, dict):
            continue
        if not entry_matches_spec(entry, spec):
            continue
        hits.append(
            {
                "filename": str(entry.get("filename") or ""),
                "directory": str(entry.get("directory") or ""),
                "kind": str(entry.get("kind") or ""),
                "mod_version": str(entry.get("mod_version") or ""),
                "icon_url": str(entry.get("icon_url") or ""),
                "path": str(entry.get("path") or ""),
            }
        )
    return hits


def public_inventory(store: dict[str, Any]) -> dict[str, Any]:
    jars: list[dict[str, Any]] = []
    for row in store.get("jars") or []:
        if not isinstance(row, dict):
            continue
        jars.append(
            {
                "path": str(row.get("path") or ""),
                "directory": str(row.get("directory") or ""),
                "filename": str(row.get("filename") or ""),
                "kind": str(row.get("kind") or ""),
                "size": _int_size(row.get("size")),
                "modified_at": str(row.get("modified_at") or ""),
                "sha512": str(row.get("sha512") or ""),
                "mod_ids": [str(x) for x in (row.get("mod_ids") or []) if str(x)],
                "mod_names": [str(x) for x in (row.get("mod_names") or []) if str(x)],
                "mod_version": str(row.get("mod_version") or ""),
                "identified": bool(row.get("identified")),
                "identify_error": str(row.get("identify_error") or ""),
                "source": str(row.get("source") or "scan"),
                "project_id": str(row.get("project_id") or ""),
                "version_id": str(row.get("version_id") or ""),
                "icon_url": str(row.get("icon_url") or ""),
                "tool_id": str(row.get("tool_id") or ""),
            }
        )
    return {"jars": jars, "scanned_at": str(store.get("scanned_at") or "")}


def _status_payload(
    *,
    running: bool,
    pending: int = 0,
    total: int = 0,
    current: str = "",
    message: str = "",
) -> dict[str, Any]:
    return {
        "running": running,
        "pending": pending,
        "total": total,
        "current": current,
        "message": message,
    }


def write_status(**kwargs: Any) -> None:
    ephemeral_set(STATUS_KEY, json.dumps(_status_payload(**kwargs), ensure_ascii=False), ttl_sec=STATUS_TTL_SEC)


def read_reconcile(pending_count: int) -> dict[str, Any]:
    running = identify_running()
    raw = ephemeral_get(STATUS_KEY)
    status: dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                status = parsed
        except json.JSONDecodeError:
            status = {}
    if running or bool(status.get("running")):
        pending = int(status.get("pending") or pending_count)
        total = int(status.get("total") or pending)
        current = str(status.get("current") or "")
        message = str(status.get("message") or "")
        if not message and pending:
            message = f"磁盘有变化，正在更新 {pending} 个"
        return _status_payload(
            running=True,
            pending=pending,
            total=total,
            current=current,
            message=message,
        )
    return _status_payload(running=False, pending=pending_count, total=pending_count)


def identify_running() -> bool:
    return bool(ephemeral_get(LOCK_KEY))


def maybe_kick_identify(pending: list[dict[str, Any]]) -> None:
    paths = [str(row.get("path") or "") for row in pending if row.get("path")]
    if not paths:
        return
    if ephemeral_get(LOCK_KEY):
        return
    ephemeral_set(LOCK_KEY, "1", ttl_sec=LOCK_TTL_SEC)
    write_status(
        running=True,
        pending=len(paths),
        total=len(paths),
        message=f"磁盘有变化，正在更新 {len(paths)} 个",
    )
    threading.Thread(
        target=_identify_worker,
        args=(paths,),
        name="zhange-mc-mod-identify",
        daemon=True,
    ).start()


def _replace_entry(store: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    path = str(entry.get("path") or "")
    jars = []
    found = False
    for row in store.get("jars") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("path") or "") == path:
            jars.append(entry)
            found = True
        else:
            jars.append(row)
    if not found and path:
        jars.append(entry)
    return {**store, "jars": jars}


def _drop_paths_in_store(store: dict[str, Any], paths: set[str]) -> dict[str, Any]:
    jars = [
        row
        for row in (store.get("jars") or [])
        if isinstance(row, dict) and str(row.get("path") or "") not in paths
    ]
    return {**store, "jars": jars}


def _identify_one(
    db: Session,
    entry: dict[str, Any],
    *,
    icon_cache: dict[str, str],
) -> dict[str, Any]:
    from app.services.minecraft import modrinth as modrinth

    base, token, uuid = get_pelican_credentials(db)
    path = str(entry.get("path") or "")
    try:
        data = pelican.download_file(
            base, token, uuid, path, max_bytes=MAX_JAR_BYTES
        )
    except pelican.PelicanError as exc:
        entry["identify_error"] = exc.message
        entry["identified"] = False
        return entry
    try:
        parsed = parse_jar_bytes(data)
    except JarManifestError as exc:
        entry["identify_error"] = exc.message
        entry["identified"] = False
        return entry
    sha512 = hashlib.sha512(data).hexdigest()
    entry["sha512"] = sha512
    entry["mod_ids"] = list(parsed.get("mod_ids") or [])
    entry["mod_names"] = list(parsed.get("mod_names") or [])
    entry["mod_version"] = str(parsed.get("mod_version") or "")
    entry["identify_error"] = ""
    entry["identified"] = True
    try:
        found = modrinth.versions_from_hashes([sha512])
    except modrinth.ModrinthError:
        logger.exception("minecraft inventory: modrinth hash lookup failed for %s", path)
        found = {}
    version = found.get(sha512) if isinstance(found, dict) else None
    if isinstance(version, dict):
        project_id = str(version.get("project_id") or "")
        pin = modrinth.pin_from_version(version, project_id=project_id)
        if pin:
            entry["project_id"] = str(pin.get("project_id") or project_id)
            entry["version_id"] = str(pin.get("version_id") or "")
            if not entry.get("mod_version"):
                entry["mod_version"] = str(pin.get("version_number") or "")
            if not entry.get("mod_names"):
                title = str(pin.get("project_title") or "")
                if title:
                    entry["mod_names"] = [title]
        elif project_id:
            entry["project_id"] = project_id
            entry["version_id"] = str(version.get("id") or "")
            if not entry.get("mod_version"):
                entry["mod_version"] = str(version.get("version_number") or "")
        if entry.get("project_id"):
            pid = str(entry["project_id"])
            if pid not in icon_cache:
                icon_cache[pid] = modrinth.project_icon_url(pid)
            if icon_cache[pid]:
                entry["icon_url"] = icon_cache[pid]
    entry["tool_id"] = matched_tool_id(entry)
    return entry


def _identify_worker(paths: list[str]) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        store, persist = load_store(db)
        if not persist:
            return
        by_path = {
            str(row.get("path") or ""): row
            for row in (store.get("jars") or [])
            if isinstance(row, dict)
        }
        todo = [by_path[path] for path in paths if path in by_path]
        total = len(todo)
        icon_cache: dict[str, str] = {}
        for index, row in enumerate(todo, start=1):
            ephemeral_set(LOCK_KEY, "1", ttl_sec=LOCK_TTL_SEC)
            current = str(row.get("filename") or row.get("path") or "")
            remaining = total - index + 1
            write_status(
                running=True,
                pending=remaining,
                total=total,
                current=current,
                message=f"正在识别 {current}（{index}/{total}）",
            )
            updated = _identify_one(db, dict(row), icon_cache=icon_cache)
            store = stamp_tool_ids(_replace_entry(store, updated))
            save_store(db, store)
        write_status(running=False, pending=0, total=total, message="")
    except Exception:
        logger.exception("minecraft inventory: identify worker failed")
        write_status(running=False, pending=0, message="识别中断，请重新扫描")
    finally:
        ephemeral_delete(LOCK_KEY)
        db.close()


def _disk_meta(db: Session, directory: str, filename: str) -> tuple[int, str]:
    base, token, uuid = get_pelican_credentials(db)
    try:
        entries = pelican.list_files(base, token, uuid, directory)
    except pelican.PelicanError:
        return 0, ""
    for row in entries:
        if str(row.get("name") or "") == filename:
            return _int_size(row.get("size")), str(row.get("modified_at") or "")
    return 0, ""


def record_install(
    db: Any,
    *,
    spec: ModToolSpec,
    directory: str,
    filename: str,
    pin: dict[str, Any],
    removed_hits: list[dict[str, Any]],
) -> None:
    """战鸽自己安装：直接改库存那一行，不再走增量队列。"""
    if not can_persist(db):
        return
    store, persist = load_store(db)
    if not persist:
        return
    drop: set[str] = set()
    for hit in removed_hits:
        name = str(hit.get("filename") or "")
        folder = str(hit.get("directory") or directory)
        if name:
            drop.add(jar_path(folder, name))
    store = _drop_paths_in_store(store, drop)
    path = jar_path(directory, filename)
    size, mtime = _disk_meta(db, directory, filename)
    if not size:
        size = _int_size(pin.get("file_size"))
    entry = {
        "path": path,
        "directory": directory,
        "filename": filename,
        "kind": "plugin" if directory.rstrip("/") == "/plugins" else "mod",
        "size": size,
        "modified_at": mtime,
        "sha512": str(pin.get("sha512") or ""),
        "mod_ids": [spec.id],
        "mod_names": [spec.title],
        "mod_version": str(pin.get("version_number") or ""),
        "identified": True,
        "identify_error": "",
        "source": "zhange",
        "project_id": str(pin.get("project_id") or spec.links.modrinth_id or ""),
        "version_id": str(pin.get("version_id") or ""),
        "icon_url": spec.links.icon_url or "",
        "tool_id": spec.id,
    }
    store = stamp_tool_ids(_replace_entry(store, entry))
    store["scanned_at"] = now().isoformat(timespec="seconds")
    save_store(db, store)
