"""终末地站内养成对比：统一本地角色图鉴，只对本人回源。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.security import strip_markup_chars
from app.models.endfield import EndfieldBoxRaw
from app.models.endfield import EndfieldAttendanceRaw
from app.models.checkin_role_pref import CheckinRolePref
from app.models.member import Member
from app.models.skland import SklandBind, SklandCheckinLog
from app.models.user import User
from app.services.box_role_cache import skland_endfield_roles_from_raws
from app.services.member_sync import ensure_user_member
from app.services.skland.boxes import parse_endfield_box
from app.services.skland.checkin import get_endfield_box_for_member
from app.services.skland.client import (
    GAME_ENDFIELD,
    GAME_META,
    SklandApiError,
    SklandRole,
)
from app.services.skland.endfield_catalog import list_operators

COMPARE_MAX_MEMBERS = 5


class EndfieldBoxCompareError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _viewer_member_id(db: Session, viewer: User) -> int:
    if viewer.member:
        return int(viewer.member.id)
    return int(ensure_user_member(db, viewer).id)


def _member_nickname(member: Member) -> str:
    return (
        strip_markup_chars(member.steam_persona_name).strip()
        or (member.user.display_name if member.user else None)
        or member.nickname
    )


def _candidate_member_ids(db: Session, self_id: int) -> set[int]:
    ids = {
        int(member_id)
        for (member_id,) in db.query(EndfieldBoxRaw.member_id).distinct().all()
        if member_id is not None
    }
    for model in (EndfieldAttendanceRaw,):
        ids.update(
            int(member_id)
            for (member_id,) in db.query(model.member_id).distinct().all()
            if member_id is not None
        )
    for (member_id,) in (
        db.query(SklandCheckinLog.member_id)
        .filter(SklandCheckinLog.game_code == GAME_ENDFIELD)
        .distinct()
        .all()
    ):
        if member_id is not None:
            ids.add(int(member_id))
    for (member_id,) in (
        db.query(CheckinRolePref.member_id)
        .filter(
            CheckinRolePref.platform == "skland",
            CheckinRolePref.game_code == GAME_ENDFIELD,
        )
        .distinct()
        .all()
    ):
        if member_id is not None:
            ids.add(int(member_id))
    if db.query(SklandBind.id).filter(SklandBind.member_id == self_id).first():
        ids.add(self_id)
    return ids


def _parse_cached_box(raw_json: str, role: SklandRole | None = None) -> Any | None:
    try:
        raw = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return parse_endfield_box(raw, role=role)
    except (TypeError, ValueError, KeyError):
        return None


def _cached_game_role_names(db: Session, member_ids: set[int]) -> dict[int, str]:
    names: dict[int, str] = {}
    if not member_ids:
        return names
    snapshots = (
        db.query(EndfieldBoxRaw)
        .filter(EndfieldBoxRaw.member_id.in_(member_ids))
        .order_by(EndfieldBoxRaw.member_id, EndfieldBoxRaw.role_id)
        .all()
    )
    for snapshot in snapshots:
        box = _parse_cached_box(snapshot.raw_json)
        if box and box.name:
            names.setdefault(int(snapshot.member_id), box.name)

    attendance_names = (
        db.query(EndfieldAttendanceRaw.member_id, EndfieldAttendanceRaw.role_name)
        .filter(EndfieldAttendanceRaw.member_id.in_(member_ids))
        .order_by(EndfieldAttendanceRaw.member_id, EndfieldAttendanceRaw.role_id)
        .all()
    )
    for member_id, role_name in attendance_names:
        if member_id is not None and role_name:
            names.setdefault(int(member_id), str(role_name))

    checkin_names = (
        db.query(SklandCheckinLog.member_id, SklandCheckinLog.role_name)
        .filter(
            SklandCheckinLog.member_id.in_(member_ids),
            SklandCheckinLog.game_code == GAME_ENDFIELD,
        )
        .order_by(SklandCheckinLog.member_id, SklandCheckinLog.checked_at.desc())
        .all()
    )
    for member_id, role_name in checkin_names:
        if member_id is not None and role_name:
            names.setdefault(int(member_id), str(role_name))
    return names


def list_compare_candidates(db: Session, viewer: User) -> list[dict[str, Any]]:
    """可选终末地成员：站内有角色记录且仍绑定森空岛的用户（含自己）。"""
    self_id = _viewer_member_id(db, viewer)
    ids = _candidate_member_ids(db, self_id)
    if not ids:
        return []
    role_names = _cached_game_role_names(db, ids)
    members = (
        db.query(Member)
        .options(joinedload(Member.user), joinedload(Member.skland_bind))
        .filter(Member.id.in_(ids), Member.user_id.isnot(None))
        .all()
    )
    candidates = []
    for member in members:
        if member.id != self_id and member.skland_bind is None:
            continue
        candidates.append(
            {
                "member_id": member.id,
                "nickname": _member_nickname(member),
                "avatar_url": member.avatar_url,
                "game_role_name": role_names.get(member.id),
                "is_self": member.id == self_id,
                "skland_bound": member.skland_bind is not None,
            }
        )
    candidates.sort(
        key=lambda row: (not row["is_self"], row["nickname"] or "", row["member_id"])
    )
    return candidates


def _role_out(role: SklandRole) -> dict[str, str]:
    return {
        "uid": str(role.uid),
        "role_name": str(role.role_name or role.uid),
        "channel_name": str(role.channel_name or ""),
    }


def _enrich_roles_from_cached_boxes(
    db: Session, member_id: int, roles: list[SklandRole]
) -> list[SklandRole]:
    by_role_id = {str(role.role_id): role for role in roles if role.role_id}
    if not by_role_id:
        return roles
    snapshots = (
        db.query(EndfieldBoxRaw)
        .filter(EndfieldBoxRaw.member_id == member_id)
        .order_by(EndfieldBoxRaw.role_id)
        .all()
    )
    for snapshot in snapshots:
        role = by_role_id.get(str(snapshot.role_id))
        if role is None:
            continue
        box = _parse_cached_box(snapshot.raw_json, role)
        if box is None:
            continue
        role.role_name = box.name or role.role_name
        role.channel_name = box.server_name or role.channel_name
    return roles


def _cached_roles(db: Session, member_id: int) -> list[SklandRole]:
    """Use roles already learned from boxes, attendance, or check-in history."""
    roles = skland_endfield_roles_from_raws(db, member_id) or []
    seen_uids = {role.uid for role in roles}
    meta = GAME_META[GAME_ENDFIELD]

    attendance_rows = (
        db.query(EndfieldAttendanceRaw)
        .filter(EndfieldAttendanceRaw.member_id == member_id)
        .order_by(EndfieldAttendanceRaw.role_id)
        .all()
    )
    for row in attendance_rows:
        role = SklandRole(
            game_code=GAME_ENDFIELD,
            game_name=meta["name"],
            uid=row.uid or row.role_id,
            role_name=row.role_name or row.uid or row.role_id,
            channel_name=row.channel_name or "",
            role_id=row.role_id,
            server_id=row.server_id,
        )
        if role.uid not in seen_uids:
            roles.append(role)
            seen_uids.add(role.uid)

    checkin_rows = (
        db.query(SklandCheckinLog)
        .filter(
            SklandCheckinLog.member_id == member_id,
            SklandCheckinLog.game_code == GAME_ENDFIELD,
        )
        .order_by(SklandCheckinLog.checked_at.desc())
        .all()
    )
    for row in checkin_rows:
        role = SklandRole(
            game_code=GAME_ENDFIELD,
            game_name=meta["name"],
            uid=row.role_uid,
            role_name=row.role_name or row.role_uid,
            channel_name=row.channel_name or "",
        )
        if role.uid not in seen_uids:
            roles.append(role)
            seen_uids.add(role.uid)

    preferences = (
        db.query(CheckinRolePref.role_uid)
        .filter(
            CheckinRolePref.member_id == member_id,
            CheckinRolePref.platform == "skland",
            CheckinRolePref.game_code == GAME_ENDFIELD,
        )
        .order_by(CheckinRolePref.role_uid)
        .all()
    )
    for (uid,) in preferences:
        uid = str(uid or "").strip()
        if not uid:
            continue
        role = SklandRole(
            game_code=GAME_ENDFIELD,
            game_name=meta["name"],
            uid=uid,
            role_name=uid,
            channel_name="",
        )
        if role.uid not in seen_uids:
            roles.append(role)
            seen_uids.add(role.uid)
    return _enrich_roles_from_cached_boxes(db, member_id, roles)


def _normalized_operator_key(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _align_box_char_ids(box: Any, catalog: list[dict[str, Any]]) -> None:
    """Re-key owned characters to the local catalog's canonical character ids."""
    catalog_ids = {
        _normalized_operator_key(operator.get("char_id")): str(operator.get("char_id"))
        for operator in catalog
        if operator.get("char_id")
    }
    names_to_ids: dict[str, set[str]] = {}
    for operator in catalog:
        name = _normalized_operator_key(operator.get("name"))
        char_id = str(operator.get("char_id") or "").strip()
        if name and char_id:
            names_to_ids.setdefault(name, set()).add(char_id)

    for char in box.chars:
        aliases = list(getattr(char, "char_id_aliases", []) or [])
        aliases.insert(0, char.char_id)
        canonical_id = next(
            (
                catalog_ids[_normalized_operator_key(alias)]
                for alias in aliases
                if _normalized_operator_key(alias) in catalog_ids
            ),
            None,
        )
        if canonical_id is None:
            matches = names_to_ids.get(_normalized_operator_key(char.name), set())
            if len(matches) == 1:
                canonical_id = next(iter(matches))
        if canonical_id:
            char.char_id = canonical_id


def _empty_row(
    member: Member,
    *,
    status: str,
    message: str | None,
    roles: list[SklandRole] | None = None,
) -> dict[str, Any]:
    return {
        "member_id": member.id,
        "nickname": _member_nickname(member),
        "avatar_url": member.avatar_url,
        "status": status,
        "message": message,
        "uid": None,
        "role_name": None,
        "channel_name": None,
        "player_level": None,
        "synced_at": None,
        "char_count": 0,
        "owned": {},
        "roles": [_role_out(role) for role in roles or []],
    }


def _cached_box(
    db: Session,
    member: Member,
    requested_uid: str | None,
    roles: list[SklandRole],
) -> tuple[Any | None, SklandRole | None, str | None, str | None]:
    role = next(
        (
            item
            for item in roles
            if not requested_uid
            or item.uid == requested_uid
            or item.role_id == requested_uid
        ),
        None,
    )
    if role is None:
        return None, None, "该成员没有此终末地角色的缓存数据", None
    row = (
        db.query(EndfieldBoxRaw)
        .filter(
            EndfieldBoxRaw.member_id == member.id,
            EndfieldBoxRaw.role_id == str(role.role_id or ""),
        )
        .one_or_none()
    )
    if row is None:
        return None, role, "暂无养成快照；成员打开干员信息页同步后可见", None
    try:
        raw = json.loads(row.raw_json)
    except json.JSONDecodeError:
        return None, role, "养成快照格式异常", None
    if not isinstance(raw, dict):
        return None, role, "养成快照格式异常", None
    return (
        parse_endfield_box(raw, role=role),
        role,
        None,
        row.synced_at.isoformat() if row.synced_at else None,
    )


def _box_row(
    member: Member,
    box: Any,
    roles: list[SklandRole],
    *,
    synced_at: str | None,
) -> dict[str, Any]:
    return {
        "member_id": member.id,
        "nickname": _member_nickname(member),
        "avatar_url": member.avatar_url,
        "status": "ok",
        "message": None,
        "uid": box.uid,
        "role_name": box.name,
        "channel_name": box.server_name,
        "player_level": box.level,
        "synced_at": synced_at,
        "char_count": box.char_count or len(box.chars),
        "owned": {char.char_id: char for char in box.chars},
        "roles": [_role_out(role) for role in roles],
    }


def build_box_compare(
    db: Session,
    viewer: User,
    member_ids: list[int],
    *,
    role_uids: dict[int, str] | None = None,
) -> dict[str, Any]:
    if not member_ids:
        raise EndfieldBoxCompareError("请至少选择一名成员")
    ordered_ids = list(dict.fromkeys(int(member_id) for member_id in member_ids))
    if len(ordered_ids) > COMPARE_MAX_MEMBERS:
        raise EndfieldBoxCompareError(f"最多同时对比 {COMPARE_MAX_MEMBERS} 人")

    self_id = _viewer_member_id(db, viewer)
    allowed = _candidate_member_ids(db, self_id)
    if any(member_id not in allowed for member_id in ordered_ids):
        raise EndfieldBoxCompareError("无权查看所选成员的终末地养成数据")

    catalog = list_operators()
    members = (
        db.query(Member)
        .options(joinedload(Member.user), joinedload(Member.skland_bind))
        .filter(Member.id.in_(ordered_ids))
        .all()
    )
    by_id = {member.id: member for member in members}
    rows: list[dict[str, Any]] = []
    uid_map = role_uids or {}
    for member_id in ordered_ids:
        member = by_id.get(member_id)
        if member is None:
            continue
        if member_id != self_id and member.skland_bind is None:
            rows.append(
                _empty_row(member, status="unbound", message="该成员已解除森空岛绑定")
            )
            continue

        requested_uid = str(uid_map.get(member_id) or "").strip() or None
        roles = _cached_roles(db, member_id)
        if member_id == self_id:
            try:
                box, _role, roles, synced_at, _stale = get_endfield_box_for_member(
                    db, member, requested_uid, force=False
                )
                roles = _enrich_roles_from_cached_boxes(db, member_id, roles)
                _align_box_char_ids(box, catalog)
            except SklandApiError as exc:
                rows.append(
                    _empty_row(member, status="error", message=exc.message, roles=roles)
                )
                continue
            rows.append(
                _box_row(
                    member,
                    box,
                    roles,
                    synced_at=synced_at.isoformat() if synced_at else None,
                )
            )
            continue

        box, _role, error, synced_at = _cached_box(db, member, requested_uid, roles)
        if box is None:
            status = "no_snapshot" if error and error.startswith("暂无") else "error"
            rows.append(_empty_row(member, status=status, message=error, roles=roles))
            continue
        _align_box_char_ids(box, catalog)
        rows.append(_box_row(member, box, roles, synced_at=synced_at))

    return {"catalog": catalog, "catalog_count": len(catalog), "rows": rows}
