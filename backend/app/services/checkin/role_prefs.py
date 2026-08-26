"""按角色「加入本站」与自动签到偏好：种子、读写、调度查询。"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.core.timeutil import now_naive
from app.models.checkin_role_pref import CheckinRolePref
from app.services.checkin.schedule import clamp_checkin_hour, clamp_checkin_minute

PLATFORM_SKLAND = "skland"
PLATFORM_TAYGEDO = "taygedo"
PLATFORM_EXILIUM = "exilium"
PLATFORM_KUJIEQU = "kujiequ"
PLATFORM_MIHOYO = "mihoyo"

RoleKey = tuple[str, str]  # (game_code, role_uid)


def role_key(game_code: str, role_uid: str) -> RoleKey:
    return (str(game_code or "").strip(), str(role_uid or "").strip())


def _parse_role_item(item: RoleKey | dict[str, Any] | Any) -> RoleKey | None:
    if isinstance(item, tuple) and len(item) == 2:
        gc, uid = role_key(item[0], item[1])
    elif isinstance(item, dict):
        gc, uid = role_key(
            str(item.get("game_code") or ""),
            str(
                item.get("role_uid")
                or item.get("uid")
                or ""
            ),
        )
    else:
        gc, uid = role_key(
            str(getattr(item, "game_code", "") or ""),
            str(
                getattr(item, "role_uid", None)
                or getattr(item, "uid", None)
                or ""
            ),
        )
    if not gc or not uid:
        return None
    return (gc, uid)


def load_pref_map(
    db: Session,
    *,
    platform: str,
    member_id: int,
) -> dict[RoleKey, CheckinRolePref]:
    rows = (
        db.query(CheckinRolePref)
        .filter(
            CheckinRolePref.platform == platform,
            CheckinRolePref.member_id == int(member_id),
        )
        .all()
    )
    return {role_key(r.game_code, r.role_uid): r for r in rows}


def count_prefs(db: Session, *, platform: str, member_id: int) -> int:
    return (
        db.query(CheckinRolePref)
        .filter(
            CheckinRolePref.platform == platform,
            CheckinRolePref.member_id == int(member_id),
        )
        .count()
    )


def ensure_prefs_for_roles(
    db: Session,
    *,
    platform: str,
    member_id: int,
    bind: Any,
    roles: Iterable[RoleKey | dict[str, Any] | Any],
    default_included: bool = False,
) -> dict[RoleKey, CheckinRolePref]:
    """为尚未有 pref 的角色插入行；已有行不覆盖。

    种子规则：
    - 新角色默认 included=False（须经绑定/同步树选加入），除非显式 default_included
    - bind.auto_checkin == True → enabled=True + 沿用 bind 时间（旧「全开」）
    - 否则 → enabled=False，时间可带上 bind 旧时间便于一键开启
    """
    pref_map = load_pref_map(db, platform=platform, member_id=member_id)
    legacy_on = bool(getattr(bind, "auto_checkin", False))
    hour = clamp_checkin_hour(getattr(bind, "checkin_hour", 0), default=0)
    minute = clamp_checkin_minute(getattr(bind, "checkin_minute", 5), default=5)
    changed = False

    for item in roles:
        parsed = _parse_role_item(item)
        if parsed is None:
            continue
        gc, uid = parsed
        key = (gc, uid)
        if key in pref_map:
            continue
        row = CheckinRolePref(
            platform=platform,
            member_id=int(member_id),
            game_code=gc,
            role_uid=uid,
            included=bool(default_included),
            enabled=legacy_on and bool(default_included),
            checkin_hour=hour,
            checkin_minute=minute,
        )
        db.add(row)
        pref_map[key] = row
        changed = True

    if changed:
        sync_bind_auto_checkin_from_prefs(db, platform=platform, member_id=member_id, bind=bind)
        db.flush()
    return pref_map


def sync_bind_auto_checkin_from_prefs(
    db: Session,
    *,
    platform: str,
    member_id: int,
    bind: Any,
) -> None:
    """bind.auto_checkin = 任一「已加入且 enabled」角色（管理端任务列表兼容）。"""
    any_on = (
        db.query(CheckinRolePref.id)
        .filter(
            CheckinRolePref.platform == platform,
            CheckinRolePref.member_id == int(member_id),
            CheckinRolePref.included.is_(True),
            CheckinRolePref.enabled.is_(True),
        )
        .first()
        is not None
    )
    if bool(getattr(bind, "auto_checkin", False)) != any_on:
        bind.auto_checkin = any_on
        if hasattr(bind, "updated_at"):
            bind.updated_at = now_naive()


def upsert_role_pref(
    db: Session,
    *,
    platform: str,
    member_id: int,
    bind: Any,
    game_code: str,
    role_uid: str,
    enabled: bool | None = None,
    included: bool | None = None,
    checkin_hour: int | None = None,
    checkin_minute: int | None = None,
    commit: bool = True,
) -> CheckinRolePref:
    gc, uid = role_key(game_code, role_uid)
    if not gc or not uid:
        raise ValueError("game_code / role_uid 不能为空")

    pref_map = load_pref_map(db, platform=platform, member_id=member_id)
    row = pref_map.get((gc, uid))
    if row is None:
        row = CheckinRolePref(
            platform=platform,
            member_id=int(member_id),
            game_code=gc,
            role_uid=uid,
            included=False,
            enabled=False,
            checkin_hour=clamp_checkin_hour(getattr(bind, "checkin_hour", 0)),
            checkin_minute=clamp_checkin_minute(getattr(bind, "checkin_minute", 5)),
        )
        db.add(row)

    if included is not None:
        row.included = bool(included)
        if not row.included:
            row.enabled = False

    if enabled is not None:
        if bool(enabled) and not bool(row.included):
            # 开启自动签到隐含加入本站
            row.included = True
        row.enabled = bool(enabled)

    if checkin_hour is not None:
        row.checkin_hour = clamp_checkin_hour(checkin_hour)
    if checkin_minute is not None:
        row.checkin_minute = clamp_checkin_minute(checkin_minute)

    if row.enabled:
        if row.checkin_hour is None or row.checkin_minute is None:
            raise ValueError("开启自动签到时必须设置签到时间")
        row.checkin_hour = clamp_checkin_hour(row.checkin_hour)
        row.checkin_minute = clamp_checkin_minute(row.checkin_minute)

    row.updated_at = now_naive()
    sync_bind_auto_checkin_from_prefs(db, platform=platform, member_id=member_id, bind=bind)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def apply_role_memberships(
    db: Session,
    *,
    platform: str,
    member_id: int,
    bind: Any,
    roles: Iterable[dict[str, Any]],
) -> list[CheckinRolePref]:
    """批量写入加入本站；未列入的已有 pref 保持不变。

    每项需含 game_code / role_uid / included。关闭 included 时强制 enabled=False。
    """
    out: list[CheckinRolePref] = []
    for item in roles:
        gc = str(item.get("game_code") or "").strip()
        uid = str(item.get("role_uid") or item.get("uid") or "").strip()
        if not gc or not uid:
            continue
        included = bool(item.get("included", False))
        row = upsert_role_pref(
            db,
            platform=platform,
            member_id=member_id,
            bind=bind,
            game_code=gc,
            role_uid=uid,
            included=included,
            enabled=False if not included else None,
            commit=False,
        )
        out.append(row)
    sync_bind_auto_checkin_from_prefs(db, platform=platform, member_id=member_id, bind=bind)
    db.commit()
    for row in out:
        db.refresh(row)
    return out


def enrich_result_dicts(
    results: list[dict[str, Any]],
    pref_map: dict[RoleKey, CheckinRolePref],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in results:
        item = dict(r)
        key = role_key(str(item.get("game_code") or ""), str(item.get("role_uid") or ""))
        pref = pref_map.get(key)
        if pref is None:
            item["included"] = False
            item["auto_checkin"] = False
            item["checkin_hour"] = None
            item["checkin_minute"] = None
        else:
            item["included"] = bool(pref.included)
            item["auto_checkin"] = bool(pref.enabled) and bool(pref.included)
            item["checkin_hour"] = pref.checkin_hour
            item["checkin_minute"] = pref.checkin_minute
        out.append(item)
    return out


def filter_included_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """签到展示：仅返回已加入本站的角色。"""
    return [r for r in results if bool(r.get("included"))]


def attach_prefs_to_status_results(
    db: Session,
    *,
    platform: str,
    member_id: int,
    bind: Any,
    results: list[dict[str, Any]],
    only_included: bool = True,
) -> list[dict[str, Any]]:
    if not results:
        return results
    roles = [
        role_key(str(r.get("game_code") or ""), str(r.get("role_uid") or ""))
        for r in results
    ]
    pref_map = ensure_prefs_for_roles(
        db,
        platform=platform,
        member_id=member_id,
        bind=bind,
        roles=roles,
        default_included=False,
    )
    db.commit()
    enriched = enrich_result_dicts(results, pref_map)
    if only_included:
        return filter_included_results(enriched)
    return enriched


def list_due_role_keys(
    db: Session,
    *,
    platform: str,
    hour: int,
    minute: int,
    member_id: int | None = None,
) -> dict[int, set[RoleKey]]:
    """返回 member_id → 到点且已加入且 enabled 的角色键集合。"""
    q = db.query(CheckinRolePref).filter(
        CheckinRolePref.platform == platform,
        CheckinRolePref.included.is_(True),
        CheckinRolePref.enabled.is_(True),
        CheckinRolePref.checkin_hour == int(hour),
        CheckinRolePref.checkin_minute == int(minute),
    )
    if member_id is not None:
        q = q.filter(CheckinRolePref.member_id == int(member_id))
    grouped: dict[int, set[RoleKey]] = {}
    for row in q.all():
        grouped.setdefault(int(row.member_id), set()).add(
            role_key(row.game_code, row.role_uid)
        )
    return grouped


def list_enabled_role_keys_for_member(
    db: Session,
    *,
    platform: str,
    member_id: int,
) -> set[RoleKey] | None:
    """该成员全部已加入且 enabled 角色；若尚无任何 pref 返回 None（走旧 bind 全量）。"""
    if count_prefs(db, platform=platform, member_id=member_id) == 0:
        return None
    rows = (
        db.query(CheckinRolePref)
        .filter(
            CheckinRolePref.platform == platform,
            CheckinRolePref.member_id == int(member_id),
            CheckinRolePref.included.is_(True),
            CheckinRolePref.enabled.is_(True),
        )
        .all()
    )
    return {role_key(r.game_code, r.role_uid) for r in rows}


def matches_role_filter(
    game_code: str,
    role_uid: str,
    role_keys: set[RoleKey] | None,
) -> bool:
    if role_keys is None:
        return True
    return role_key(game_code, role_uid) in role_keys


def collect_checkin_job_targets(
    db: Session,
    *,
    platform: str,
    bind_model: Any,
    due_only: bool = False,
    member_id: int | None = None,
) -> dict[int, set[RoleKey] | None]:
    """组装调度目标：member_id → role_keys（None=旧绑定全量）。"""
    from app.core.timeutil import now as now_beijing

    targets: dict[int, set[RoleKey] | None] = {}

    if member_id is not None and not due_only:
        bind = (
            db.query(bind_model)
            .filter(bind_model.member_id == int(member_id))
            .one_or_none()
        )
        if bind is not None and bind.auto_checkin:
            targets[bind.member_id] = list_enabled_role_keys_for_member(
                db, platform=platform, member_id=bind.member_id
            )
        return targets

    if due_only:
        t = now_beijing()
        targets.update(
            list_due_role_keys(
                db,
                platform=platform,
                hour=t.hour,
                minute=t.minute,
                member_id=member_id,
            )
        )
        q = db.query(bind_model).filter(
            bind_model.auto_checkin.is_(True),
            bind_model.checkin_hour == t.hour,
            bind_model.checkin_minute == t.minute,
        )
        if member_id is not None:
            q = q.filter(bind_model.member_id == int(member_id))
        for bind in q.all():
            if bind.member_id in targets:
                continue
            if count_prefs(db, platform=platform, member_id=bind.member_id) == 0:
                targets[bind.member_id] = None
        return targets

    for bind in db.query(bind_model).filter(bind_model.auto_checkin.is_(True)).all():
        targets[bind.member_id] = list_enabled_role_keys_for_member(
            db, platform=platform, member_id=bind.member_id
        )
    return targets


def build_membership_tree_from_roles(
    *,
    platform: str,
    roles: Iterable[Any],
    pref_map: dict[RoleKey, CheckinRolePref] | None = None,
) -> list[dict[str, Any]]:
    """将 preview_roles 结果规整为 membership 树叶子（扁平，前端按 game 分组）。"""
    prefs = pref_map or {}
    out: list[dict[str, Any]] = []
    seen: set[RoleKey] = set()
    for item in roles:
        if isinstance(item, dict):
            gc = str(item.get("game_code") or "").strip()
            uid = str(item.get("role_uid") or item.get("uid") or "").strip()
            game_name = str(item.get("game_name") or gc)
            role_name = str(item.get("role_name") or uid)
            channel_name = str(item.get("channel_name") or "")
        else:
            gc = str(getattr(item, "game_code", "") or "").strip()
            uid = str(
                getattr(item, "role_uid", None) or getattr(item, "uid", None) or ""
            ).strip()
            game_name = str(getattr(item, "game_name", None) or gc)
            role_name = str(getattr(item, "role_name", None) or uid)
            channel_name = str(getattr(item, "channel_name", None) or "")
        if not gc or not uid:
            continue
        key = (gc, uid)
        if key in seen:
            continue
        seen.add(key)
        pref = prefs.get(key)
        out.append(
            {
                "game_code": gc,
                "game_name": game_name,
                "role_uid": uid,
                "role_name": role_name,
                "channel_name": channel_name,
                "included": bool(pref.included) if pref is not None else False,
            }
        )
    return out
