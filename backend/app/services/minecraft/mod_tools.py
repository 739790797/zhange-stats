"""探测 / 安装 / 配置已注册的模组工具，并经 RCON 执行白名单指令。

只看当前正在跑的服（Pelican 盘面 + 启动项 + RCON），对照 Modrinth 后代操。
规格在 `minecraft_mod_registry.SPECS`。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.services.minecraft import modrinth as modrinth
from app.services.minecraft import pelican as pelican
from app.services.integrations_config import (
    get_minecraft_rcon_credentials,
    get_pelican_credentials,
)
from app.services.minecraft.mod_registry import (
    SPECS,
    SPEC_BY_ID,
    ModCommandError,
    ModToolSpec,
    assemble_mod_command,
    clear_draft_content,
    command_tree_out,
    config_directory,
    config_directory_abs,
    install_directory,
    jar_matches_spec,
    preset_by_id,
    resolve_preset_body,
    spec_links_out,
    spec_project_id,
    upsert_draft_content,
    version_from_jar,
)
from app.services.minecraft.rcon import MinecraftRconError, rcon_exec
from app.services.minecraft.status import strip_section_codes

logger = logging.getLogger(__name__)

SCAN_TTL_SEC = 30
PIN_TTL_SEC = 30 * 60
RCON_TIMEOUT = 8.0
SCAN_CACHE_KEY = "minecraft:modtools:scan:v1"
JAR_DIRS = ("/mods", "/plugins")
WORLD_SKIP = {
    "mods",
    "plugins",
    "config",
    "configs",
    "logs",
    "crash-reports",
    "libraries",
    "versions",
    "cache",
    ".cache",
    "tmp",
    "temp",
    "screenshots",
    "resourcepacks",
    "shaderpacks",
    "datapacks",
    "defaultconfigs",
    "kubejs",
    "local",
    "debug",
    "dumps",
    "spark",
    "chunky",
    "zhange",
    "backups",
    "backup",
    "bluemap",
    "dynmap",
    "squaremap",
    "pl3xmap",
    "simplebackups",
    "server_map_cache",
    "journeymap",
}
WORLD_MARKERS = {"level.dat", "region", "dim-1", "dimensions"}
SHAPES = ("square", "circle", "diamond", "ellipse", "triangle", "pentagon", "hexagon", "star", "rectangle")
PATTERNS = ("concentric", "loop", "spiral", "csv", "region")
CHUNKY_ACTIONS = (
    "progress",
    "selection",
    "start",
    "pause",
    "continue",
    "cancel",
    "confirm",
    "spawn",
    "worldborder",
    "apply",
)
ChunkyAction = Literal[
    "progress",
    "selection",
    "start",
    "pause",
    "continue",
    "cancel",
    "confirm",
    "spawn",
    "worldborder",
    "apply",
]
_WORLD_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")
_UNKNOWN_HINTS = (
    "unknown command",
    "unknown or incomplete command",
    "incorrect argument for command",
    "没有此命令",
    "未知的命令",
    "unknown or incomplete",
)
_CENTER_RE = re.compile(
    r"center[:\s]+(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)",
    re.I,
)
_RADIUS_RE = re.compile(r"radius(?:es)?[:\s]+(-?\d+(?:\.\d+)?)(?:\s*[x×,/]\s*(-?\d+(?:\.\d+)?))?", re.I)
_WORLD_LINE_RE = re.compile(r"\bworld[:\s]+([A-Za-z0-9_.:\-]+)", re.I)
_SHAPE_RE = re.compile(r"\bshape[:\s]+([A-Za-z]+)", re.I)
_PATTERN_RE = re.compile(r"\bpattern[:\s]+([A-Za-z0-9_\-]+)", re.I)
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_COUNT_RE = re.compile(
    r"(\d[\d,]*)\s*(?:/\s*(\d[\d,]*))?\s*chunks?",
    re.I,
)
_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:cps|chunks?\s*per\s*second)\b", re.I)
_ETA_RE = re.compile(r"(?:eta|estimated time(?: remaining)?)[:\s]+(\d+:\d{2}:\d{2}|\d+:\d{2})", re.I)
_COORD_RE = re.compile(r"chunk[:\s]+(-?\d+)\s*[,\s]+(-?\d+)", re.I)


class MinecraftModToolsError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def is_unknown_command(raw: str) -> bool:
    text = strip_section_codes(raw or "").lower()
    return any(hint in text for hint in _UNKNOWN_HINTS)


def parse_chunky_state(raw: str) -> dict[str, Any]:
    text = strip_section_codes(raw or "")
    lower = text.lower()
    state = "idle"
    if any(token in lower for token in ("no tasks", "task_none", "currently running: 0", "没有任务")):
        state = "idle"
    elif "paused" in lower or "已暂停" in lower:
        state = "paused"
    elif "cancelled" in lower or "canceled" in lower or "已取消" in lower:
        state = "idle"
    elif any(token in lower for token in ("finished", "complete", "done", "已完成")):
        state = "idle"
    elif "running" in lower or "started" in lower or "进行中" in lower:
        state = "running"
    percent: float | None = None
    match = _PERCENT_RE.search(text)
    if match:
        try:
            percent = float(match.group(1))
        except ValueError:
            percent = None
        if state == "idle" and percent is not None and percent < 100:
            state = "running"
    chunks: int | None = None
    chunks_total: int | None = None
    count = _COUNT_RE.search(text.replace(",", ""))
    if count:
        try:
            chunks = int(count.group(1))
        except ValueError:
            chunks = None
        if count.group(2):
            try:
                chunks_total = int(count.group(2))
            except ValueError:
                chunks_total = None
    rate: float | None = None
    rate_match = _RATE_RE.search(lower)
    if rate_match:
        try:
            rate = float(rate_match.group(1))
        except ValueError:
            rate = None
    eta = ""
    eta_match = _ETA_RE.search(text)
    if eta_match:
        eta = eta_match.group(1)
    world = ""
    world_match = _WORLD_LINE_RE.search(text)
    if world_match:
        world = world_match.group(1)
    elif "task running for " in lower:
        after = text[lower.index("task running for ") + len("task running for ") :]
        world = after.split(".", 1)[0].strip().strip("[]")
    shape = ""
    shape_match = _SHAPE_RE.search(text)
    if shape_match and shape_match.group(1).lower() in SHAPES:
        shape = shape_match.group(1).lower()
    pattern = ""
    pattern_match = _PATTERN_RE.search(text)
    if pattern_match and pattern_match.group(1).lower() in PATTERNS:
        pattern = pattern_match.group(1).lower()
    center_x: int | None = None
    center_z: int | None = None
    center = _CENTER_RE.search(text)
    if center:
        try:
            center_x = int(float(center.group(1)))
            center_z = int(float(center.group(2)))
        except ValueError:
            center_x = None
            center_z = None
    radius: int | None = None
    radius_match = _RADIUS_RE.search(text)
    if radius_match:
        try:
            radius = int(float(radius_match.group(1)))
        except ValueError:
            radius = None
    chunk_x: int | None = None
    chunk_z: int | None = None
    coord = _COORD_RE.search(text)
    if coord:
        try:
            chunk_x = int(coord.group(1))
            chunk_z = int(coord.group(2))
        except ValueError:
            chunk_x = None
            chunk_z = None
    needs_confirm = "confirm" in lower and "chunky confirm" in lower
    return {
        "state": state,
        "world": world,
        "shape": shape,
        "pattern": pattern,
        "center_x": center_x,
        "center_z": center_z,
        "radius": radius,
        "percent": percent,
        "chunks": chunks,
        "chunks_total": chunks_total,
        "rate": rate,
        "eta": eta,
        "chunk_x": chunk_x,
        "chunk_z": chunk_z,
        "needs_confirm": needs_confirm,
        "raw": text.strip(),
    }


def _list_jars(base: str, token: str, uuid: str, directory: str) -> list[dict[str, str]]:
    try:
        entries = pelican.list_files(base, token, uuid, directory)
    except pelican.PelicanError:
        return []
    out: list[dict[str, str]] = []
    for entry in entries:
        if not entry.get("is_file") or entry.get("is_symlink"):
            continue
        name = str(entry.get("name") or "")
        if not name.lower().endswith(".jar"):
            continue
        kind = "plugin" if directory.rstrip("/") == "/plugins" else "mod"
        out.append({"filename": name, "directory": directory, "kind": kind})
    return out


def _looks_like_world(base: str, token: str, uuid: str, name: str) -> bool:
    lower = name.lower()
    if lower in {"world", "world_nether", "world_the_end"}:
        return True
    try:
        entries = pelican.list_files(base, token, uuid, f"/{name}")
    except pelican.PelicanError:
        return False
    names = {str(entry.get("name") or "").lower() for entry in entries}
    return bool(names & WORLD_MARKERS)


def _list_worlds(base: str, token: str, uuid: str) -> list[str]:
    try:
        entries = pelican.list_files(base, token, uuid, "/")
    except pelican.PelicanError:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.get("is_file"):
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name.startswith(".") or name.lower() in WORLD_SKIP:
            continue
        key = name.lower()
        if key in seen:
            continue
        if not _looks_like_world(base, token, uuid, name):
            continue
        seen.add(key)
        names.append(name)
    names.sort(key=lambda row: (row.lower() not in {"world", "world_nether", "world_the_end"}, row.lower()))
    return names[:24]


def _scan_files(db: Session, *, force: bool = False) -> dict[str, Any]:
    cache_key = SCAN_CACHE_KEY
    if not force:
        cached = ephemeral_get(cache_key)
        if cached:
            try:
                parsed = json.loads(cached)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    base, token, uuid = get_pelican_credentials(db)
    payload: dict[str, Any] = {
        "pelican_configured": pelican.pelican_configured(base, token, uuid),
        "jars": [],
        "worlds": [],
        "message": "",
    }
    if not payload["pelican_configured"]:
        payload["message"] = "未配置 Pelican"
        return payload
    jars: list[dict[str, str]] = []
    for directory in JAR_DIRS:
        jars.extend(_list_jars(base, token, uuid, directory))
    payload["jars"] = jars
    payload["worlds"] = _list_worlds(base, token, uuid)
    ephemeral_set(cache_key, json.dumps(payload, ensure_ascii=False), ttl_sec=SCAN_TTL_SEC)
    return payload


def _match_hits(jars: list[dict[str, str]], spec: ModToolSpec) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for row in jars:
        filename = str(row.get("filename") or "")
        if jar_matches_spec(filename, spec):
            hits.append(row)
    return hits


def _rcon_creds(db: Session) -> tuple[str, int, str]:
    host, port, password = get_minecraft_rcon_credentials(db)
    return host, port, password


def _rcon_configured(host: str, password: str) -> bool:
    return bool(host and password)


def rcon_run(db: Session, command: str, *, timeout: float = RCON_TIMEOUT) -> str:
    host, port, password = _rcon_creds(db)
    if not _rcon_configured(host, password):
        raise MinecraftModToolsError("未配置 RCON", status_code=400)
    try:
        return rcon_exec(host, port, password, command, timeout=timeout)
    except MinecraftRconError as exc:
        raise MinecraftModToolsError(exc.message, status_code=502) from exc


def _probe_chunky(db: Session) -> dict[str, Any]:
    host, _port, password = _rcon_creds(db)
    if not _rcon_configured(host, password):
        return {"loaded": False, "rcon_connected": None, "message": "未配置 RCON", "progress": None, "selection": None}
    try:
        progress_raw = rcon_run(db, "chunky progress")
        selection_raw = rcon_run(db, "chunky selection")
    except MinecraftModToolsError as exc:
        return {
            "loaded": False,
            "rcon_connected": False,
            "message": exc.message,
            "progress": None,
            "selection": None,
        }
    loaded = not is_unknown_command(progress_raw) and not is_unknown_command(selection_raw)
    if not loaded:
        return {
            "loaded": False,
            "rcon_connected": True,
            "message": "RCON 已连通，但 Chunky 命令不可用（文件在但未加载？）",
            "progress": parse_chunky_state(progress_raw),
            "selection": parse_chunky_state(selection_raw),
        }
    progress = parse_chunky_state(progress_raw)
    selection = parse_chunky_state(selection_raw)
    merged = {**selection, **{k: v for k, v in progress.items() if v not in (None, "", False)}}
    merged["raw"] = "\n".join(part for part in (progress.get("raw"), selection.get("raw")) if part)
    merged["needs_confirm"] = bool(progress.get("needs_confirm") or selection.get("needs_confirm"))
    if progress.get("state"):
        merged["state"] = progress["state"]
    return {
        "loaded": True,
        "rcon_connected": True,
        "message": "",
        "progress": progress,
        "selection": selection,
        "status": merged,
    }


_MC_VERSION_KEYS = ("MINECRAFT_VERSION", "MC_VERSION", "VANILLA_VERSION", "VERSION")
_PLUGIN_LOADER_TOKENS = ("purpur", "paper", "spigot", "bukkit", "arclight")
_SKIP_MC_VERSIONS = {"", "latest", "latest-release"}


def _mc_version_from_variables(variables: Any) -> str:
    if not isinstance(variables, list):
        return ""
    for row in variables:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip().upper()
        if key not in _MC_VERSION_KEYS:
            continue
        value = str(row.get("value") or "").strip()
        if value.lower() not in _SKIP_MC_VERSIONS:
            return value
    return ""


def _infer_runtime_loader(blob: str) -> str:
    from app.services.minecraft.eggs import infer_loader

    loader = infer_loader(blob)
    if loader:
        return loader
    text = (blob or "").lower()
    for token in _PLUGIN_LOADER_TOKENS:
        if token in text:
            return token
    return ""


def _blob_from_startup(current: dict[str, Any]) -> str:
    variables = current.get("variables") if isinstance(current.get("variables"), list) else []
    return " ".join(
        str(part or "")
        for part in (
            current.get("command"),
            current.get("egg_name"),
            current.get("docker_image"),
            " ".join(str(row or "") for row in (current.get("docker_images") or [])),
            " ".join(
                f"{row.get('key')}={row.get('value')}"
                for row in variables
                if isinstance(row, dict)
            ),
        )
    )


def _entry_names(entries: Any) -> list[str]:
    if not isinstance(entries, list):
        return []
    return [str(row.get("name") or "") for row in entries if isinstance(row, dict)]


def _live_disk_loader(base: str, token: str, uuid: str) -> str:
    """看服根目录自己的加载器/安装器 jar，以及 libraries/net；不扫 /mods 里的模组文件。"""
    try:
        root = pelican.list_files(base, token, uuid, "/")
    except pelican.PelicanError:
        return ""
    names = _entry_names(root)
    loader = _infer_runtime_loader(" ".join(names))
    if loader:
        return loader
    if not any(name.lower() == "libraries" for name in names):
        return ""
    try:
        net = pelican.list_files(base, token, uuid, "/libraries/net")
    except pelican.PelicanError:
        return ""
    return _infer_runtime_loader(" ".join(_entry_names(net)))


def _live_egg_context(db: Session) -> dict[str, str]:
    """当前服的加载器与 MC 版本：Pelican 启动项，不够再看服根目录。"""
    base, token, uuid = get_pelican_credentials(db)
    if not pelican.pelican_configured(base, token, uuid):
        return {"loader": "", "mc_version": ""}
    loader = ""
    mc_version = ""
    try:
        from app.services.minecraft.eggs import inspect_current_egg

        current = inspect_current_egg(base, token, uuid)
        loader = str(current.get("inferred_loader") or "") or _infer_runtime_loader(
            _blob_from_startup(current)
        )
        mc_version = _mc_version_from_variables(current.get("variables"))
    except pelican.PelicanError:
        pass
    except Exception:
        logger.exception("minecraft mod tools: inspect current egg failed")
    if not loader:
        loader = _live_disk_loader(base, token, uuid)
    return {"loader": loader, "mc_version": mc_version}


def _server_context(db: Session) -> dict[str, str]:
    return _live_egg_context(db)


def _pin_cache_key(project_id: str, loader: str, mc_version: str) -> str:
    return f"minecraft:modtools:pin:v1:{project_id}:{loader}:{mc_version}"


def lookup_latest_pin(spec: ModToolSpec, *, loader: str, mc_version: str) -> dict[str, Any] | None:
    project_id = (spec.links.modrinth_id or spec.links.modrinth_slug or "").strip()
    if not project_id or not loader or not mc_version:
        return None
    cache_key = _pin_cache_key(project_id, loader, mc_version)
    cached = ephemeral_get(cache_key)
    if cached:
        try:
            parsed = json.loads(cached)
            if parsed is None:
                return None
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    try:
        pin = modrinth.latest_pin(project_id, loader=loader, mc_version=mc_version)
    except modrinth.ModrinthError:
        logger.exception("minecraft mod tools: modrinth lookup failed for %s", spec.id)
        pin = None
    ephemeral_set(cache_key, json.dumps(pin, ensure_ascii=False), ttl_sec=PIN_TTL_SEC)
    return pin if isinstance(pin, dict) else None


def _catalog_out(
    spec: ModToolSpec,
    *,
    loader: str,
    mc_version: str,
    filename: str,
    directory: str,
) -> dict[str, Any]:
    target = install_directory(loader, spec, present_directory=directory)
    installed_version = version_from_jar(filename)
    pin = lookup_latest_pin(spec, loader=loader, mc_version=mc_version)
    latest_version = str((pin or {}).get("version_number") or "")
    latest_filename = str((pin or {}).get("filename") or "")
    compatible = bool(pin)
    update_available = False
    if pin and filename:
        if latest_version and installed_version:
            update_available = latest_version != installed_version
        elif latest_filename and latest_filename != filename:
            update_available = True
    if compatible:
        catalog_message = ""
    elif not loader:
        catalog_message = "读不到当前服加载器"
    elif not mc_version:
        catalog_message = "读不到当前 Minecraft 版本"
    else:
        catalog_message = "当前加载器/版本在 Modrinth 没有匹配文件"
    return {
        "loader": loader,
        "mc_version": mc_version,
        "project_id": spec_project_id(spec),
        "installed_version": installed_version,
        "latest_version": latest_version,
        "latest_filename": latest_filename,
        "compatible": compatible,
        "update_available": update_available,
        "target_directory": target,
        "message": catalog_message,
    }


def _tool_out(
    spec: ModToolSpec,
    *,
    hits: list[dict[str, str]],
    loaded: bool,
    loader: str,
    mc_version: str,
) -> dict[str, Any]:
    present = bool(hits) or loaded
    filename = hits[0]["filename"] if hits else ""
    directory = hits[0]["directory"] if hits else ""
    kind = hits[0]["kind"] if hits else ""
    links = spec_links_out(spec, loader)
    return {
        "id": spec.id,
        "title": spec.title,
        "summary": spec.summary,
        "present": present,
        "loaded": loaded,
        "filename": filename,
        "directory": directory,
        "kind": kind,
        "files": hits,
        "capabilities": list(spec.capabilities),
        "icon_url": links.get("icon_url") or "",
        "links": links,
        "catalog": _catalog_out(
            spec,
            loader=loader,
            mc_version=mc_version,
            filename=filename,
            directory=directory,
        ),
        "presets": [
            {"id": row.id, "title": row.title, "summary": row.summary} for row in spec.presets
        ],
        "config_directory": config_directory_abs(
            loader, spec, present_directory=directory
        ),
        "command_tree": command_tree_out(spec),
    }


def collect_mod_tools(db: Session, *, force: bool = False) -> dict[str, Any]:
    scan = _scan_files(db, force=force)
    host, _port, password = _rcon_creds(db)
    rcon_ok = _rcon_configured(host, password)
    ctx = _server_context(db)
    loader = ctx["loader"]
    mc_version = ctx["mc_version"]
    tools: list[dict[str, Any]] = []
    chunky_live: dict[str, Any] | None = None
    jars = scan.get("jars") if isinstance(scan.get("jars"), list) else []
    for spec in SPECS:
        hits = _match_hits([row for row in jars if isinstance(row, dict)], spec)
        loaded = False
        if spec.id == "chunky" and (hits or rcon_ok):
            live = _probe_chunky(db)
            chunky_live = live
            loaded = bool(live.get("loaded"))
        tools.append(
            _tool_out(
                spec,
                hits=hits,
                loaded=loaded,
                loader=loader,
                mc_version=mc_version,
            )
        )
    return {
        "ok": True,
        "pelican_configured": bool(scan.get("pelican_configured")),
        "rcon_configured": rcon_ok,
        "rcon_connected": None if not chunky_live else chunky_live.get("rcon_connected"),
        "loader": loader,
        "mc_version": mc_version,
        "message": str(scan.get("message") or ""),
        "worlds": scan.get("worlds") or [],
        "tools": tools,
        "chunky": None if not chunky_live else chunky_live.get("status"),
    }


def _require_spec(tool_id: str) -> ModToolSpec:
    spec = SPEC_BY_ID.get((tool_id or "").strip())
    if spec is None:
        raise MinecraftModToolsError("未知模组工具", status_code=404)
    return spec


def _pelican(db: Session) -> tuple[str, str, str]:
    base, token, uuid = get_pelican_credentials(db)
    if not pelican.pelican_configured(base, token, uuid):
        raise MinecraftModToolsError("未配置 Pelican", status_code=400)
    return base, token, uuid


def _invalidate_scans() -> None:
    ephemeral_delete(SCAN_CACHE_KEY)
    try:
        from app.services.minecraft.profile import invalidate_live_public_facts

        invalidate_live_public_facts()
    except Exception:
        logger.exception("minecraft mod tools: invalidate live facts failed")


def _ensure_config_dir(base: str, token: str, uuid: str, directory: str) -> None:
    parts = [part for part in directory.replace("\\", "/").strip("/").split("/") if part]
    root = "/"
    for name in parts:
        pelican.create_folder(base, token, uuid, root=root, name=name, ignore_exists=True)
        root = f"{root.rstrip('/')}/{name}"


def _present_directory(db: Session, spec: ModToolSpec, *, force: bool = False) -> str:
    scan = _scan_files(db, force=force)
    jars = scan.get("jars") if isinstance(scan.get("jars"), list) else []
    hits = _match_hits([row for row in jars if isinstance(row, dict)], spec)
    return str(hits[0]["directory"] or "") if hits else ""


def _preset_blob(db: Session) -> dict[str, Any]:
    from app.services.minecraft.profile import get_or_create_profile

    row = get_or_create_profile(db)
    raw = getattr(row, "mod_presets_json", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _require_preset(spec: ModToolSpec, preset_id: str):
    if "config" not in spec.capabilities:
        raise MinecraftModToolsError("该模组没有配置预设")
    preset = preset_by_id(spec, preset_id)
    if preset is None:
        raise MinecraftModToolsError("没有这个配置预设")
    return preset


def get_tool_preset(db: Session, tool_id: str, preset_id: str) -> dict[str, Any]:
    spec = _require_spec(tool_id)
    preset = _require_preset(spec, preset_id)
    ctx = _server_context(db)
    present_dir = _present_directory(db, spec)
    filename, content, source = resolve_preset_body(
        preset,
        ctx["loader"],
        spec,
        _preset_blob(db),
        present_directory=present_dir,
    )
    if not filename:
        raise MinecraftModToolsError("该预设没有对应加载器的出厂文件")
    return {
        "ok": True,
        "tool_id": spec.id,
        "preset_id": preset.id,
        "title": preset.title,
        "summary": preset.summary,
        "source": source,
        "filename": filename,
        "content": content,
    }


def save_tool_preset(
    db: Session,
    tool_id: str,
    preset_id: str,
    *,
    content: str | None = None,
    restore: bool = False,
) -> dict[str, Any]:
    spec = _require_spec(tool_id)
    preset = _require_preset(spec, preset_id)
    from app.services.minecraft.profile import get_or_create_profile

    row = get_or_create_profile(db)
    blob = getattr(row, "mod_presets_json", None)
    if restore:
        row.mod_presets_json = clear_draft_content(blob, spec.id, preset.id)
    else:
        if content is None:
            raise MinecraftModToolsError("请填写预设内容")
        if len(content) > 256_000:
            raise MinecraftModToolsError("预设内容过长")
        row.mod_presets_json = upsert_draft_content(blob, spec.id, preset.id, content)
    db.commit()
    db.refresh(row)
    return get_tool_preset(db, spec.id, preset.id)


def apply_tool_preset(db: Session, tool_id: str, preset_id: str = "") -> dict[str, Any]:
    spec = _require_spec(tool_id)
    preset = _require_preset(spec, preset_id)
    ctx = _server_context(db)
    present_dir = _present_directory(db, spec, force=True)
    filename, content, source = resolve_preset_body(
        preset,
        ctx["loader"],
        spec,
        _preset_blob(db),
        present_directory=present_dir,
    )
    if not filename:
        raise MinecraftModToolsError("该预设没有对应加载器的出厂文件")
    rel_dir = config_directory(ctx["loader"], spec, present_directory=present_dir)
    if not rel_dir:
        raise MinecraftModToolsError("该模组未声明配置目录")
    base, token, uuid = _pelican(db)
    _ensure_config_dir(base, token, uuid, rel_dir)
    path = f"/{rel_dir}/{filename}".replace("//", "/")
    pelican.write_file(base, token, uuid, path, content)
    _invalidate_scans()
    reloaded = False
    if spec.probe_command:
        try:
            rcon_run(db, f"{spec.id} reload")
            reloaded = True
        except MinecraftModToolsError:
            reloaded = False
    src_label = "草稿" if source == "draft" else "出厂"
    return {
        "ok": True,
        "tool_id": spec.id,
        "preset_id": preset.id,
        "path": path,
        "source": source,
        "reloaded": reloaded,
        "restart_required": not reloaded,
        "message": (
            f"已写入 {path}（{src_label}）"
            + ("，并已 reload" if reloaded else "，重启后生效")
        ),
    }


def pick_install_pin(versions: list[dict[str, Any]], version_id: str) -> dict[str, Any]:
    wanted = (version_id or "").strip()
    if not wanted:
        raise MinecraftModToolsError("请选择模组版本")
    for row in versions:
        if str(row.get("version_id") or "") == wanted:
            return row
    raise MinecraftModToolsError("该版本不匹配当前服的加载器或游戏版本")


def list_tool_versions(db: Session, tool_id: str) -> dict[str, Any]:
    spec = _require_spec(tool_id)
    ctx = _server_context(db)
    loader = ctx["loader"]
    mc_version = ctx["mc_version"]
    project_id = spec_project_id(spec)
    versions: list[dict[str, Any]] = []
    message = ""
    if not project_id:
        message = "该模组没有 Modrinth 项目"
    elif not loader or not mc_version:
        message = "读不到当前服的加载器或 Minecraft 版本"
    else:
        try:
            versions = modrinth.list_versions(
                project_id, loader=loader, mc_version=mc_version
            )
        except modrinth.ModrinthError as exc:
            raise MinecraftModToolsError(exc.message, status_code=502) from exc
        if not versions:
            message = f"Modrinth 上没有 {loader} / {mc_version} 可用的 {spec.title} 文件"
    return {
        "ok": True,
        "tool_id": spec.id,
        "source": "modrinth",
        "loader": loader,
        "mc_version": mc_version,
        "message": message,
        "versions": versions,
    }


def install_tool(
    db: Session,
    tool_id: str,
    *,
    version_id: str = "",
    preset_id: str = "",
    restart: bool = False,
) -> dict[str, Any]:
    spec = _require_spec(tool_id)
    if "install" not in spec.capabilities:
        raise MinecraftModToolsError("该模组不支持快捷安装")
    ctx = _server_context(db)
    loader = ctx["loader"]
    mc_version = ctx["mc_version"]
    if not loader or not mc_version:
        raise MinecraftModToolsError("读不到当前服的加载器或 Minecraft 版本")
    project_id = spec_project_id(spec)
    if not project_id:
        raise MinecraftModToolsError("该模组没有 Modrinth 项目")
    try:
        versions = modrinth.list_versions(project_id, loader=loader, mc_version=mc_version)
    except modrinth.ModrinthError as exc:
        raise MinecraftModToolsError(exc.message, status_code=502) from exc
    pin = pick_install_pin(versions, version_id)
    filename = str(pin.get("filename") or "")
    url = str(pin.get("download_url") or "")
    if not filename or not url:
        raise MinecraftModToolsError("Modrinth 返回的文件不完整")
    scan = _scan_files(db, force=True)
    jars = scan.get("jars") if isinstance(scan.get("jars"), list) else []
    hits = _match_hits([row for row in jars if isinstance(row, dict)], spec)
    present_dir = hits[0]["directory"] if hits else ""
    directory = install_directory(loader, spec, present_directory=present_dir)
    base, token, uuid = _pelican(db)
    removed = 0
    by_dir: dict[str, list[str]] = {}
    for row in hits:
        by_dir.setdefault(str(row.get("directory") or directory), []).append(
            str(row.get("filename") or "")
        )
    for folder, names in by_dir.items():
        names = [name for name in names if name and name != filename]
        if not names:
            continue
        try:
            pelican.delete_files(base, token, uuid, root=folder, files=names)
            removed += len(names)
        except pelican.PelicanError as exc:
            raise MinecraftModToolsError(exc.message, status_code=exc.status_code or 502) from exc
    try:
        pelican.pull_file(base, token, uuid, url=url, directory=directory, filename=filename)
    except pelican.PelicanError as exc:
        raise MinecraftModToolsError(exc.message, status_code=exc.status_code or 502) from exc
    notes = [f"已下载 {directory}/{filename}"]
    if removed:
        notes.append(f"已替换旧文件 {removed} 个")
    config_path = ""
    if (preset_id or "").strip():
        applied = apply_tool_preset(db, spec.id, preset_id.strip())
        config_path = str(applied.get("path") or "")
        notes.append(str(applied.get("message") or ""))
    restarted = False
    if restart:
        try:
            pelican.send_power(base, token, uuid, "restart")
            restarted = True
            notes.append("已请求重启")
        except pelican.PelicanError as exc:
            notes.append(f"下载成功，但重启失败：{exc.message}")
    _invalidate_scans()
    return {
        "ok": True,
        "tool_id": spec.id,
        "filename": filename,
        "directory": directory,
        "version_number": str(pin.get("version_number") or ""),
        "config_path": config_path,
        "restarted": restarted,
        "restart_required": not restarted,
        "message": "；".join(part for part in notes if part),
    }


def _require_world(world: str) -> str:
    text = (world or "").strip()
    if not text:
        return ""
    if not _WORLD_RE.match(text):
        raise MinecraftModToolsError("世界名不合法")
    return text


def _require_shape(shape: str) -> str:
    text = (shape or "").strip().lower()
    if not text:
        return ""
    if text not in SHAPES:
        raise MinecraftModToolsError("不支持的形状")
    return text


def _require_pattern(pattern: str) -> str:
    text = (pattern or "").strip().lower()
    if not text:
        return ""
    if text not in PATTERNS:
        raise MinecraftModToolsError("不支持的生成模式")
    return text


def _require_int(value: int | None, *, lo: int, hi: int, label: str) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise MinecraftModToolsError(f"{label}须为整数") from exc
    if number < lo or number > hi:
        raise MinecraftModToolsError(f"{label}超出范围")
    return number


def build_chunky_commands(
    action: str,
    *,
    world: str = "",
    shape: str = "",
    pattern: str = "",
    center_x: int | None = None,
    center_z: int | None = None,
    radius: int | None = None,
) -> list[str]:
    act = (action or "").strip().lower()
    if act not in CHUNKY_ACTIONS:
        raise MinecraftModToolsError("不支持的 Chunky 操作")
    world = _require_world(world)
    shape = _require_shape(shape)
    pattern = _require_pattern(pattern)
    cx = _require_int(center_x, lo=-30_000_000, hi=30_000_000, label="中心 X")
    cz = _require_int(center_z, lo=-30_000_000, hi=30_000_000, label="中心 Z")
    rad = _require_int(radius, lo=1, hi=1_000_000, label="半径")
    if act in {"progress", "selection", "pause", "continue", "cancel", "confirm", "spawn", "worldborder"}:
        if world and act in {"pause", "continue", "cancel", "worldborder"}:
            return [f"chunky {act} {world}"]
        return [f"chunky {act}"]
    apply_cmds: list[str] = []
    if world:
        apply_cmds.append(f"chunky world {world}")
    if shape:
        apply_cmds.append(f"chunky shape {shape}")
    if cx is not None and cz is not None:
        apply_cmds.append(f"chunky center {cx} {cz}")
    elif cx is not None or cz is not None:
        raise MinecraftModToolsError("中心 X/Z 须成对填写")
    if rad is not None:
        apply_cmds.append(f"chunky radius {rad}")
    if pattern:
        apply_cmds.append(f"chunky pattern {pattern}")
    if act == "apply":
        if not apply_cmds:
            raise MinecraftModToolsError("没有可应用的选择参数")
        apply_cmds.append("chunky selection")
        return apply_cmds
    if act == "start":
        if world and shape and cx is not None and cz is not None and rad is not None:
            return [f"chunky start {world} {shape} {cx} {cz} {rad}"]
        return [*apply_cmds, "chunky start"]
    raise MinecraftModToolsError("不支持的 Chunky 操作")


def run_tool_command(
    db: Session,
    tool_id: str,
    command_id: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = _require_spec(tool_id)
    try:
        command = assemble_mod_command(spec, command_id, args)
    except ModCommandError as exc:
        raise MinecraftModToolsError(str(exc)) from exc
    raw = strip_section_codes(rcon_run(db, command)).strip()
    if is_unknown_command(raw):
        raise MinecraftModToolsError("服务器未加载该模组（命令不可用）", status_code=400)
    status: dict[str, Any] = {}
    if spec.id == "chunky":
        parsed = parse_chunky_state(raw)
        try:
            live = _probe_chunky(db)
            if isinstance(live.get("status"), dict):
                parsed = live["status"]
                extra = str(live["status"].get("raw") or "")
                if extra and extra not in raw:
                    raw = f"{raw}\n{extra}".strip()
                    parsed["raw"] = raw
        except MinecraftModToolsError:
            pass
        status = parsed
    return {
        "ok": True,
        "action": (command_id or "").strip(),
        "commands": [command],
        "message": "",
        "raw": raw,
        "status": status,
    }


def run_chunky_command(
    db: Session,
    action: str,
    *,
    world: str = "",
    shape: str = "",
    pattern: str = "",
    center_x: int | None = None,
    center_z: int | None = None,
    radius: int | None = None,
) -> dict[str, Any]:
    commands = build_chunky_commands(
        action,
        world=world,
        shape=shape,
        pattern=pattern,
        center_x=center_x,
        center_z=center_z,
        radius=radius,
    )
    outputs: list[str] = []
    for command in commands:
        outputs.append(rcon_run(db, command))
    raw = "\n".join(strip_section_codes(part) for part in outputs if part).strip()
    if any(is_unknown_command(part) for part in outputs):
        raise MinecraftModToolsError("服务器未加载 Chunky（命令不可用）", status_code=400)
    parsed = parse_chunky_state(raw)
    if action in {"progress", "selection", "apply", "start", "pause", "continue", "cancel"}:
        try:
            live = _probe_chunky(db)
            if isinstance(live.get("status"), dict):
                parsed = live["status"]
                extra = str(live["status"].get("raw") or "")
                if extra and extra not in raw:
                    raw = f"{raw}\n{extra}".strip()
                    parsed["raw"] = raw
        except MinecraftModToolsError:
            pass
    return {
        "ok": True,
        "action": action,
        "commands": commands,
        "message": raw.splitlines()[0] if raw else "已执行",
        "raw": raw,
        "status": parsed,
    }
