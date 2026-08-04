"""登录会话等认证配置：数据库优先，.env / 代码默认兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.system_config import SystemConfig

AUTH_CONFIG_KEY = "auth_session"
_DEFAULT_EXPIRE_MINUTES = 60 * 24 * 30  # 30 天
_MIN_EXPIRE = 5
_MAX_EXPIRE = 60 * 24 * 365  # 最长 1 年


def _clamp_expire(value: Any, default: int = _DEFAULT_EXPIRE_MINUTES) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return default
    return max(_MIN_EXPIRE, min(_MAX_EXPIRE, minutes))


def _env_defaults() -> dict[str, int]:
    s = get_settings()
    return {
        "access_token_expire_minutes": _clamp_expire(
            s.ACCESS_TOKEN_EXPIRE_MINUTES, _DEFAULT_EXPIRE_MINUTES
        ),
    }


def load_auth_config(db: Session) -> dict[str, int]:
    base = _env_defaults()
    row = db.query(SystemConfig).filter(SystemConfig.key == AUTH_CONFIG_KEY).first()
    if not row:
        return dict(base)
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return dict(base)
    if not isinstance(stored, dict):
        return dict(base)
    if "access_token_expire_minutes" in stored and stored["access_token_expire_minutes"] is not None:
        base["access_token_expire_minutes"] = _clamp_expire(
            stored["access_token_expire_minutes"],
            base["access_token_expire_minutes"],
        )
    return base


def save_auth_config(db: Session, payload: dict[str, Any]) -> dict[str, int]:
    current = load_auth_config(db)
    minutes = payload.get("access_token_expire_minutes")
    if minutes is None:
        minutes = current["access_token_expire_minutes"]
    data = {
        "access_token_expire_minutes": _clamp_expire(
            minutes, current["access_token_expire_minutes"]
        ),
    }
    raw = json.dumps(data, ensure_ascii=False)
    row = db.query(SystemConfig).filter(SystemConfig.key == AUTH_CONFIG_KEY).first()
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=AUTH_CONFIG_KEY, value=raw))
    db.commit()
    return data


def public_auth_config(cfg: dict[str, int]) -> dict[str, Any]:
    minutes = int(cfg.get("access_token_expire_minutes") or _DEFAULT_EXPIRE_MINUTES)
    days = round(minutes / (60 * 24), 2)
    return {
        "access_token_expire_minutes": minutes,
        "access_token_expire_days": days,
    }


def get_access_token_expire_minutes(db: Session | None = None) -> int:
    if db is not None:
        return load_auth_config(db)["access_token_expire_minutes"]
    session = SessionLocal()
    try:
        return load_auth_config(session)["access_token_expire_minutes"]
    finally:
        session.close()
