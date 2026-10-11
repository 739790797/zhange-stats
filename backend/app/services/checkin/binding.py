"""绑定生命周期里各平台共用的收尾：（重新）绑定成功后、解绑时。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.checkin_role_pref import CheckinRolePref
from app.services.checkin.adapter import CheckinPlatformAdapter
from app.services.checkin.attempts import clear_checkin_attempts
from app.services.checkin.orchestrator import run_checkin_for_bind
from app.services.checkin.role_prefs import list_enabled_role_keys_for_member

logger = logging.getLogger(__name__)


def _delete_member_raws(
    adapter: CheckinPlatformAdapter, db: Session, member_id: int
) -> None:
    for model in adapter.member_raw_models:
        db.query(model).filter(model.member_id == member_id).delete(
            synchronize_session=False
        )


def after_bind(adapter: CheckinPlatformAdapter, db: Session, bind: Any) -> None:
    """（重新）绑定成功后的收尾；绑定接口同时承担「更换绑定」，新凭证可能是另一个账号。

    - 删掉按成员缓存的 raw：读库优先的页面不能还展示旧账号，下次打开再回源
    - 清当日重试账：凭证失效被判当日终止的成员，换票后今天还要能排上
    - 开着自动签到就按已开的角色立即补签（与调度同一口径）
    """
    member_id = bind.member_id
    _delete_member_raws(adapter, db, member_id)
    db.commit()
    clear_checkin_attempts(adapter.platform, member_id)
    if not bind.auto_checkin:
        return
    role_keys = list_enabled_role_keys_for_member(
        db, platform=adapter.platform, member_id=member_id
    )
    if role_keys is not None and not role_keys:
        return
    try:
        run_checkin_for_bind(adapter, db, bind, force=False, role_keys=role_keys)
    except Exception:  # noqa: BLE001
        logger.exception(
            "%s checkin after bind failed member_id=%s", adapter.platform, member_id
        )
        db.rollback()
        db.refresh(bind)


def unbind_member(adapter: CheckinPlatformAdapter, db: Session, member_id: int) -> bool:
    """删绑定，连同该平台按成员缓存的 raw、按角色偏好与当日重试账；没有绑定返回 False。

    签到 logs 随 bind 级联删除。
    """
    bind = adapter.get_bind(db, member_id)
    if bind is None:
        return False
    _delete_member_raws(adapter, db, member_id)
    db.query(CheckinRolePref).filter(
        CheckinRolePref.platform == adapter.platform,
        CheckinRolePref.member_id == member_id,
    ).delete(synchronize_session=False)
    db.delete(bind)
    db.commit()
    clear_checkin_attempts(adapter.platform, member_id)
    return True
