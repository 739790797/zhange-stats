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
    read_example,
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

_IMPORT_MARKER_KEY = "legacy_config_imported"

# 同组字段一起迁：组里有一项已不是模板默认值，就当管理员在 config/ 里配过这一组，整组不动，免得拼出新主机配旧端口
_IMPORT_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "email": (
        (
            "enabled",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "smtp_from",
            "display_name",
            "encryption",
        ),
        ("code_expire_minutes",),
    ),
    "integrations": (
        ("steam_api_key",),
        ("qq_app_id", "qq_app_key"),
        ("github_token",),
        (
            "pelican_base_url",
            "pelican_client_token",
            "pelican_application_token",
            "pelican_server_uuid",
        ),
        ("minecraft_rcon_host", "minecraft_rcon_port", "minecraft_rcon_password"),
        ("minecraft_public_host", "minecraft_public_port"),
    ),
    "auth": (
        ("access_token_expire_minutes",),
        ("min_password_length",),
        ("reject_weak_admin_password",),
        ("enforce_single_admin",),
        ("icp_beian_no",),
    ),
    "ocr": (("paddle_profile", "engines", "use_cases"),),
    "jobs": (("scheduler",), ("features",)),
}

_MISSING = object()


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
    """库里空的或解不开的密钥当没配，回落 .env。"""
    for key in (*_SECRET_KEYS, "smtp_password"):
        plain = decrypt_secret(str(stored.get(key) or ""))
        if not plain.strip():
            stored.pop(key, None)
        else:
            stored[key] = plain if key == "smtp_password" else plain.strip()


def _overlay(base: dict[str, Any], stored: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(base)
    out.update({key: value for key, value in (stored or {}).items() if value is not None})
    return out


def _legacy_email(db: Session, env: dict[str, str]) -> dict[str, Any]:
    stored = _row_json(db, "email_smtp")
    if stored:
        _decrypt_stored_secrets(stored)
    return _overlay(_email_from_env(env), stored)


def _legacy_integrations(db: Session, env: dict[str, str]) -> dict[str, Any]:
    stored = _row_json(db, "integrations")
    if stored:
        _decrypt_stored_secrets(stored)
    return _overlay(_integrations_from_env(env), stored)


def _legacy_auth(db: Session, env: dict[str, str]) -> dict[str, Any]:
    stored = _row_json(db, "auth_session") or {}
    out = _overlay(_auth_from_env(env), stored)
    if "reject_weak_admin_password" in stored:
        # 旧版库里 null 是管理员选的「自动」，同样盖过 .env
        out["reject_weak_admin_password"] = stored["reject_weak_admin_password"]
    site = _row_json(db, "site") or {}
    if site.get("icp_beian_no") is not None:
        out["icp_beian_no"] = site["icp_beian_no"]
    return out


def _legacy_jobs(db: Session) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sched = _row_json(db, "scheduler_jobs")
    if sched:
        out["scheduler"] = sched
    feat = _row_json(db, "platform_features")
    if feat:
        flags = feat.get("features") if isinstance(feat.get("features"), dict) else feat
        if flags:
            out["features"] = flags
    return out


def _at_template_default(current: dict[str, Any], template: dict[str, Any], key: str) -> bool:
    value = current.get(key, _MISSING)
    return value is _MISSING or value == template.get(key, _MISSING)


def _merge_legacy(name: str, legacy: dict[str, Any]) -> bool:
    """Copy legacy values into groups still at the template defaults. True when the file changed."""
    template = read_example(name) or {}
    current = read_json(name) or {}
    changed = False
    for group in _IMPORT_GROUPS[name]:
        values = {key: legacy[key] for key in group if legacy.get(key) is not None}
        if not values or not all(_at_template_default(current, template, key) for key in group):
            continue
        for key, value in values.items():
            if current.get(key, _MISSING) != value:
                current[key] = value
                changed = True
    if changed:
        write_json(name, current)
    return changed


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
    """Fill config/*.json from the root .env and legacy system_configs rows, once per database.

    sync_site_config (startup and the lifecycle scripts) creates the files from the templates before
    the database is reachable, so an existing file says nothing about the admin: a group is imported
    while it is still at the template defaults. The marker row stops values the admin clears later
    from coming back on the next start.
    """
    if db.get(SystemConfig, _IMPORT_MARKER_KEY) is not None:
        return
    env = _legacy_env()
    legacy = {
        "email": _legacy_email(db, env),
        "integrations": _legacy_integrations(db, env),
        "auth": _legacy_auth(db, env),
        "ocr": _row_json(db, "ocr") or {},
        "jobs": _legacy_jobs(db),
    }
    imported = [name for name, values in legacy.items() if values and _merge_legacy(name, values)]
    db.add(SystemConfig(key=_IMPORT_MARKER_KEY, value="1"))
    db.commit()
    if imported:
        logger.info("imported legacy .env/system_configs into config/ files=%s", ",".join(imported))


def default_sqlite_database_json(path: Path) -> dict[str, Any]:
    return {"engine": "sqlite", "path": str(path)}
