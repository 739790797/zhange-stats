"""One-shot: copy root .env and system_configs rows into config/*.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret
from app.core.file_config import (
    parse_dotenv,
    read_json,
    write_json,
)
from app.core.paths import resolve_install_dir
from app.models.system_config import SystemConfig

logger = logging.getLogger("zhange.config")

_SECRET_KEYS = (
    "steam_api_key",
    "qq_app_key",
    "github_token",
    "pelican_client_token",
    "pelican_application_token",
    "minecraft_rcon_password",
)

_APP_STR_KEYS = (
    "APP_ENV",
    "REDIS_URL",
    "CORS_ORIGINS",
    "CORS_ORIGIN_REGEX",
    "PUBLIC_BACKEND_URL",
    "PUBLIC_FRONTEND_URL",
    "APP_LOG_LEVEL",
    "HF_ENDPOINT",
    "DATA_DIR",
    "UPLOAD_DIR",
    "STATIC_DIR",
    "APP_INSTALL_DIR",
)

_APP_BOOL_KEYS = (
    "CSP_ENFORCE",
    "TRUST_X_FORWARDED_FOR",
    "ALLOW_EMAIL_CODE_LOG",
    "ALLOW_IN_APP_UPDATE",
)

_ENV_TO_INTEGRATION = (
    ("STEAM_API_KEY", "steam_api_key"),
    ("QQ_APP_ID", "qq_app_id"),
    ("QQ_APP_KEY", "qq_app_key"),
    ("UPDATE_GITHUB_TOKEN", "github_token"),
)


def _row_json(db: Session, key: str) -> dict[str, Any] | None:
    row = db.get(SystemConfig, key)
    if row is None:
        return None
    try:
        data = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _legacy_env() -> dict[str, str]:
    return parse_dotenv(resolve_install_dir() / ".env")


def _parse_bool(raw: str) -> bool | None:
    text = (raw or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return None


def _app_from_env(env: dict[str, str]) -> dict[str, Any]:
    app: dict[str, Any] = {}
    for key in _APP_STR_KEYS:
        if env.get(key):
            app[key] = env[key]
    for key in _APP_BOOL_KEYS:
        parsed = _parse_bool(env.get(key) or "")
        if parsed is not None:
            app[key] = parsed
    return app


def _email_from_env(env: dict[str, str]) -> dict[str, Any]:
    host = (env.get("SMTP_HOST") or "").strip()
    mail_from = (env.get("SMTP_FROM") or "").strip()
    user = (env.get("SMTP_USER") or "").strip()
    password = env.get("SMTP_PASSWORD") or ""
    if not any((host, mail_from, user, password)):
        return {}
    use_ssl = _parse_bool(env.get("SMTP_USE_SSL") or "true")
    starttls = _parse_bool(env.get("SMTP_STARTTLS") or "false")
    if use_ssl is None:
        use_ssl = True
    if starttls is None:
        starttls = False
    if use_ssl:
        encryption = "SSL"
    elif starttls:
        encryption = "STARTTLS"
    else:
        encryption = "NONE"
    try:
        port = int(env.get("SMTP_PORT") or 465)
    except (TypeError, ValueError):
        port = 465
    try:
        expire = int(env.get("EMAIL_CODE_EXPIRE_MINUTES") or 15)
    except (TypeError, ValueError):
        expire = 15
    return {
        "enabled": bool(host and (mail_from or user)),
        "smtp_host": host,
        "smtp_port": port,
        "smtp_user": user,
        "smtp_password": password,
        "smtp_from": mail_from,
        "display_name": "",
        "encryption": encryption,
        "code_expire_minutes": max(1, expire),
    }


def _integrations_from_env(env: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for env_key, json_key in _ENV_TO_INTEGRATION:
        value = (env.get(env_key) or "").strip()
        if value:
            out[json_key] = value
    return out


def _auth_from_env(env: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    expire = (env.get("ACCESS_TOKEN_EXPIRE_MINUTES") or "").strip()
    if expire:
        try:
            out["access_token_expire_minutes"] = int(expire)
        except (TypeError, ValueError):
            pass
    reject = _parse_bool(env.get("REJECT_WEAK_ADMIN_PASSWORD") or "")
    if reject is not None:
        out["reject_weak_admin_password"] = reject
    enforce = _parse_bool(env.get("ENFORCE_SINGLE_ADMIN") or "")
    if enforce is not None:
        out["enforce_single_admin"] = enforce
    icp = (env.get("ICP_BEIAN_NO") or "").strip()
    if icp:
        out["icp_beian_no"] = icp
    return out


def _decrypt_stored_secrets(stored: dict[str, Any]) -> None:
    for key in _SECRET_KEYS:
        if stored.get(key):
            stored[key] = decrypt_secret(str(stored[key])).strip()
    pwd = stored.get("smtp_password")
    if pwd:
        stored["smtp_password"] = decrypt_secret(str(pwd))


def import_legacy_dotenv() -> None:
    if read_json("database") and read_json("app"):
        return
    env = _legacy_env()
    if not env:
        return
    if not read_json("database"):
        url = (env.get("DATABASE_URL") or "").strip()
        if url:
            engine = "sqlite" if url.startswith("sqlite") else "mysql"
            payload: dict[str, Any] = {"engine": engine, "url": url}
            write_json("database", payload)
            logger.info("imported DATABASE_URL from .env into config/database.json")
    if not read_json("app"):
        app = _app_from_env(env)
        if app:
            write_json("app", app)
            logger.info("imported runtime keys from .env into config/app.json")


def import_legacy_system_configs(db: Session) -> None:
    env = _legacy_env()

    if not read_json("email"):
        merged = _email_from_env(env)
        stored = _row_json(db, "email_smtp")
        if stored:
            _decrypt_stored_secrets(stored)
            merged.update(stored)
        if merged:
            write_json("email", merged)
            logger.info("imported email into config/email.json")

    if not read_json("integrations"):
        merged = _integrations_from_env(env)
        stored = _row_json(db, "integrations")
        if stored:
            _decrypt_stored_secrets(stored)
            merged.update(stored)
        if merged:
            write_json("integrations", merged)
            logger.info("imported integrations into config/integrations.json")

    if not read_json("auth"):
        auth = _auth_from_env(env)
        stored_auth = _row_json(db, "auth_session") or {}
        site = _row_json(db, "site") or {}
        auth.update(stored_auth)
        if site.get("icp_beian_no") is not None:
            auth["icp_beian_no"] = site.get("icp_beian_no")
        if auth:
            write_json("auth", auth)
            logger.info("imported auth_session/site into config/auth.json")

    if not read_json("ocr"):
        stored = _row_json(db, "ocr")
        if stored:
            write_json("ocr", stored)
            logger.info("imported ocr into config/ocr.json")

    jobs = read_json("jobs") or {}
    changed = False
    if "scheduler" not in jobs:
        sched = _row_json(db, "scheduler_jobs")
        if sched:
            jobs["scheduler"] = sched
            changed = True
    if "features" not in jobs:
        feat = _row_json(db, "platform_features")
        if feat:
            flags = feat.get("features") if isinstance(feat.get("features"), dict) else feat
            if isinstance(flags, dict):
                jobs["features"] = flags
                changed = True
    if changed:
        write_json("jobs", jobs)
        logger.info("imported scheduler/platform_features into config/jobs.json")


def default_sqlite_database_json(path: Path) -> dict[str, Any]:
    return {"engine": "sqlite", "path": str(path)}
