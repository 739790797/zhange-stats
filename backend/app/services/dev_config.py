"""本地假监控等开发选项：数据库优先，.env 兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.local_dev_hooks import import_steam_fake
from app.models.system_config import SystemConfig

DEV_CONFIG_KEY = "dev_local"


def steam_fake_module_available() -> bool:
    return import_steam_fake() is not None


def _env_defaults() -> dict[str, bool]:
    return {"steam_fake_poll": bool(get_settings().STEAM_FAKE_POLL)}


def load_dev_config(db: Session) -> dict[str, bool]:
    base = _env_defaults()
    row = db.query(SystemConfig).filter(SystemConfig.key == DEV_CONFIG_KEY).first()
    if not row:
        return dict(base)
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return dict(base)
    if not isinstance(stored, dict):
        return dict(base)
    if "steam_fake_poll" in stored and stored["steam_fake_poll"] is not None:
        base["steam_fake_poll"] = bool(stored["steam_fake_poll"])
    return base


def save_dev_config(db: Session, payload: dict[str, Any]) -> dict[str, bool]:
    current = load_dev_config(db)
    if "steam_fake_poll" in payload and payload["steam_fake_poll"] is not None:
        current["steam_fake_poll"] = bool(payload["steam_fake_poll"])
    raw = json.dumps(current, ensure_ascii=False)
    row = db.query(SystemConfig).filter(SystemConfig.key == DEV_CONFIG_KEY).first()
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=DEV_CONFIG_KEY, value=raw))
    db.commit()
    return current


def is_steam_fake_poll(db: Session | None = None) -> bool:
    if db is not None:
        return bool(load_dev_config(db).get("steam_fake_poll"))
    session = SessionLocal()
    try:
        return bool(load_dev_config(session).get("steam_fake_poll"))
    finally:
        session.close()
