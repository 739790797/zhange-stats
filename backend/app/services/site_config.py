"""公开站点展示：ICP 备案号等。权威源为 config/auth.json。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.auth_config import load_auth_config, save_auth_config

SITE_CONFIG_KEY = "site"
ICP_BEIAN_HREF = "https://beian.miit.gov.cn/"
_MAX_ICP_BEIAN_NO = 64


def normalize_icp_beian_no(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > _MAX_ICP_BEIAN_NO:
        return text[:_MAX_ICP_BEIAN_NO]
    return text


def load_site_config(_db: Session | None = None) -> dict[str, str]:
    cfg = load_auth_config(_db)
    return {"icp_beian_no": normalize_icp_beian_no(cfg.get("icp_beian_no"))}


def save_site_config(_db: Session | None, payload: dict[str, Any]) -> dict[str, str]:
    current = load_site_config(_db)
    if "icp_beian_no" in payload:
        current["icp_beian_no"] = normalize_icp_beian_no(payload.get("icp_beian_no"))
    saved = save_auth_config(_db, {"icp_beian_no": current["icp_beian_no"]})
    return {"icp_beian_no": normalize_icp_beian_no(saved.get("icp_beian_no"))}


def public_site_config(cfg: dict[str, Any]) -> dict[str, str]:
    return {
        "icp_beian_no": normalize_icp_beian_no(cfg.get("icp_beian_no")),
        "icp_beian_href": ICP_BEIAN_HREF,
    }
