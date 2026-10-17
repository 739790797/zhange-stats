"""第三方集成密钥：config/integrations.json。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.file_config import read_json, write_json

INTEGRATIONS_KEY = "integrations"
RCON_DEFAULT_PORT = 25575
GAME_DEFAULT_PORT = 25565

# 只写不读：管理端响应恒为空串 + `<字段>_set`；保存时空/缺省保留原值，`clear_<字段>: true` 才清空。
SECRET_FIELDS = (
    "steam_api_key",
    "qq_app_key",
    "github_token",
    "pelican_client_token",
    "pelican_application_token",
    "minecraft_rcon_password",
    "weblate_token",
)
# 长 token 回末 4 位方便认出是哪把；口令类（RCON）不给。
HINTED_SECRET_FIELDS = frozenset(
    {
        "steam_api_key",
        "qq_app_key",
        "github_token",
        "pelican_client_token",
        "pelican_application_token",
        "weblate_token",
    }
)
HINT_MIN_LENGTH = 16


def _parse_port(raw: Any, *, default: int) -> int:
    try:
        port = int(raw or 0)
    except (TypeError, ValueError):
        port = 0
    if 1 <= port <= 65535:
        return port
    return default


def _parse_rcon_port(raw: Any) -> int:
    return _parse_port(raw, default=RCON_DEFAULT_PORT)


def _parse_game_port(raw: Any) -> int:
    return _parse_port(raw, default=GAME_DEFAULT_PORT)


def _defaults() -> dict[str, str]:
    return {
        "steam_api_key": "",
        "qq_app_id": "",
        "qq_app_key": "",
        "github_token": "",
        "pelican_base_url": "",
        "pelican_client_token": "",
        "pelican_application_token": "",
        "pelican_server_uuid": "",
        "minecraft_rcon_host": "",
        "minecraft_rcon_port": "25575",
        "minecraft_rcon_password": "",
        "minecraft_public_host": "",
        "minecraft_public_port": "25565",
        "weblate_url": "",
        "weblate_project": "",
        "weblate_component": "",
        "weblate_token": "",
    }


def _normalize(stored: dict[str, Any] | None) -> dict[str, str]:
    base = _defaults()
    if not isinstance(stored, dict):
        return base
    merged = dict(base)
    if stored.get("qq_app_id") is not None:
        merged["qq_app_id"] = str(stored.get("qq_app_id") or "").strip()
    if stored.get("pelican_base_url") is not None:
        from app.services.minecraft.pelican import normalize_pelican_base_url

        merged["pelican_base_url"] = normalize_pelican_base_url(
            str(stored.get("pelican_base_url") or "")
        )
    if stored.get("pelican_server_uuid") is not None:
        merged["pelican_server_uuid"] = str(stored.get("pelican_server_uuid") or "").strip()
    if stored.get("minecraft_rcon_host") is not None:
        merged["minecraft_rcon_host"] = str(stored.get("minecraft_rcon_host") or "").strip()
    if stored.get("minecraft_rcon_port") is not None:
        merged["minecraft_rcon_port"] = str(stored.get("minecraft_rcon_port") or "").strip()
    if stored.get("minecraft_public_host") is not None:
        merged["minecraft_public_host"] = str(stored.get("minecraft_public_host") or "").strip()
    if stored.get("minecraft_public_port") is not None:
        merged["minecraft_public_port"] = str(stored.get("minecraft_public_port") or "").strip()
    if stored.get("weblate_url") is not None:
        merged["weblate_url"] = str(stored.get("weblate_url") or "").strip()
    if stored.get("weblate_project") is not None:
        merged["weblate_project"] = str(stored.get("weblate_project") or "").strip()
    if stored.get("weblate_component") is not None:
        merged["weblate_component"] = str(stored.get("weblate_component") or "").strip()
    for key in SECRET_FIELDS:
        if key not in stored or stored.get(key) is None:
            continue
        merged[key] = str(stored.get(key) or "").strip()
    return {
        "steam_api_key": merged.get("steam_api_key") or "",
        "qq_app_id": merged.get("qq_app_id") or "",
        "qq_app_key": merged.get("qq_app_key") or "",
        "github_token": merged.get("github_token") or "",
        "pelican_base_url": (merged.get("pelican_base_url") or "").rstrip("/"),
        "pelican_client_token": merged.get("pelican_client_token") or "",
        "pelican_application_token": merged.get("pelican_application_token") or "",
        "pelican_server_uuid": (merged.get("pelican_server_uuid") or "").strip(),
        "minecraft_rcon_host": (merged.get("minecraft_rcon_host") or "").strip(),
        "minecraft_rcon_port": str(_parse_rcon_port(merged.get("minecraft_rcon_port"))),
        "minecraft_rcon_password": merged.get("minecraft_rcon_password") or "",
        "minecraft_public_host": (merged.get("minecraft_public_host") or "").strip(),
        "minecraft_public_port": str(_parse_game_port(merged.get("minecraft_public_port"))),
        "weblate_url": (merged.get("weblate_url") or "").strip().rstrip("/"),
        "weblate_project": (merged.get("weblate_project") or "").strip(),
        "weblate_component": (merged.get("weblate_component") or "").strip(),
        "weblate_token": merged.get("weblate_token") or "",
    }


_RETIRED_STEAMCMD_KEYS = (
    "steamcmd_username",
    "steamcmd_password",
    "steamcmd_guard_code",
    "steamcmd_path",
    "steamcmd_install_dir",
)


def load_integrations(_db: Session | None = None) -> dict[str, str]:
    raw = read_json("integrations")
    if isinstance(raw, dict) and any(key in raw for key in _RETIRED_STEAMCMD_KEYS):
        raw = {key: value for key, value in raw.items() if key not in _RETIRED_STEAMCMD_KEYS}
        write_json("integrations", raw)
    return _normalize(raw)


def save_integrations(_db: Session | None, payload: dict[str, Any]) -> dict[str, str]:
    stored = dict(load_integrations(_db))
    stored.pop("napcat_base_url", None)
    stored.pop("napcat_token", None)

    if "qq_app_id" in payload and payload.get("qq_app_id") is not None:
        stored["qq_app_id"] = str(payload.get("qq_app_id") or "").strip()
    if "pelican_base_url" in payload and payload.get("pelican_base_url") is not None:
        from app.services.minecraft.pelican import normalize_pelican_base_url

        stored["pelican_base_url"] = normalize_pelican_base_url(
            str(payload.get("pelican_base_url") or "")
        )
    if "pelican_server_uuid" in payload and payload.get("pelican_server_uuid") is not None:
        stored["pelican_server_uuid"] = str(payload.get("pelican_server_uuid") or "").strip()

    for key in SECRET_FIELDS:
        if payload.get(f"clear_{key}"):
            stored[key] = ""
            continue
        value = payload.get(key)
        if value is not None and str(value).strip():
            stored[key] = str(value).strip()

    if "minecraft_rcon_host" in payload and payload.get("minecraft_rcon_host") is not None:
        stored["minecraft_rcon_host"] = str(payload.get("minecraft_rcon_host") or "").strip()
    if "minecraft_rcon_port" in payload and payload.get("minecraft_rcon_port") is not None:
        stored["minecraft_rcon_port"] = str(_parse_rcon_port(payload.get("minecraft_rcon_port")))
    if "minecraft_public_host" in payload and payload.get("minecraft_public_host") is not None:
        stored["minecraft_public_host"] = str(payload.get("minecraft_public_host") or "").strip()
    if "minecraft_public_port" in payload and payload.get("minecraft_public_port") is not None:
        stored["minecraft_public_port"] = str(_parse_game_port(payload.get("minecraft_public_port")))
    if "weblate_url" in payload and payload.get("weblate_url") is not None:
        stored["weblate_url"] = str(payload.get("weblate_url") or "").strip()
    if "weblate_project" in payload and payload.get("weblate_project") is not None:
        stored["weblate_project"] = str(payload.get("weblate_project") or "").strip()
    if "weblate_component" in payload and payload.get("weblate_component") is not None:
        stored["weblate_component"] = str(payload.get("weblate_component") or "").strip()
    rcon_changed = any(
        key in payload
        for key in (
            "minecraft_rcon_host",
            "minecraft_rcon_port",
            "minecraft_rcon_password",
            "clear_minecraft_rcon_password",
        )
    )

    write_json("integrations", _normalize(stored))
    if rcon_changed:
        from app.services.minecraft.rcon import reset_session

        reset_session()
    return load_integrations(_db)


def secret_hint(value: str) -> str:
    text = (value or "").strip()
    return text[-4:] if len(text) >= HINT_MIN_LENGTH else ""


def public_integrations(cfg: dict[str, str]) -> dict[str, Any]:
    values = {key: cfg.get(key) or "" for key in SECRET_FIELDS}
    qq_id = cfg.get("qq_app_id") or ""
    pelican_url = cfg.get("pelican_base_url") or ""
    pelican_uuid = cfg.get("pelican_server_uuid") or ""
    rcon_host = cfg.get("minecraft_rcon_host") or ""
    public_host = cfg.get("minecraft_public_host") or ""
    out: dict[str, Any] = {
        "qq_app_id": qq_id,
        "qq_configured": bool(qq_id and values["qq_app_key"]),
        "steam_configured": bool(values["steam_api_key"]),
        "github_configured": bool(values["github_token"]),
        "pelican_base_url": pelican_url,
        "pelican_server_uuid": pelican_uuid,
        "pelican_configured": bool(pelican_url and values["pelican_client_token"] and pelican_uuid),
        "minecraft_rcon_host": rcon_host,
        "minecraft_rcon_port": _parse_rcon_port(cfg.get("minecraft_rcon_port")),
        "minecraft_rcon_configured": bool(rcon_host and values["minecraft_rcon_password"]),
        "minecraft_public_host": public_host,
        "minecraft_public_port": _parse_game_port(cfg.get("minecraft_public_port")),
        "minecraft_public_configured": bool(public_host),
        "weblate_url": cfg.get("weblate_url") or "",
        "weblate_project": cfg.get("weblate_project") or "",
        "weblate_component": cfg.get("weblate_component") or "",
        "weblate_configured": bool(
            cfg.get("weblate_url")
            and cfg.get("weblate_project")
            and cfg.get("weblate_component")
            and values["weblate_token"]
        ),
    }
    for key, value in values.items():
        out[key] = ""
        out[f"{key}_set"] = bool(value)
        if key in HINTED_SECRET_FIELDS:
            out[f"{key}_hint"] = secret_hint(value)
    return out


def get_steam_api_key(_db: Session | None = None) -> str:
    return load_integrations(_db).get("steam_api_key") or ""


def get_qq_credentials(_db: Session | None = None) -> tuple[str, str]:
    cfg = load_integrations(_db)
    return cfg.get("qq_app_id") or "", cfg.get("qq_app_key") or ""


def get_github_token(_db: Session | None = None) -> str:
    return load_integrations(_db).get("github_token") or ""


def get_pelican_credentials(_db: Session | None = None) -> tuple[str, str, str]:
    cfg = load_integrations(_db)
    return (
        cfg.get("pelican_base_url") or "",
        cfg.get("pelican_client_token") or "",
        cfg.get("pelican_server_uuid") or "",
    )


def get_pelican_application_token(_db: Session | None = None) -> str:
    return load_integrations(_db).get("pelican_application_token") or ""


def get_minecraft_rcon_credentials(_db: Session | None = None) -> tuple[str, int, str]:
    cfg = load_integrations(_db)
    return (
        (cfg.get("minecraft_rcon_host") or "").strip(),
        _parse_rcon_port(cfg.get("minecraft_rcon_port")),
        (cfg.get("minecraft_rcon_password") or "").strip(),
    )


def get_minecraft_public_address(_db: Session | None = None) -> tuple[str, int]:
    cfg = load_integrations(_db)
    return (
        (cfg.get("minecraft_public_host") or "").strip(),
        _parse_game_port(cfg.get("minecraft_public_port")),
    )
