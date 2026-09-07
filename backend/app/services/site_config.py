"""公开站点展示：ICP 备案号等。数据库优先，.env 兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.system_config import SystemConfig

SITE_CONFIG_KEY = "site"
ICP_BEIAN_HREF = "https://beian.miit.gov.cn/"
_MAX_ICP_BEIAN_NO = 64


def normalize_icp_beian_no(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > _MAX_ICP_BEIAN_NO:
        return text[:_MAX_ICP_BEIAN_NO]
    return text


def _env_defaults() -> dict[str, str]:
    return {"icp_beian_no": normalize_icp_beian_no(get_settings().ICP_BEIAN_NO)}


def load_site_config(db: Session) -> dict[str, str]:
    base = _env_defaults()
    row = db.query(SystemConfig).filter(SystemConfig.key == SITE_CONFIG_KEY).first()
    if not row:
        return dict(base)
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return dict(base)
    if not isinstance(stored, dict):
        return dict(base)
    if "icp_beian_no" in stored:
        base["icp_beian_no"] = normalize_icp_beian_no(stored.get("icp_beian_no"))
    return base


def save_site_config(db: Session, payload: dict[str, Any]) -> dict[str, str]:
    current = load_site_config(db)
    if "icp_beian_no" in payload:
        current["icp_beian_no"] = normalize_icp_beian_no(payload.get("icp_beian_no"))
    raw = json.dumps(
        {"icp_beian_no": current["icp_beian_no"]},
        ensure_ascii=False,
    )
    row = db.query(SystemConfig).filter(SystemConfig.key == SITE_CONFIG_KEY).first()
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=SITE_CONFIG_KEY, value=raw))
    db.commit()
    return current


def public_site_config(cfg: dict[str, Any]) -> dict[str, str]:
    return {
        "icp_beian_no": normalize_icp_beian_no(cfg.get("icp_beian_no")),
        "icp_beian_href": ICP_BEIAN_HREF,
    }
