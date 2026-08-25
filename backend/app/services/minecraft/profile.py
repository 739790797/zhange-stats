"""单行 Minecraft 目标档案：读写、解析加载器版本、经 Pelican 应用。"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.core.timeutil import now_naive
from app.models.minecraft import PROFILE_ROW_ID, MinecraftServerProfile
from app.services.minecraft import mod_catalog as catalog
from app.services.minecraft import modrinth as modrinth
from app.services.minecraft import pack as pack
from app.services.minecraft import status as status_svc
from app.services.minecraft import pelican as pelican
from app.services.integrations_config import (
    get_minecraft_public_address,
    get_minecraft_rcon_credentials,
    get_pelican_credentials,
)

logger = logging.getLogger(__name__)

FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
MOJANG_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
UA = "zhange-stats-minecraft/1.0"


class MinecraftProfileError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _http_json(url: str, *, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise MinecraftProfileError(f"上游 HTTP {exc.code}", status_code=502) from exc
    except urllib.error.URLError as exc:
        raise MinecraftProfileError(f"无法连接上游：{exc.reason}", status_code=502) from exc


def _http_text(url: str, *, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise MinecraftProfileError(f"上游 HTTP {exc.code}", status_code=502) from exc
    except urllib.error.URLError as exc:
        raise MinecraftProfileError(f"无法连接上游：{exc.reason}", status_code=502) from exc


def get_or_create_profile(db: Session) -> MinecraftServerProfile:
    row = (
        db.query(MinecraftServerProfile)
        .filter(MinecraftServerProfile.id == PROFILE_ROW_ID)
        .first()
    )
    if row:
        if seed_applied_if_missing(row):
            db.commit()
            db.refresh(row)
        return row
    row = MinecraftServerProfile(
        id=PROFILE_ROW_ID,
        mc_version="1.21.1",
        loader="fabric",
        loader_version="",
        egg_id=0,
        startup="",
        mods_json=[],
        overrides_json={},
        mod_presets_json={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mods_list(row: MinecraftServerProfile) -> list[dict[str, Any]]:
    raw = row.mods_json
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    return []


def _overrides_map(row: MinecraftServerProfile) -> dict[str, str]:
    raw = row.overrides_json
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


_LEGACY_SNAPSHOT_KEYS = (
    "rcon_enabled",
    "rcon_port",
    "rcon_connect_host",
    "rcon_connect_port",
    "rcon_password_set",
    "public_host",
    "public_port",
)


def desired_snapshot(row: MinecraftServerProfile) -> dict[str, Any]:
    return {
        "mc_version": row.mc_version,
        "loader": row.loader,
        "loader_version": row.loader_version or "",
        "egg_id": int(getattr(row, "egg_id", 0) or 0),
        "startup": str(getattr(row, "startup", "") or ""),
        "mods": _mods_list(row),
        "overrides": _overrides_map(row),
    }


def _without_legacy_snapshot_keys(snap: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snap.items() if key not in _LEGACY_SNAPSHOT_KEYS}


def applied_snapshot(row: MinecraftServerProfile) -> dict[str, Any] | None:
    raw = getattr(row, "applied_json", None)
    if not isinstance(raw, dict) or not raw:
        return None
    return raw


def seed_applied_if_missing(row: MinecraftServerProfile) -> bool:
    """旧行只有 last_applied_at、没有快照时，用当前档案补一份（须在改草稿之前调用）。"""
    if applied_snapshot(row) is not None or row.last_applied_at is None:
        return False
    row.applied_json = desired_snapshot(row)
    return True


def _canonical_snapshot(snap: dict[str, Any]) -> str:
    return json.dumps(snap, sort_keys=True, ensure_ascii=False, default=str)


def is_playbook_dirty(row: MinecraftServerProfile) -> bool:
    applied = applied_snapshot(row)
    if applied is None:
        return False
    return _canonical_snapshot(_strip_snapshot_meta(applied)) != _canonical_snapshot(
        _strip_snapshot_meta(desired_snapshot(row))
    )


def _playbook_from_parts(
    *,
    mc_version: str,
    loader: str,
    loader_version: str,
    egg_id: int = 0,
    startup: str = "",
    mods: list[dict[str, Any]],
    overrides: dict[str, str],
) -> dict[str, Any]:
    props_text = overrides.get("server.properties") or ""
    extra = [
        {"path": path, "content": content}
        for path, content in overrides.items()
        if path != "server.properties"
    ]
    return {
        "mc_version": mc_version,
        "loader": loader,
        "loader_version": loader_version or "",
        "egg_id": int(egg_id or 0),
        "startup": startup or "",
        "mods": mods,
        "properties": pack.redact_properties(pack.parse_properties(props_text)),
        "overrides": extra,
    }


def playbook_from_snapshot(snap: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snap, dict):
        return None
    overrides_raw = snap.get("overrides")
    overrides = (
        {str(k): str(v) for k, v in overrides_raw.items()}
        if isinstance(overrides_raw, dict)
        else {}
    )
    mods_raw = snap.get("mods")
    mods = [m for m in mods_raw if isinstance(m, dict)] if isinstance(mods_raw, list) else []
    return _playbook_from_parts(
        mc_version=str(snap.get("mc_version") or ""),
        loader=str(snap.get("loader") or ""),
        loader_version=str(snap.get("loader_version") or ""),
        egg_id=int(snap.get("egg_id") or 0),
        startup=str(snap.get("startup") or ""),
        mods=mods,
        overrides=overrides,
    )


def public_applied_view(row: MinecraftServerProfile) -> dict[str, Any] | None:
    playbook = playbook_from_snapshot(applied_snapshot(row))
    if playbook is None:
        return None
    applied_at = row.last_applied_at
    mods = []
    for mod in playbook.get("mods") or []:
        if not isinstance(mod, dict):
            continue
        filename = str(mod.get("filename") or "")
        if not filename:
            continue
        mods.append(
            {
                "project_title": str(mod.get("project_title") or ""),
                "filename": filename,
                "version_number": str(mod.get("version_number") or ""),
                "project_id": str(mod.get("project_id") or ""),
                "slug": str(mod.get("slug") or ""),
            }
        )
    properties = playbook.get("properties") if isinstance(playbook.get("properties"), dict) else {}
    shown = {
        key: str(properties[key])
        for key in pack.COMMON_PROPERTY_KEYS
        if key in properties and str(properties.get(key) or "").strip()
    }
    return {
        "mc_version": playbook["mc_version"],
        "loader": playbook["loader"],
        "loader_version": playbook["loader_version"],
        "mods": mods,
        "properties": shown,
        "last_applied_at": applied_at.isoformat() if applied_at else None,
    }


LIVE_FACTS_KEY = "minecraft:live_public_facts:v2"
LIVE_FACTS_TTL_SEC = 45


def read_cached_live_facts() -> dict[str, Any]:
    cached = ephemeral_get(LIVE_FACTS_KEY)
    if not cached:
        return {}
    try:
        parsed = json.loads(cached)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def jar_display_name(filename: str) -> str:
    name = str(filename or "").strip()
    if name.lower().endswith(".jar"):
        return name[:-4]
    return name


def parse_whitelist_json(text: str) -> list[dict[str, str]]:
    try:
        data = json.loads(text or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        uid = str(row.get("uuid") or row.get("id") or "").strip()
        if not name and not uid:
            continue
        out.append({"name": name or uid, "id": uid})
    return out


def merge_overview_mods(
    live_mods: list[dict[str, str]] | None,
    applied_mods: list[dict[str, str]],
) -> list[dict[str, str]]:
    applied_by_file = {
        str(row.get("filename") or ""): row
        for row in applied_mods
        if str(row.get("filename") or "")
    }
    if live_mods is None:
        return list(applied_mods)
    out: list[dict[str, str]] = []
    for row in live_mods:
        filename = str(row.get("filename") or "")
        if not filename:
            continue
        hit = applied_by_file.get(filename) or {}
        out.append(
            {
                "filename": filename,
                "project_title": str(
                    hit.get("project_title") or row.get("project_title") or jar_display_name(filename)
                ),
                "version_number": str(hit.get("version_number") or row.get("version_number") or ""),
                "project_id": str(hit.get("project_id") or row.get("project_id") or ""),
                "slug": str(hit.get("slug") or row.get("slug") or ""),
            }
        )
    return out


def _player_key(row: dict[str, Any]) -> str:
    uid = re.sub(r"[^0-9a-f]", "", str(row.get("id") or "").lower())
    if len(uid) == 32:
        return f"id:{uid}"
    name = str(row.get("name") or "").strip().lower()
    return f"name:{name}" if name else ""


def merge_roster(
    online: list[dict[str, str]],
    *groups: list[dict[str, str]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group:
            if not isinstance(row, dict):
                continue
            key = _player_key(row)
            if not key:
                continue
            current = by_key.get(key)
            name = str(row.get("name") or "").strip()
            uid = str(row.get("id") or "").strip()
            if current is None:
                by_key[key] = {"name": name or uid, "id": uid, "online": False}
                continue
            if name and not current["name"]:
                current["name"] = name
            if uid and not current["id"]:
                current["id"] = uid
    online_keys = {_player_key(row) for row in online if isinstance(row, dict)}
    online_names = {
        str(row.get("name") or "").strip().lower()
        for row in online
        if isinstance(row, dict) and str(row.get("name") or "").strip()
    }
    for row in by_key.values():
        key = _player_key(row)
        row["online"] = key in online_keys or row["name"].lower() in online_names
    for row in online:
        if not isinstance(row, dict):
            continue
        key = _player_key(row)
        if key and key not in by_key:
            by_key[key] = {
                "name": str(row.get("name") or "").strip(),
                "id": str(row.get("id") or "").strip(),
                "online": True,
            }
    out = list(by_key.values())
    out.sort(key=lambda row: (not row["online"], str(row["name"]).lower()))
    return out


def invalidate_live_public_facts() -> None:
    ephemeral_delete(LIVE_FACTS_KEY)


def _public_property_map(raw: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(raw[key])
        for key in pack.COMMON_PROPERTY_KEYS
        if key in raw and str(raw.get(key) or "").strip()
    }


def load_live_public_facts(base: str, token: str, uuid: str) -> dict[str, Any]:
    cached = read_cached_live_facts()
    if cached:
        return cached

    facts: dict[str, Any] = {"properties": {}, "mods": None, "whitelist": [], "known": []}
    try:
        text = pelican.get_file_contents(base, token, uuid, "/server.properties")
        facts["properties"] = _public_property_map(pack.parse_properties(text))
    except pelican.PelicanError:
        pass
    try:
        entries = pelican.list_files(base, token, uuid, "/mods")
        mods: list[dict[str, str]] = []
        for entry in entries:
            if not entry.get("is_file") or entry.get("is_symlink"):
                continue
            name = str(entry.get("name") or "")
            if not name.lower().endswith(".jar"):
                continue
            mods.append(
                {
                    "filename": name,
                    "project_title": jar_display_name(name),
                    "version_number": "",
                }
            )
        facts["mods"] = mods
    except pelican.PelicanError:
        pass
    whitelist_on = str(facts["properties"].get("white-list") or "").lower() == "true"
    if whitelist_on:
        try:
            raw = pelican.get_file_contents(base, token, uuid, "/whitelist.json")
            facts["whitelist"] = parse_whitelist_json(raw)
        except pelican.PelicanError:
            pass
    try:
        raw = pelican.get_file_contents(base, token, uuid, "/usercache.json")
        facts["known"] = parse_whitelist_json(raw)
    except pelican.PelicanError:
        pass
    ephemeral_set(
        LIVE_FACTS_KEY,
        json.dumps(facts, ensure_ascii=False),
        ttl_sec=LIVE_FACTS_TTL_SEC,
    )
    return facts


def profile_to_dict(row: MinecraftServerProfile, *, pelican_ok: bool) -> dict[str, Any]:
    playbook = _playbook_from_parts(
        mc_version=row.mc_version,
        loader=row.loader,
        loader_version=row.loader_version or "",
        egg_id=int(getattr(row, "egg_id", 0) or 0),
        startup=str(getattr(row, "startup", "") or ""),
        mods=_mods_list(row),
        overrides=_overrides_map(row),
    )
    applied = row.last_applied_at
    return {
        **playbook,
        "last_applied_at": applied.isoformat() if applied else None,
        "last_apply_message": row.last_apply_message,
        "pelican_configured": pelican_ok,
        "startup_hint": "bash zhange/boot.sh java -Xms128M -XX:MaxRAMPercentage=95.0 -jar {{SERVER_JARFILE}}",
        "playbook_dirty": is_playbook_dirty(row),
        "applied": playbook_from_snapshot(applied_snapshot(row)),
        "stages": playbook_stages(row),
    }


def save_profile(db: Session, payload: dict[str, Any]) -> MinecraftServerProfile:
    row = get_or_create_profile(db)
    seed_applied_if_missing(row)
    loader = pack.normalize_loader(str(payload.get("loader") or row.loader))
    mc_version = str(payload.get("mc_version") or row.mc_version).strip()
    if not mc_version:
        raise MinecraftProfileError("请填写游戏版本")
    loader_version = str(payload.get("loader_version") or "").strip()
    if loader_version.lower() in {"", "latest"}:
        loader_version = resolve_latest_loader(loader, mc_version) or loader_version
    mods = payload.get("mods") if isinstance(payload.get("mods"), list) else []
    clean_mods: list[dict[str, Any]] = []
    for mod in mods:
        if not isinstance(mod, dict):
            continue
        if str(mod.get("env_server") or "") == "unsupported":
            continue
        if not mod.get("filename") or not mod.get("download_url") or not mod.get("sha512"):
            raise MinecraftProfileError("模组条目缺少 filename / download_url / sha512")
        clean_mods.append(mod)
    extra = payload.get("overrides") if isinstance(payload.get("overrides"), list) else []
    properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
    existing = _overrides_map(row).get("server.properties") or ""
    overrides = pack.build_overrides_map(
        {str(k): str(v) for k, v in properties.items() if str(k) not in pack.SECRET_PROPERTY_KEYS},
        [e for e in extra if isinstance(e, dict)],
        existing_properties_text=existing,
    )
    row.mc_version = mc_version
    row.loader = loader
    row.loader_version = loader_version
    try:
        row.egg_id = int(payload.get("egg_id") or 0)
    except (TypeError, ValueError):
        row.egg_id = 0
    row.startup = str(payload.get("startup") or "").strip()
    row.mods_json = clean_mods
    row.overrides_json = overrides
    db.commit()
    db.refresh(row)
    return row


def _rows_from_mojang(data: Any) -> list[dict[str, Any]]:
    versions = data.get("versions") if isinstance(data, dict) else None
    if not isinstance(versions, list):
        return []
    out: list[dict[str, Any]] = []
    for row in versions:
        if not isinstance(row, dict):
            continue
        ver = str(row.get("id") or "")
        if not ver:
            continue
        kind = str(row.get("type") or "release").strip() or "release"
        released = str(row.get("releaseTime") or "").strip() or None
        out.append(
            {
                "version": ver,
                "stable": kind == "release",
                "version_type": kind,
                "release_time": released,
            }
        )
    return out


def _rows_from_fabric(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        ver = str(row.get("version") or "")
        if not ver:
            continue
        stable = bool(row.get("stable"))
        out.append(
            {
                "version": ver,
                "stable": stable,
                "version_type": "release" if stable else "snapshot",
                "release_time": None,
            }
        )
    return out


def list_game_versions() -> list[dict[str, Any]]:
    try:
        rows = _rows_from_mojang(_http_json(MOJANG_MANIFEST))
        if rows:
            return rows
    except MinecraftProfileError as exc:
        logger.warning("Mojang version manifest failed: %s", exc)
    return _rows_from_fabric(_http_json(f"{FABRIC_META}/versions/game"))


def _xml_versions(text: str) -> list[str]:
    return re.findall(r"<version>([^<]+)</version>", text)


def list_loader_versions(loader: str, mc_version: str) -> list[str]:
    loader = pack.normalize_loader(loader)
    mc_version = (mc_version or "").strip()
    if loader == "fabric":
        url = f"{FABRIC_META}/versions/loader/{mc_version}" if mc_version else f"{FABRIC_META}/versions/loader"
        data = _http_json(url)
        if not isinstance(data, list):
            return []
        out: list[str] = []
        for row in data:
            if isinstance(row, dict):
                inner = row.get("loader") if isinstance(row.get("loader"), dict) else row
                ver = str(inner.get("version") or "")
                if ver:
                    out.append(ver)
            elif isinstance(row, str):
                out.append(row)
        return out
    if loader == "quilt":
        url = f"{QUILT_META}/versions/loader/{mc_version}" if mc_version else f"{QUILT_META}/versions/loader"
        data = _http_json(url)
        if not isinstance(data, list):
            return []
        out: list[str] = []
        for row in data:
            if isinstance(row, dict):
                inner = row.get("loader") if isinstance(row.get("loader"), dict) else row
                ver = str(inner.get("version") or "")
                if ver:
                    out.append(ver)
        return out
    if loader == "forge":
        xml = _http_text(
            "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
        )
        versions = _xml_versions(xml)
        if mc_version:
            prefix = f"{mc_version}-"
            versions = [v[len(prefix) :] if v.startswith(prefix) else v for v in versions if v.startswith(prefix)]
        return versions[:80]
    xml = _http_text(
        "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
    )
    versions = _xml_versions(xml)
    if mc_version:
        # NeoForge：21.1.x 对应 1.21.1
        parts = mc_version.split(".")
        if len(parts) >= 3 and parts[0] == "1":
            prefix = f"{parts[1]}.{parts[2]}."
            versions = [v for v in versions if v.startswith(prefix)]
    return versions[:80]


def resolve_latest_loader(loader: str, mc_version: str) -> str:
    versions = list_loader_versions(loader, mc_version)
    return versions[0] if versions else ""


def _creds(db: Session) -> tuple[str, str, str]:
    base, token, uuid = get_pelican_credentials(db)
    if not pelican.pelican_configured(base, token, uuid):
        raise MinecraftProfileError(
            "未配置 Pelican（请在集成密钥填写 Panel 地址、Client Token、Server UUID）",
            status_code=400,
        )
    return base, token, uuid


_STAGE_KEY = "_committed_stages"
_STAGE_FIELDS = {
    "bootstrap": ("mc_version", "loader", "loader_version", "egg_id", "startup"),
    "mods": ("mods",),
    "config": ("overrides",),
}
READY_TIMEOUT_SEC = 240.0
_CONFIG_EXTS = (".toml", ".json", ".properties", ".cfg", ".yml", ".yaml", ".txt")
_CONFIG_SKIP_DIRS = {
    "world",
    "world_nether",
    "world_the_end",
    "libraries",
    "mods",
    "versions",
    "logs",
    "crash-reports",
    "zhange",
    ".cache",
    "libraries",
}


def wait_offline(base: str, token: str, uuid: str, *, timeout: float = 45.0) -> str:
    deadline = time.monotonic() + timeout
    last = "unknown"
    while time.monotonic() < deadline:
        try:
            res = pelican.get_resources(base, token, uuid)
            last = pelican.power_state_from_resources(res)
        except pelican.PelicanError:
            last = "unknown"
        if last in {"offline", "stopped"}:
            return last
        time.sleep(1.5)
    return last


def wait_ready(
    base: str,
    token: str,
    uuid: str,
    *,
    host: str,
    port: int,
    timeout: float = READY_TIMEOUT_SEC,
) -> dict[str, Any]:
    """等 Pelican 进入 running，再尽量 ping 通公开地址。"""
    deadline = time.monotonic() + timeout
    last = "unknown"
    ping_online = False
    ping_message = ""
    while time.monotonic() < deadline:
        try:
            res = pelican.get_resources(base, token, uuid)
            last = pelican.power_state_from_resources(res)
        except pelican.PelicanError as exc:
            last = "unknown"
            ping_message = exc.message
        if last == "running":
            if host:
                try:
                    status_svc.ping_server(host, int(port or 25565), timeout=2.5)
                    ping_online = True
                    ping_message = ""
                    return {
                        "power_state": last,
                        "ping_online": True,
                        "ready": True,
                        "message": "",
                    }
                except (status_svc.MinecraftPingError, OSError) as exc:
                    ping_message = str(getattr(exc, "message", None) or exc)
            else:
                return {
                    "power_state": last,
                    "ping_online": False,
                    "ready": True,
                    "message": "进程已运行，但未设置公开地址，跳过列表 ping",
                }
        time.sleep(3.0)
    ready = last == "running"
    message = ping_message or (
        f"等待超时，当前电源状态 {last}" + ("，列表 ping 尚未通" if ready and host else "")
    )
    return {
        "power_state": last,
        "ping_online": ping_online,
        "ready": ready,
        "message": message,
    }


def committed_stages(row: MinecraftServerProfile) -> set[str]:
    applied = applied_snapshot(row)
    if not applied:
        return set()
    raw = applied.get(_STAGE_KEY)
    if isinstance(raw, list) and raw:
        return {str(item) for item in raw if item}
    return {"bootstrap", "mods", "config"}


def playbook_stages(row: MinecraftServerProfile) -> dict[str, str]:
    applied = applied_snapshot(row)
    desired = _strip_snapshot_meta(desired_snapshot(row))
    committed = committed_stages(row)
    out: dict[str, str] = {}
    applied_n = _strip_snapshot_meta(applied) if applied else None
    for stage, keys in _STAGE_FIELDS.items():
        if applied_n is None:
            out[stage] = "pending"
            continue
        a = {key: applied_n.get(key) for key in keys}
        d = {key: desired.get(key) for key in keys}
        if stage not in committed:
            out[stage] = "pending"
        elif _canonical_snapshot(a) == _canonical_snapshot(d):
            out[stage] = "applied"
        else:
            out[stage] = "dirty"
    return out


def _strip_snapshot_meta(snap: dict[str, Any]) -> dict[str, Any]:
    data = _without_legacy_snapshot_keys(snap)
    data.pop(_STAGE_KEY, None)
    data.setdefault("egg_id", 0)
    data.setdefault("startup", "")
    return data


def _mark_stage(row: MinecraftServerProfile, stage: str) -> None:
    desired = desired_snapshot(row)
    previous = applied_snapshot(row)
    snap = dict(previous or {})
    for key in _STAGE_FIELDS[stage]:
        snap[key] = desired[key]
    for key, value in desired.items():
        if key in snap:
            continue
        if key == "mods":
            snap[key] = []
        elif key == "overrides":
            snap[key] = {}
        else:
            snap[key] = value
    raw = snap.get(_STAGE_KEY)
    if isinstance(raw, list) and raw:
        stages = [str(item) for item in raw if item]
    elif previous:
        stages = ["bootstrap", "mods", "config"]
    else:
        stages = []
    if stage not in stages:
        stages.append(stage)
    snap = _without_legacy_snapshot_keys(snap)
    snap[_STAGE_KEY] = stages
    row.applied_json = snap


def _power_state(base: str, token: str, uuid: str) -> str:
    try:
        resources = pelican.get_resources(base, token, uuid)
        return pelican.power_state_from_resources(resources)
    except pelican.PelicanError as exc:
        raise MinecraftProfileError(exc.message, status_code=exc.status_code or 502) from exc


def _stop_if_running(base: str, token: str, uuid: str, notes: list[str]) -> None:
    state = _power_state(base, token, uuid)
    if state in {"running", "starting"}:
        pelican.send_power(base, token, uuid, "stop")
        notes.append("已停止正在运行的服")
        wait_offline(base, token, uuid)


def _ensure_server_dirs(base: str, token: str, uuid: str) -> None:
    pelican.create_folder(base, token, uuid, root="/", name="zhange")
    pelican.create_folder(base, token, uuid, root="/", name="mods")
    pelican.create_folder(base, token, uuid, root="/", name="config")


def _write_boot_pack(
    base: str,
    token: str,
    uuid: str,
    row: MinecraftServerProfile,
    *,
    mods: list[dict[str, Any]],
    overrides: dict[str, str],
    notes: list[str],
    write_overrides: bool,
) -> None:
    _ensure_server_dirs(base, token, uuid)
    mrpack = pack.build_mrpack_bytes(
        mc_version=row.mc_version,
        loader=row.loader,
        loader_version=row.loader_version,
        mods=mods,
        overrides=overrides if write_overrides else {},
    )
    pelican.write_file(base, token, uuid, "zhange/pack.mrpack", mrpack)
    pelican.write_file(base, token, uuid, "zhange/boot.sh", pack.BOOT_SH)
    pelican.write_file(
        base,
        token,
        uuid,
        "zhange/desired.json",
        pack.desired_json(
            mc_version=row.mc_version,
            loader=row.loader,
            loader_version=row.loader_version,
            mods=mods,
        ),
    )
    try:
        pelican.chmod_file(base, token, uuid, "zhange/boot.sh", "0755")
    except pelican.PelicanError as exc:
        notes.append(f"chmod boot.sh：{exc.message}")
    if write_overrides:
        for rel, content in overrides.items():
            pelican.write_file(base, token, uuid, rel, content)
    try:
        pelican.pull_file(
            base,
            token,
            uuid,
            url=pack.MRPACK_INSTALL_URL,
            directory="/zhange",
            filename="mrpack-install",
        )
        try:
            pelican.chmod_file(base, token, uuid, "zhange/mrpack-install", "0755")
        except pelican.PelicanError:
            pass
    except pelican.PelicanError as exc:
        notes.append(f"拉取 mrpack-install 失败：{exc.message}")


def _sync_mod_jars(
    base: str,
    token: str,
    uuid: str,
    mods: list[dict[str, Any]],
    notes: list[str],
) -> dict[str, int]:
    wanted: list[tuple[str, str]] = []
    for mod in mods:
        filename = str(mod.get("filename") or "")
        url = str(mod.get("download_url") or "")
        if filename and url:
            wanted.append((filename, url))
    wanted_names = {name for name, _ in wanted}
    existing_names: set[str] = set()
    try:
        existing = pelican.list_files(base, token, uuid, "/mods")
        existing_names = {
            str(row.get("name") or "")
            for row in existing
            if row.get("is_file") and str(row.get("name") or "").endswith(".jar")
        }
        existing_names.discard("")
    except pelican.PelicanError as exc:
        notes.append(f"读取 /mods：{exc.message}")
    skipped = 0
    pulled = 0
    for filename, url in wanted:
        if filename in existing_names:
            skipped += 1
            continue
        try:
            pelican.pull_file(
                base,
                token,
                uuid,
                url=url,
                directory="/mods",
                filename=filename,
            )
            pulled += 1
        except pelican.PelicanError as exc:
            notes.append(f"拉取 {filename} 失败：{exc.message}")
    removed = 0
    extra = sorted(name for name in existing_names if name not in wanted_names)
    if extra:
        try:
            pelican.delete_files(base, token, uuid, root="/mods", files=extra)
            removed = len(extra)
            notes.append(f"已移除不在档案中的模组 {removed} 个")
        except pelican.PelicanError as exc:
            notes.append(f"清理 extras：{exc.message}")
    if skipped:
        notes.append(f"已存在、跳过下载 {skipped} 个")
    if pulled:
        notes.append(f"新下载 {pulled} 个模组")
    return {"pulled": pulled, "skipped": skipped, "removed": removed}


def _boot_in_startup(base: str, token: str, uuid: str, notes: list[str]) -> bool:
    try:
        startup = pelican.get_startup(base, token, uuid)
        cmd = pelican.startup_command(startup)
        wrapped = "zhange/boot.sh" in cmd
        if cmd and not wrapped:
            notes.append("启动命令同步后仍未包含 zhange/boot.sh")
        return wrapped
    except pelican.PelicanError as exc:
        notes.append(f"读取启动命令：{exc.message}")
        return False


def _apply_egg_and_notes(
    db: Session,
    row: MinecraftServerProfile,
    base: str,
    token: str,
    uuid: str,
    notes: list[str],
    *,
    startup: str = "",
    egg_id: int | None = None,
) -> dict[str, Any]:
    from app.services.minecraft import eggs as eggs

    try:
        synced = eggs.sync_server_egg(
            db,
            loader=row.loader,
            mc_version=row.mc_version,
            loader_version=row.loader_version or "",
            startup=startup,
            egg_id=egg_id,
        )
    except eggs.EggSyncError as exc:
        raise MinecraftProfileError(exc.message, status_code=exc.status_code) from exc
    except pelican.PelicanError as exc:
        raise MinecraftProfileError(exc.message, status_code=exc.status_code or 502) from exc
    if synced.get("message"):
        notes.append(str(synced["message"]))
    current = synced.get("current") if isinstance(synced.get("current"), dict) else {}
    recommended = synced.get("recommended") if isinstance(synced.get("recommended"), dict) else {}
    inferred = str(current.get("inferred_loader") or "")
    rec_name = str(current.get("egg_name") or recommended.get("name") or "")
    match = bool(inferred and inferred == row.loader)
    return {
        "egg_match": match,
        "egg_name": rec_name,
        "inferred_loader": inferred,
        "boot_in_startup": bool(synced.get("boot_in_startup")),
    }


def _start_and_wait(
    db: Session,
    base: str,
    token: str,
    uuid: str,
    notes: list[str],
    *,
    restart: bool = False,
) -> dict[str, Any]:
    pelican.send_power(base, token, uuid, "restart" if restart else "start")
    notes.append("已请求重启" if restart else "已请求启动")
    host, port = get_minecraft_public_address(db)
    ready = wait_ready(
        base,
        token,
        uuid,
        host=host,
        port=port,
    )
    if ready.get("message"):
        notes.append(str(ready["message"]))
    elif ready.get("ping_online"):
        notes.append("列表 ping 已通，服已就绪")
    elif ready.get("ready"):
        notes.append("进程已运行")
    return ready


def _finish_stage(
    db: Session,
    row: MinecraftServerProfile,
    notes: list[str],
    *,
    stage: str,
    boot_in_startup: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message = "；".join(notes) if notes else "ok"
    row.last_applied_at = now_naive()
    row.last_apply_message = message[:4000]
    _mark_stage(row, stage)
    db.commit()
    invalidate_live_public_facts()
    result = {
        "ok": True,
        "message": message,
        "stage": stage,
        "boot_in_startup": boot_in_startup,
        "mod_count": len(_mods_list(row)),
        "startup_hint": profile_to_dict(row, pelican_ok=True)["startup_hint"],
        "stages": playbook_stages(row),
    }
    if extra:
        result.update({key: value for key, value in extra.items() if key != "message"})
    return result


def _pin_loader_version(db: Session, row: MinecraftServerProfile) -> MinecraftServerProfile:
    if not row.loader_version:
        row.loader_version = resolve_latest_loader(row.loader, row.mc_version)
        db.commit()
        db.refresh(row)
    return row


def bootstrap_profile(
    db: Session,
    *,
    startup: str = "",
    egg_id: int | None = None,
) -> dict[str, Any]:
    row = _pin_loader_version(db, get_or_create_profile(db))
    base, token, uuid = _creds(db)
    notes: list[str] = []
    _stop_if_running(base, token, uuid, notes)
    _write_boot_pack(
        base,
        token,
        uuid,
        row,
        mods=[],
        overrides={},
        notes=notes,
        write_overrides=False,
    )
    egg = _apply_egg_and_notes(
        db,
        row,
        base,
        token,
        uuid,
        notes,
        startup=(startup or "").strip() or str(getattr(row, "startup", "") or ""),
        egg_id=int(egg_id or 0) or int(getattr(row, "egg_id", 0) or 0) or None,
    )
    boot_in_startup = bool(egg.get("boot_in_startup")) or _boot_in_startup(
        base, token, uuid, notes
    )
    ready = _start_and_wait(db, base, token, uuid, notes)
    return _finish_stage(
        db,
        row,
        notes,
        stage="bootstrap",
        boot_in_startup=boot_in_startup,
        extra={**egg, **ready, "pulled": 0, "skipped": 0, "removed": 0},
    )


def sync_profile_mods(db: Session) -> dict[str, Any]:
    row = _pin_loader_version(db, get_or_create_profile(db))
    base, token, uuid = _creds(db)
    mods = _mods_list(row)
    notes: list[str] = []
    _stop_if_running(base, token, uuid, notes)
    _write_boot_pack(
        base,
        token,
        uuid,
        row,
        mods=mods,
        overrides=_overrides_map(row),
        notes=notes,
        write_overrides=False,
    )
    counts = _sync_mod_jars(base, token, uuid, mods, notes)
    boot_in_startup = _boot_in_startup(base, token, uuid, notes)
    ready = _start_and_wait(db, base, token, uuid, notes)
    return _finish_stage(
        db,
        row,
        notes,
        stage="mods",
        boot_in_startup=boot_in_startup,
        extra={**counts, **ready},
    )


def apply_profile_config(db: Session) -> dict[str, Any]:
    row = _pin_loader_version(db, get_or_create_profile(db))
    base, token, uuid = _creds(db)
    overrides = _overrides_map(row)
    notes: list[str] = []
    _stop_if_running(base, token, uuid, notes)
    _ensure_server_dirs(base, token, uuid)
    for rel, content in overrides.items():
        pelican.write_file(base, token, uuid, rel, content)
    if overrides:
        notes.append(f"已写入配置文件 {len(overrides)} 个")
    else:
        notes.append("没有要覆盖的配置，仅重启核对状态")
    boot_in_startup = _boot_in_startup(base, token, uuid, notes)
    ready = _start_and_wait(db, base, token, uuid, notes, restart=False)
    return _finish_stage(
        db,
        row,
        notes,
        stage="config",
        boot_in_startup=boot_in_startup,
        extra={**ready, "pulled": 0, "skipped": 0, "removed": 0},
    )


def list_live_configs(db: Session) -> list[dict[str, Any]]:
    base, token, uuid = _creds(db)
    found: list[dict[str, Any]] = []

    def add(path: str, entry: dict[str, Any], kind: str) -> None:
        found.append(
            {
                "path": path,
                "size": int(entry.get("size") or 0),
                "modified_at": entry.get("modified_at"),
                "kind": kind,
            }
        )

    try:
        root = pelican.list_files(base, token, uuid, "/")
    except pelican.PelicanError as exc:
        raise MinecraftProfileError(exc.message, status_code=exc.status_code or 502) from exc
    has_config_dir = False
    for row in root:
        name = str(row.get("name") or "")
        if row.get("is_file") and name == "server.properties":
            add("/server.properties", row, "server")
        if not row.get("is_file") and name == "config":
            has_config_dir = True
    if has_config_dir:
        try:
            top = pelican.list_files(base, token, uuid, "/config")
        except pelican.PelicanError:
            top = []
        for entry in top:
            name = str(entry.get("name") or "")
            if not name:
                continue
            if entry.get("is_file"):
                lower = name.lower()
                if any(lower.endswith(ext) for ext in _CONFIG_EXTS):
                    add(f"/config/{name}", entry, "mod")
                continue
            if name in _CONFIG_SKIP_DIRS:
                continue
            try:
                nested = pelican.list_files(base, token, uuid, f"/config/{name}")
            except pelican.PelicanError:
                continue
            for child in nested:
                child_name = str(child.get("name") or "")
                if not child.get("is_file") or not child_name:
                    continue
                lower = child_name.lower()
                if any(lower.endswith(ext) for ext in _CONFIG_EXTS):
                    add(f"/config/{name}/{child_name}", child, "mod")
            if len(found) >= 80:
                break
    return found[:80]


def apply_profile(db: Session) -> dict[str, Any]:
    """一次性跑完三步（兼容旧入口）。"""
    row = _pin_loader_version(db, get_or_create_profile(db))
    base, token, uuid = _creds(db)
    mods = _mods_list(row)
    overrides = _overrides_map(row)
    notes: list[str] = []
    _stop_if_running(base, token, uuid, notes)
    _write_boot_pack(
        base,
        token,
        uuid,
        row,
        mods=mods,
        overrides=overrides,
        notes=notes,
        write_overrides=True,
    )
    egg = _apply_egg_and_notes(db, row, base, token, uuid, notes)
    counts = _sync_mod_jars(base, token, uuid, mods, notes)
    boot_in_startup = _boot_in_startup(base, token, uuid, notes)
    ready = _start_and_wait(db, base, token, uuid, notes)
    message = "；".join(notes) if notes else "ok"
    row.last_applied_at = now_naive()
    row.last_apply_message = message[:4000]
    row.applied_json = {**desired_snapshot(row), _STAGE_KEY: ["bootstrap", "mods", "config"]}
    db.commit()
    invalidate_live_public_facts()
    return {
        "ok": True,
        "message": message,
        "stage": "all",
        "boot_in_startup": boot_in_startup,
        "mod_count": len(mods),
        "startup_hint": profile_to_dict(row, pelican_ok=True)["startup_hint"],
        "stages": playbook_stages(row),
        **egg,
        **counts,
        "power_state": ready.get("power_state") or "",
        "ping_online": bool(ready.get("ping_online")),
        "ready": bool(ready.get("ready")),
    }


def collect_status(db: Session) -> dict[str, Any]:
    row = get_or_create_profile(db)
    base, token, uuid = get_pelican_credentials(db)
    pelican_ok = pelican.pelican_configured(base, token, uuid)
    power_state = None
    pelican_message = ""
    if pelican_ok:
        try:
            res = pelican.get_resources(base, token, uuid)
            power_state = pelican.power_state_from_resources(res)
        except pelican.PelicanError as exc:
            pelican_message = exc.message
            power_state = "unknown"

    host, port = get_minecraft_public_address(db)
    ping_online = False
    latency_ms = None
    motd = ""
    motd_raw = ""
    favicon = ""
    version_name = ""
    players_online = 0
    players_max = 0
    players: list[dict[str, str]] = []
    ping_message = ""
    if host:
        started = time.perf_counter()
        try:
            parsed = status_svc.ping_server(host, port)
            ping_online = True
            latency_ms = int((time.perf_counter() - started) * 1000)
            motd = str(parsed.get("motd") or "")
            motd_raw = str(parsed.get("motd_raw") or "")
            favicon = str(parsed.get("favicon") or "")
            version_name = str(parsed.get("version_name") or "")
            players_online = int(parsed.get("players_online") or 0)
            players_max = int(parsed.get("players_max") or 0)
            players = list(parsed.get("players") or [])
        except status_svc.MinecraftPingError as exc:
            ping_message = exc.message
        except OSError as exc:
            ping_message = str(exc)
    else:
        ping_message = "未设置公开地址"

    address = f"{host}:{port}" if host else ""
    message = pelican_message or ping_message
    applied = public_applied_view(row)
    live: dict[str, Any] = {"properties": {}, "mods": None, "whitelist": [], "known": []}
    if pelican_ok:
        live = load_live_public_facts(base, token, uuid)
    applied_props = (applied or {}).get("properties") if isinstance(applied, dict) else {}
    applied_mods = (applied or {}).get("mods") if isinstance(applied, dict) else []
    if not isinstance(applied_props, dict):
        applied_props = {}
    if not isinstance(applied_mods, list):
        applied_mods = []
    properties = dict(applied_props)
    live_props = live.get("properties") if isinstance(live.get("properties"), dict) else {}
    properties.update(live_props)
    live_mods = live.get("mods")
    mods = merge_overview_mods(
        live_mods if isinstance(live_mods, list) else None,
        [item for item in applied_mods if isinstance(item, dict)],
    )
    mods = catalog.enrich_overview_mods(mods)
    raw_whitelist = live.get("whitelist") if isinstance(live.get("whitelist"), list) else []
    whitelist: list[dict[str, str]] = []
    for item in raw_whitelist:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        uid = str(item.get("id") or "").strip()
        if name or uid:
            whitelist.append({"name": name or uid, "id": uid})
    known = live.get("known") if isinstance(live.get("known"), list) else []
    roster = merge_roster(players, known if isinstance(known, list) else [], whitelist)
    known_players: list[dict[str, str]] = []
    for item in [*whitelist, *(known if isinstance(known, list) else [])]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        uid = str(item.get("id") or "").strip()
        if name or uid:
            known_players.append({"name": name or uid, "id": uid})
    try:
        from app.services.minecraft import presence as presence_svc

        presence_svc.record_snapshot(
            db,
            online=players,
            known=known_players,
            players_online=players_online,
            reachable=ping_online,
        )
    except Exception:
        logger.exception("minecraft presence sample from status failed")
    rcon_host, _rcon_port, rcon_password = get_minecraft_rcon_credentials(db)
    rcon_connected = None
    if rcon_host and rcon_password:
        from app.services.minecraft.rcon import session_connected

        rcon_connected = session_connected()
    return {
        "pelican_configured": pelican_ok,
        "power_state": power_state,
        "ping_online": ping_online,
        "rcon_connected": rcon_connected,
        "latency_ms": latency_ms,
        "motd": motd,
        "motd_raw": motd_raw,
        "favicon": favicon,
        "version_name": version_name,
        "players_online": players_online,
        "players_max": players_max,
        "players": players,
        "public_host": host,
        "public_port": port,
        "address": address,
        "message": message,
        "playbook_dirty": is_playbook_dirty(row),
        "applied": applied,
        "properties": properties,
        "mods": mods,
        "whitelist": whitelist,
        "roster": roster,
    }


def check_mod_updates(db: Session) -> list[dict[str, Any]]:
    row = get_or_create_profile(db)
    out: list[dict[str, Any]] = []
    for mod in _mods_list(row):
        pid = str(mod.get("project_id") or "")
        if not pid:
            continue
        latest = modrinth.latest_pin(
            pid, loader=row.loader, mc_version=row.mc_version
        )
        if not latest:
            continue
        if latest.get("version_id") == mod.get("version_id"):
            continue
        out.append({"current": mod, "latest": latest})
    return out
