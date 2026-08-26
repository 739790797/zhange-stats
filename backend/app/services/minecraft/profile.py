"""单行 Minecraft 档案：服况、已应用快照、公开事实缓存。"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.models.minecraft import PROFILE_ROW_ID, MinecraftServerProfile
from app.services.minecraft import mod_catalog as catalog
from app.services.minecraft import pack as pack
from app.services.minecraft import status as status_svc
from app.services.minecraft import pelican as pelican
from app.services.integrations_config import (
    get_minecraft_public_address,
    get_minecraft_rcon_credentials,
    get_pelican_credentials,
)

logger = logging.getLogger(__name__)


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


def applied_snapshot(row: MinecraftServerProfile) -> dict[str, Any] | None:
    raw = getattr(row, "applied_json", None)
    if not isinstance(raw, dict) or not raw:
        return None
    return raw


def seed_applied_if_missing(row: MinecraftServerProfile) -> bool:
    """旧行只有 last_applied_at、没有快照时，用当前档案补一份。"""
    if applied_snapshot(row) is not None or row.last_applied_at is None:
        return False
    row.applied_json = desired_snapshot(row)
    return True


def _view_from_parts(
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


def view_from_snapshot(snap: dict[str, Any] | None) -> dict[str, Any] | None:
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
    return _view_from_parts(
        mc_version=str(snap.get("mc_version") or ""),
        loader=str(snap.get("loader") or ""),
        loader_version=str(snap.get("loader_version") or ""),
        egg_id=int(snap.get("egg_id") or 0),
        startup=str(snap.get("startup") or ""),
        mods=mods,
        overrides=overrides,
    )


def public_applied_view(row: MinecraftServerProfile) -> dict[str, Any] | None:
    snap = view_from_snapshot(applied_snapshot(row))
    if snap is None:
        return None
    applied_at = row.last_applied_at
    mods = []
    for mod in snap.get("mods") or []:
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
    properties = snap.get("properties") if isinstance(snap.get("properties"), dict) else {}
    shown = {
        key: str(properties[key])
        for key in pack.COMMON_PROPERTY_KEYS
        if key in properties and str(properties.get(key) or "").strip()
    }
    return {
        "mc_version": snap["mc_version"],
        "loader": snap["loader"],
        "loader_version": snap["loader_version"],
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
        "applied": applied,
        "properties": properties,
        "mods": mods,
        "whitelist": whitelist,
        "roster": roster,
    }


