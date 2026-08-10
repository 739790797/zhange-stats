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


def _env_defaults() -> dict[str, str]:
    s = get_settings()
    return {
        "steam_api_key": (s.STEAM_API_KEY or "").strip(),
        "qq_app_id": (s.QQ_APP_ID or "").strip(),
        "qq_app_key": (s.QQ_APP_KEY or "").strip(),
        "napcat_base_url": (s.NAPCAT_BASE_URL or "").strip(),
        "napcat_token": (s.NAPCAT_TOKEN or "").strip(),
        "github_token": (s.UPDATE_GITHUB_TOKEN or "").strip(),
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

    for secret_key in ("steam_api_key", "qq_app_key", "napcat_token", "github_token"):
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
