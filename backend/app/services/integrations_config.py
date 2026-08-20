"""第三方集成密钥：数据库优先，.env 兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.database import SessionLocal
from app.models.system_config import SystemConfig

INTEGRATIONS_KEY = "integrations"
RCON_DEFAULT_PORT = 25575


def _parse_rcon_port(raw: Any) -> int:
    try:
        port = int(raw or 0)
    except (TypeError, ValueError):
        port = 0
    if 1 <= port <= 65535:
        return port
    return RCON_DEFAULT_PORT


def _env_defaults() -> dict[str, str]:
    s = get_settings()
    return {
        "steam_api_key": (s.STEAM_API_KEY or "").strip(),
        "qq_app_id": (s.QQ_APP_ID or "").strip(),
        "qq_app_key": (s.QQ_APP_KEY or "").strip(),
        "napcat_base_url": (s.NAPCAT_BASE_URL or "").strip(),
        "napcat_token": (s.NAPCAT_TOKEN or "").strip(),
        "github_token": (s.UPDATE_GITHUB_TOKEN or "").strip(),
        "pelican_base_url": "",
        "pelican_client_token": "",
        "pelican_server_uuid": "",
        "minecraft_rcon_host": "",
        "minecraft_rcon_port": "25575",
        "minecraft_rcon_password": "",
    }


def load_integrations(db: Session) -> dict[str, str]:
    base = _env_defaults()
    row = db.query(SystemConfig).filter(SystemConfig.key == INTEGRATIONS_KEY).first()
    if not row:
        return dict(base)
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return dict(base)
    if not isinstance(stored, dict):
        return dict(base)

    merged = dict(base)
    if "qq_app_id" in stored and stored["qq_app_id"] is not None:
        merged["qq_app_id"] = str(stored["qq_app_id"] or "").strip()
    if "napcat_base_url" in stored and stored["napcat_base_url"] is not None:
        merged["napcat_base_url"] = str(stored["napcat_base_url"] or "").strip().rstrip(
            "/"
        )
    if "pelican_base_url" in stored and stored["pelican_base_url"] is not None:
        from app.services.pelican_client import normalize_pelican_base_url

        merged["pelican_base_url"] = normalize_pelican_base_url(
            str(stored["pelican_base_url"] or "")
        )
    if "pelican_server_uuid" in stored and stored["pelican_server_uuid"] is not None:
        merged["pelican_server_uuid"] = str(stored["pelican_server_uuid"] or "").strip()
    if "minecraft_rcon_host" in stored and stored["minecraft_rcon_host"] is not None:
        merged["minecraft_rcon_host"] = str(stored["minecraft_rcon_host"] or "").strip()
    if "minecraft_rcon_port" in stored and stored["minecraft_rcon_port"] is not None:
        merged["minecraft_rcon_port"] = str(stored["minecraft_rcon_port"] or "").strip()

    for secret_key in (
        "steam_api_key",
        "qq_app_key",
        "napcat_token",
        "github_token",
        "pelican_client_token",
        "minecraft_rcon_password",
    ):
        if secret_key not in stored:
            continue
        raw = stored.get(secret_key)
        if raw is None:
            # 显式 null：删除覆盖，回落 env（已在 base）
            continue
        text = str(raw or "").strip()
        if not text:
            # 空串：同样视为未在库中配置 → 回落 env
            continue
        merged[secret_key] = decrypt_secret(text).strip()

    return {
        "steam_api_key": merged.get("steam_api_key") or "",
        "qq_app_id": merged.get("qq_app_id") or "",
        "qq_app_key": merged.get("qq_app_key") or "",
        "napcat_base_url": (merged.get("napcat_base_url") or "").rstrip("/"),
        "napcat_token": merged.get("napcat_token") or "",
        "github_token": merged.get("github_token") or "",
        "pelican_base_url": (merged.get("pelican_base_url") or "").rstrip("/"),
        "pelican_client_token": merged.get("pelican_client_token") or "",
        "pelican_server_uuid": (merged.get("pelican_server_uuid") or "").strip(),
        "minecraft_rcon_host": (merged.get("minecraft_rcon_host") or "").strip(),
        "minecraft_rcon_port": str(
            _parse_rcon_port(merged.get("minecraft_rcon_port"))
        ),
        "minecraft_rcon_password": merged.get("minecraft_rcon_password") or "",
    }


def save_integrations(db: Session, payload: dict[str, Any]) -> dict[str, str]:
    row = db.query(SystemConfig).filter(SystemConfig.key == INTEGRATIONS_KEY).first()
    stored: dict[str, Any] = {}
    if row:
        try:
            parsed = json.loads(row.value or "{}")
            if isinstance(parsed, dict):
                stored = parsed
        except json.JSONDecodeError:
            stored = {}

    # qq_app_id / napcat_base_url：明文，始终可写
    if "qq_app_id" in payload and payload.get("qq_app_id") is not None:
        stored["qq_app_id"] = str(payload.get("qq_app_id") or "").strip()
    if "napcat_base_url" in payload and payload.get("napcat_base_url") is not None:
        from app.services.napcat_client import normalize_napcat_base_url

        stored["napcat_base_url"] = normalize_napcat_base_url(
            str(payload.get("napcat_base_url") or "")
        )
    if "pelican_base_url" in payload and payload.get("pelican_base_url") is not None:
        from app.services.pelican_client import normalize_pelican_base_url

        stored["pelican_base_url"] = normalize_pelican_base_url(
            str(payload.get("pelican_base_url") or "")
        )
    if "pelican_server_uuid" in payload and payload.get("pelican_server_uuid") is not None:
        stored["pelican_server_uuid"] = str(payload.get("pelican_server_uuid") or "").strip()

    if payload.get("clear_steam_api_key"):
        stored.pop("steam_api_key", None)
    else:
        steam_key = payload.get("steam_api_key")
        if steam_key is not None and str(steam_key).strip():
            stored["steam_api_key"] = encrypt_secret(str(steam_key).strip())

    if payload.get("clear_qq_app_key"):
        stored.pop("qq_app_key", None)
    else:
        qq_key = payload.get("qq_app_key")
        if qq_key is not None and str(qq_key).strip():
            stored["qq_app_key"] = encrypt_secret(str(qq_key).strip())

    if payload.get("clear_napcat_token"):
        stored.pop("napcat_token", None)
    else:
        napcat_token = payload.get("napcat_token")
        if napcat_token is not None and str(napcat_token).strip():
            stored["napcat_token"] = encrypt_secret(str(napcat_token).strip())

    if payload.get("clear_github_token"):
        stored.pop("github_token", None)
    else:
        github_token = payload.get("github_token")
        if github_token is not None and str(github_token).strip():
            stored["github_token"] = encrypt_secret(str(github_token).strip())

    if payload.get("clear_pelican_client_token"):
        stored.pop("pelican_client_token", None)
    else:
        pelican_token = payload.get("pelican_client_token")
        if pelican_token is not None and str(pelican_token).strip():
            stored["pelican_client_token"] = encrypt_secret(str(pelican_token).strip())

    if "minecraft_rcon_host" in payload and payload.get("minecraft_rcon_host") is not None:
        stored["minecraft_rcon_host"] = str(payload.get("minecraft_rcon_host") or "").strip()
    if "minecraft_rcon_port" in payload and payload.get("minecraft_rcon_port") is not None:
        stored["minecraft_rcon_port"] = _parse_rcon_port(payload.get("minecraft_rcon_port"))
    if payload.get("clear_minecraft_rcon_password"):
        stored.pop("minecraft_rcon_password", None)
    else:
        rcon_password = payload.get("minecraft_rcon_password")
        if rcon_password is not None and str(rcon_password).strip():
            stored["minecraft_rcon_password"] = encrypt_secret(str(rcon_password).strip())

    raw = json.dumps(stored, ensure_ascii=False)
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=INTEGRATIONS_KEY, value=raw))
    db.commit()
    return load_integrations(db)


def public_integrations(cfg: dict[str, str]) -> dict[str, Any]:
    steam = cfg.get("steam_api_key") or ""
    qq_key = cfg.get("qq_app_key") or ""
    qq_id = cfg.get("qq_app_id") or ""
    napcat_url = cfg.get("napcat_base_url") or ""
    napcat_token = cfg.get("napcat_token") or ""
    github_token = cfg.get("github_token") or ""
    pelican_url = cfg.get("pelican_base_url") or ""
    pelican_token = cfg.get("pelican_client_token") or ""
    pelican_uuid = cfg.get("pelican_server_uuid") or ""
    rcon_host = cfg.get("minecraft_rcon_host") or ""
    rcon_port = _parse_rcon_port(cfg.get("minecraft_rcon_port"))
    rcon_password = cfg.get("minecraft_rcon_password") or ""
    return {
        "steam_api_key": steam,
        "steam_api_key_set": bool(steam),
        "qq_app_id": qq_id,
        "qq_app_key": qq_key,
        "qq_app_key_set": bool(qq_key),
        "qq_configured": bool(qq_id and qq_key),
        "steam_configured": bool(steam),
        "napcat_base_url": napcat_url,
        "napcat_token": napcat_token,
        "napcat_token_set": bool(napcat_token),
        "napcat_configured": bool(napcat_url and napcat_token),
        "github_token": github_token,
        "github_token_set": bool(github_token),
        "github_configured": bool(github_token),
        "pelican_base_url": pelican_url,
        "pelican_client_token": pelican_token,
        "pelican_client_token_set": bool(pelican_token),
        "pelican_server_uuid": pelican_uuid,
        "pelican_configured": bool(pelican_url and pelican_token and pelican_uuid),
        "minecraft_rcon_host": rcon_host,
        "minecraft_rcon_port": rcon_port,
        "minecraft_rcon_password": rcon_password,
        "minecraft_rcon_password_set": bool(rcon_password),
        "minecraft_rcon_configured": bool(rcon_host and rcon_password),
    }


def get_steam_api_key(db: Session | None = None) -> str:
    if db is not None:
        return load_integrations(db).get("steam_api_key") or ""
    session = SessionLocal()
    try:
        return load_integrations(session).get("steam_api_key") or ""
    finally:
        session.close()


def get_qq_credentials(db: Session | None = None) -> tuple[str, str]:
    def _read(session: Session) -> tuple[str, str]:
        cfg = load_integrations(session)
        return cfg.get("qq_app_id") or "", cfg.get("qq_app_key") or ""

    if db is not None:
        return _read(db)
    session = SessionLocal()
    try:
        return _read(session)
    finally:
        session.close()


def get_napcat_credentials(db: Session | None = None) -> tuple[str, str]:
    def _read(session: Session) -> tuple[str, str]:
        cfg = load_integrations(session)
        return cfg.get("napcat_base_url") or "", cfg.get("napcat_token") or ""

    if db is not None:
        return _read(db)
    session = SessionLocal()
    try:
        return _read(session)
    finally:
        session.close()


def get_github_token(db: Session | None = None) -> str:
    if db is not None:
        return load_integrations(db).get("github_token") or ""
    session = SessionLocal()
    try:
        return load_integrations(session).get("github_token") or ""
    finally:
        session.close()


def get_pelican_credentials(db: Session | None = None) -> tuple[str, str, str]:
    def _read(session: Session) -> tuple[str, str, str]:
        cfg = load_integrations(session)
        return (
            cfg.get("pelican_base_url") or "",
            cfg.get("pelican_client_token") or "",
            cfg.get("pelican_server_uuid") or "",
        )

    if db is not None:
        return _read(db)
    session = SessionLocal()
    try:
        return _read(session)
    finally:
        session.close()


def get_minecraft_rcon_credentials(db: Session | None = None) -> tuple[str, int, str]:
    def _read(session: Session) -> tuple[str, int, str]:
        cfg = load_integrations(session)
        return (
            (cfg.get("minecraft_rcon_host") or "").strip(),
            _parse_rcon_port(cfg.get("minecraft_rcon_port")),
            (cfg.get("minecraft_rcon_password") or "").strip(),
        )

    if db is not None:
        return _read(db)
    session = SessionLocal()
    try:
        return _read(session)
    finally:
        session.close()
