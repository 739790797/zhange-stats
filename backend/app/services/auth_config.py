"""登录会话与安全策略：数据库优先，.env / 代码默认兜底。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.system_config import SystemConfig
from app.models.user import User, UserRole

AUTH_CONFIG_KEY = "auth_session"
_DEFAULT_EXPIRE_MINUTES = 60 * 24  # 24 小时
_MIN_EXPIRE = 5
_MAX_EXPIRE = 60 * 24 * 365  # 最长 1 年
_DEFAULT_MIN_PASSWORD_LENGTH = 8
_MIN_PASSWORD_LENGTH = 6
_MAX_PASSWORD_LENGTH = 72


def _clamp_expire(value: Any, default: int = _DEFAULT_EXPIRE_MINUTES) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return default
    return max(_MIN_EXPIRE, min(_MAX_EXPIRE, minutes))


def _clamp_min_password_length(
    value: Any, default: int = _DEFAULT_MIN_PASSWORD_LENGTH
) -> int:
    try:
        length = int(value)
    except (TypeError, ValueError):
        return default
    return max(_MIN_PASSWORD_LENGTH, min(_MAX_PASSWORD_LENGTH, length))


def _as_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("", "null", "none"):
        return None
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return None


def _env_defaults() -> dict[str, Any]:
    s = get_settings()
    # 兼容旧 .env：仅在库中尚无策略时作为初始默认
    reject: bool | None = None
    if s.REJECT_WEAK_ADMIN_PASSWORD is not None:
        reject = bool(s.REJECT_WEAK_ADMIN_PASSWORD)
    return {
        "access_token_expire_minutes": _clamp_expire(
            s.ACCESS_TOKEN_EXPIRE_MINUTES, _DEFAULT_EXPIRE_MINUTES
        ),
        "min_password_length": _DEFAULT_MIN_PASSWORD_LENGTH,
        "reject_weak_admin_password": reject,
        "enforce_single_admin": bool(s.ENFORCE_SINGLE_ADMIN),
    }


def load_auth_config(db: Session) -> dict[str, Any]:
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

    if (
        "access_token_expire_minutes" in stored
        and stored["access_token_expire_minutes"] is not None
    ):
        base["access_token_expire_minutes"] = _clamp_expire(
            stored["access_token_expire_minutes"],
            base["access_token_expire_minutes"],
        )
    if "min_password_length" in stored and stored["min_password_length"] is not None:
        base["min_password_length"] = _clamp_min_password_length(
            stored["min_password_length"],
            base["min_password_length"],
        )
    if "reject_weak_admin_password" in stored:
        base["reject_weak_admin_password"] = _as_optional_bool(
            stored.get("reject_weak_admin_password")
        )
    if "enforce_single_admin" in stored and stored["enforce_single_admin"] is not None:
        base["enforce_single_admin"] = bool(stored["enforce_single_admin"])
    return base


def save_auth_config(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    current = load_auth_config(db)

    minutes = payload.get("access_token_expire_minutes")
    if minutes is None:
        minutes = current["access_token_expire_minutes"]

    min_len = payload.get("min_password_length")
    if min_len is None:
        min_len = current["min_password_length"]

    if "reject_weak_admin_password" in payload:
        reject = _as_optional_bool(payload.get("reject_weak_admin_password"))
    else:
        reject = current.get("reject_weak_admin_password")

    if "enforce_single_admin" in payload and payload["enforce_single_admin"] is not None:
        enforce = bool(payload["enforce_single_admin"])
    else:
        enforce = bool(current.get("enforce_single_admin"))

    data = {
        "access_token_expire_minutes": _clamp_expire(
            minutes, current["access_token_expire_minutes"]
        ),
        "min_password_length": _clamp_min_password_length(
            min_len, current["min_password_length"]
        ),
        "reject_weak_admin_password": reject,
        "enforce_single_admin": enforce,
    }
    raw = json.dumps(data, ensure_ascii=False)
    row = db.query(SystemConfig).filter(SystemConfig.key == AUTH_CONFIG_KEY).first()
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=AUTH_CONFIG_KEY, value=raw))
    db.commit()
    return data


def effective_reject_weak_admin_password(cfg: dict[str, Any] | None = None) -> bool:
    """显式策略优先；未设置时 production 默认拒绝。"""
    settings = get_settings()
    if cfg is None:
        reject = None
    else:
        reject = _as_optional_bool(cfg.get("reject_weak_admin_password"))
    if reject is not None:
        return reject
    # 库无策略时仍尊重旧 env 覆盖
    if settings.REJECT_WEAK_ADMIN_PASSWORD is not None:
        return bool(settings.REJECT_WEAK_ADMIN_PASSWORD)
    return settings.is_production


def public_auth_config(
    cfg: dict[str, Any],
    *,
    db: Session | None = None,
    check_weak_passwords: bool = False,
) -> dict[str, Any]:
    minutes = int(cfg.get("access_token_expire_minutes") or _DEFAULT_EXPIRE_MINUTES)
    days = round(minutes / (60 * 24), 2)
    reject_effective = effective_reject_weak_admin_password(cfg)
    out: dict[str, Any] = {
        "access_token_expire_minutes": minutes,
        "access_token_expire_days": days,
        "min_password_length": _clamp_min_password_length(
            cfg.get("min_password_length"), _DEFAULT_MIN_PASSWORD_LENGTH
        ),
        "reject_weak_admin_password": _as_optional_bool(
            cfg.get("reject_weak_admin_password")
        ),
        "reject_weak_admin_password_effective": reject_effective,
        "enforce_single_admin": bool(cfg.get("enforce_single_admin")),
        "app_env": get_settings().APP_ENV,
        "is_production": get_settings().is_production,
    }
    if db is not None:
        admins = (
            db.query(User)
            .filter(User.role == UserRole.admin)
            .order_by(User.id.asc())
            .all()
        )
        weak_ids: set[int] = set()
        if check_weak_passwords:
            from app.services.password_policy import list_admins_with_weak_password

            weak_ids = {u.id for u in list_admins_with_weak_password(db)}
        out["admins"] = [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "email": u.email,
                "weak_password": (u.id in weak_ids) if check_weak_passwords else False,
            }
            for u in admins
        ]
        out["weak_password_checked"] = check_weak_passwords
    return out


def get_access_token_expire_minutes(db: Session | None = None) -> int:
    if db is not None:
        return int(load_auth_config(db)["access_token_expire_minutes"])
    session = SessionLocal()
    try:
        return int(load_auth_config(session)["access_token_expire_minutes"])
    finally:
        session.close()


def get_min_password_length(db: Session) -> int:
    return _clamp_min_password_length(
        load_auth_config(db).get("min_password_length"),
        _DEFAULT_MIN_PASSWORD_LENGTH,
    )


def enforce_single_admin_if_needed(
    db: Session,
    *,
    keep_user_id: int | None = None,
) -> None:
    cfg = load_auth_config(db)
    if not cfg.get("enforce_single_admin"):
        return
    admins = (
        db.query(User)
        .filter(User.role == UserRole.admin)
        .order_by(User.id.asc())
        .all()
    )
    if len(admins) <= 1:
        return
    keeper_id = keep_user_id
    if keeper_id is None or not any(u.id == keeper_id for u in admins):
        keeper_id = admins[0].id
    for user in admins:
        if user.id != keeper_id:
            user.apply_role(UserRole.user)
