"""明日方舟盒子对比：图鉴对齐 + 盒子练度日更缓存。"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.timeutil import now_naive, today
from app.models.arknights import ArknightsBoxSnapshot
from app.models.checkin_role_pref import CheckinRolePref
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.skland import SklandAttendanceRaw, SklandBind, SklandCheckinLog
from app.models.user import User
from app.services.skland.arknights_catalog import (
    ArknightsCatalogError,
    ensure_catalog,
    get_catalog_meta,
)
from app.services.skland.checkin import get_arknights_box_for_member, get_bind_for_member
from app.services.skland.client import GAME_ARKNIGHTS, SklandApiError

logger = logging.getLogger(__name__)

COMPARE_MAX_MEMBERS = 5
JOB_KEY = "arknights_box_sync"


def _owned_map_from_box(box) -> dict[str, dict[str, Any]]:
    owned: dict[str, dict[str, Any]] = {}
    for c in box.chars:
        skills = [
            {
                "skill_id": s.skill_id,
                "specialize_level": s.specialize_level,
                "label": s.label,
            }
            for s in (c.skills or [])
        ]
        equips = [
            {
                "equip_id": e.equip_id,
                "name": e.name,
                "level": e.level,
                "type_icon": e.type_icon,
                "locked": e.locked,
            }
            for e in (c.equips or [])
        ]
        owned[c.char_id] = {
            "level": c.level,
            "evolve_phase": c.evolve_phase,
            "potential_rank": c.potential_rank,
            "favor_percent": c.favor_percent,
            "skin_id": c.skin_id,
            "avatar_url": c.avatar_url,
            "main_skill_lvl": c.main_skill_lvl,
            "skills": skills,
            "equips": equips,
        }
    return owned


def _payload_has_detail(payload: dict[str, Any]) -> bool:
    """旧缓存无技能/模组字段时视为过期。"""
    owned = payload.get("owned")
    if not isinstance(owned, dict) or not owned:
        return "roles" in payload
    sample = next(iter(owned.values()), None)
    return isinstance(sample, dict) and "skills" in sample


def _load_snapshot(
    db: Session, member_id: int, uid: str | None
) -> dict[str, Any] | None:
    day = today()
    if uid:
        row = (
            db.query(ArknightsBoxSnapshot)
            .filter(
                ArknightsBoxSnapshot.member_id == member_id,
                ArknightsBoxSnapshot.uid == uid,
                ArknightsBoxSnapshot.sync_date == day,
            )
            .first()
        )
    else:
        # 未指定 uid：用当日任一快照里的 roles 推断默认角色
        row = (
            db.query(ArknightsBoxSnapshot)
            .filter(
                ArknightsBoxSnapshot.member_id == member_id,
                ArknightsBoxSnapshot.sync_date == day,
            )
            .order_by(ArknightsBoxSnapshot.synced_at.desc())
            .first()
        )
        if row is None:
            return None
        try:
            probe = json.loads(row.payload_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(probe, dict):
            return None
        roles = probe.get("roles") if isinstance(probe.get("roles"), list) else []
        default_uid = None
        if roles and isinstance(roles[0], dict):
            default_uid = str(roles[0].get("uid") or "").strip() or None
        if not default_uid:
            default_uid = str(probe.get("uid") or row.uid or "").strip() or None
        if default_uid and default_uid != row.uid:
            return _load_snapshot(db, member_id, default_uid)
        # row 已是默认角色
        if not _payload_has_detail(probe):
            return None
        return probe

    if row is None:
        return None
    try:
        payload = json.loads(row.payload_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not _payload_has_detail(payload):
        return None
    return payload


def _save_snapshot(db: Session, member_id: int, payload: dict[str, Any]) -> None:
    uid = str(payload.get("uid") or "").strip()
    if not uid:
        return
    row = (
        db.query(ArknightsBoxSnapshot)
        .filter(
            ArknightsBoxSnapshot.member_id == member_id,
            ArknightsBoxSnapshot.uid == uid,
        )
        .first()
    )
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    from app.services.raw_payload_monitor import note_raw_payload

    note_raw_payload(
        "arknights_box_snapshot",
        blob,
        member_id=member_id,
        uid=uid,
    )
    sync_day = today()
    synced = now_naive()
    if row is None:
        db.add(
            ArknightsBoxSnapshot(
                member_id=member_id,
                uid=uid,
                payload_json=blob,
                sync_date=sync_day,
                synced_at=synced,
            )
        )
    else:
        row.payload_json = blob
        row.sync_date = sync_day
        row.synced_at = synced
    db.commit()


def fetch_member_owned_chars(
    db: Session,
    member: Member,
    *,
    uid: str | None = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """返回盒子练度；默认使用当日快照，过期或缺失时拉取森空岛。"""
    if use_cache and not force_refresh:
        cached = _load_snapshot(db, member.id, uid)
        if cached is not None and "roles" in cached:
            return cached

    bind = get_bind_for_member(db, member.id)
    if bind is None:
        return {
            "status": "unbound",
            "message": "未绑定森空岛",
            "uid": None,
            "role_name": None,
            "channel_name": None,
            "owned": {},
            "roles": [],
        }

    try:
        box, role, roles = get_arknights_box_for_member(db, member, uid)
        payload = {
            "status": "ok",
            "message": None,
            "uid": box.uid,
            "role_name": role.role_name,
            "channel_name": role.channel_name,
            "owned": _owned_map_from_box(box),
            "char_count": box.char_count,
            "player_name": box.name,
            "player_level": box.level,
            "roles": [
                {
                    "uid": r.uid,
                    "role_name": r.role_name,
                    "channel_name": r.channel_name,
                }
                for r in roles
            ],
            "synced_at": now_naive().isoformat(sep=" ", timespec="seconds"),
        }
    except SklandApiError as exc:
        # 拉取失败时尽量回退到非当日快照
        stale = (
            db.query(ArknightsBoxSnapshot)
            .filter(ArknightsBoxSnapshot.member_id == member.id)
            .order_by(ArknightsBoxSnapshot.synced_at.desc())
            .first()
        )
        if stale is not None:
            try:
                old = json.loads(stale.payload_json)
                if isinstance(old, dict) and old.get("status") == "ok":
                    old = dict(old)
                    old["message"] = f"使用缓存（刷新失败：{exc.message}）"
                    return old
            except json.JSONDecodeError:
                pass
        return {
            "status": "error",
            "message": exc.message,
            "uid": None,
            "role_name": None,
            "channel_name": None,
            "owned": {},
            "roles": [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("fetch box for member %s failed", member.id)
        return {
            "status": "error",
            "message": str(exc),
            "uid": None,
            "role_name": None,
            "channel_name": None,
            "owned": {},
            "roles": [],
        }

    if payload["status"] == "ok":
        member_id = member.id
        try:
            _save_snapshot(db, member_id, payload)
        except Exception:  # noqa: BLE001
            # 先 rollback，再打日志；避免 PendingRollbackError 把接口打成 500
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
            logger.exception(
                "save arknights box snapshot failed member_id=%s", member_id
            )
    return payload


def _member_ids_with_arknights(db: Session) -> set[int]:
    """站内可判定有明日方舟角色的成员（不依赖 Steam 好友）。"""
    ids: set[int] = set()
    for (mid,) in db.query(ArknightsBoxSnapshot.member_id).distinct():
        if mid is not None:
            ids.add(int(mid))
    for (mid,) in (
        db.query(SklandCheckinLog.member_id)
        .filter(SklandCheckinLog.game_code == GAME_ARKNIGHTS)
        .distinct()
    ):
        if mid is not None:
            ids.add(int(mid))
    for (mid,) in (
        db.query(CheckinRolePref.member_id)
        .filter(
            CheckinRolePref.platform == "skland",
            CheckinRolePref.game_code == GAME_ARKNIGHTS,
        )
        .distinct()
    ):
        if mid is not None:
            ids.add(int(mid))
    for (mid,) in db.query(SklandAttendanceRaw.member_id).distinct():
        if mid is not None:
            ids.add(int(mid))
    return ids


def _viewer_member_id(db: Session, viewer: User) -> int:
    if viewer.member:
        return int(viewer.member.id)
    from app.services.member_sync import ensure_user_member

    return int(ensure_user_member(db, viewer).id)


def list_compare_candidates(db: Session, viewer: User) -> list[dict[str, Any]]:
    """可选对比成员：站内已有明日方舟账号记录者（含自己）。"""
    self_id = _viewer_member_id(db, viewer)
    candidate_ids = _member_ids_with_arknights(db)
    # 自己已绑森空岛即可出现在列表（即便尚未写出方舟日志/快照）
    self_bind = (
        db.query(SklandBind.id)
        .filter(SklandBind.member_id == self_id)
        .first()
    )
    if self_bind is not None:
        candidate_ids.add(self_id)
    if not candidate_ids:
        return []

    rows = (
        db.query(Member)
        .options(joinedload(Member.user), joinedload(Member.skland_bind))
        .filter(Member.id.in_(candidate_ids), Member.user_id.isnot(None))
        .all()
    )
    out: list[dict[str, Any]] = []
    for m in rows:
        # 仅展示仍绑定森空岛的成员；自己例外已在上面处理
        if m.skland_bind is None and m.id != self_id:
            continue
        nickname = (
            m.steam_persona_name
            or (m.user.display_name if m.user else None)
            or m.nickname
        )
        out.append(
            {
                "member_id": m.id,
                "nickname": nickname,
                "avatar_url": m.avatar_url,
                "is_self": m.id == self_id,
                "skland_bound": m.skland_bind is not None,
            }
        )
    out.sort(key=lambda x: (not x["is_self"], x["nickname"] or "", x["member_id"]))
    return out


def build_box_compare(
    db: Session,
    viewer: User,
    member_ids: list[int],
    *,
    role_uids: dict[int, str] | None = None,
) -> dict[str, Any]:
    if not member_ids:
        raise ArknightsCatalogError("请至少选择一名成员")
    if len(member_ids) > COMPARE_MAX_MEMBERS:
        raise ArknightsCatalogError(f"最多同时对比 {COMPARE_MAX_MEMBERS} 人")

    uid_map = role_uids or {}

    seen: set[int] = set()
    ordered_ids: list[int] = []
    for mid in member_ids:
        if mid in seen:
            continue
        seen.add(mid)
        ordered_ids.append(mid)

    self_id = _viewer_member_id(db, viewer)
    allowed = _member_ids_with_arknights(db)
    self_bind = (
        db.query(SklandBind.id)
        .filter(SklandBind.member_id == self_id)
        .first()
    )
    if self_bind is not None:
        allowed.add(self_id)
    for mid in ordered_ids:
        if mid not in allowed:
            raise ArknightsCatalogError(
                f"无权查看成员 {mid} 的盒子（需为站内有明日方舟账号的用户）"
            )

    operators = ensure_catalog(db)
    meta = get_catalog_meta(db)

    members = (
        db.query(Member)
        .options(joinedload(Member.user), joinedload(Member.skland_bind))
        .filter(Member.id.in_(ordered_ids))
        .all()
    )
    by_id = {m.id: m for m in members}

    catalog = [
        {
            "char_id": op.char_id,
            "name": op.name,
            "rarity": op.rarity,
            "profession": op.profession,
            "profession_label": op.profession_label,
            "avatar_url": op.avatar_url,
        }
        for op in operators
    ]

    rows: list[dict[str, Any]] = []
    for mid in ordered_ids:
        member = by_id.get(mid)
        if member is None:
            rows.append(
                {
                    "member_id": mid,
                    "nickname": f"成员#{mid}",
                    "avatar_url": None,
                    "status": "missing",
                    "message": "成员不存在",
                    "uid": None,
                    "role_name": None,
                    "channel_name": None,
                    "player_name": None,
                    "player_level": None,
                    "char_count": 0,
                    "owned": {},
                    "roles": [],
                }
            )
            continue
        nickname = (
            member.steam_persona_name
            or (member.user.display_name if member.user else None)
            or member.nickname
        )
        selected_uid = (uid_map.get(mid) or "").strip() or None
        owned_payload = fetch_member_owned_chars(db, member, uid=selected_uid)
        rows.append(
            {
                "member_id": member.id,
                "nickname": nickname,
                "avatar_url": member.avatar_url,
                "status": owned_payload["status"],
                "message": owned_payload.get("message"),
                "uid": owned_payload.get("uid"),
                "role_name": owned_payload.get("role_name"),
                "channel_name": owned_payload.get("channel_name"),
                "player_name": owned_payload.get("player_name"),
                "player_level": owned_payload.get("player_level"),
                "char_count": owned_payload.get("char_count")
                or len(owned_payload.get("owned") or {}),
                "owned": owned_payload.get("owned") or {},
                "roles": owned_payload.get("roles") or [],
            }
        )

    return {
        "catalog": catalog,
        "catalog_version": meta.source_version if meta else None,
        "catalog_synced_at": meta.synced_at.isoformat() if meta and meta.synced_at else None,
        "rows": rows,
    }


def sync_box_for_bind(db: Session, bind: SklandBind) -> dict[str, Any]:
    """强制刷新该绑定下所有明日方舟角色盒子。"""
    member = bind.member
    if member is None:
        member = db.query(Member).filter(Member.id == bind.member_id).first()
    if member is None:
        return {"ok": False, "message": "成员不存在"}

    # 先拉一次拿 roles，再逐 uid 刷新
    first = fetch_member_owned_chars(db, member, force_refresh=True)
    if first.get("status") != "ok":
        return {"ok": False, "message": first.get("message") or "同步失败", "uid": None}

    roles = first.get("roles") or []
    synced = {str(first.get("uid") or "")}
    for role in roles:
        if not isinstance(role, dict):
            continue
        uid = str(role.get("uid") or "").strip()
        if not uid or uid in synced:
            continue
        fetch_member_owned_chars(db, member, uid=uid, force_refresh=True)
        synced.add(uid)
    return {"ok": True, "uids": sorted(u for u in synced if u)}


def run_arknights_box_sync_job(db: Session) -> dict[str, Any]:
    binds = (
        db.query(SklandBind)
        .options(joinedload(SklandBind.member))
        .all()
    )
    stats: dict[str, Any] = {"total": len(binds), "ok": 0, "failed": 0, "skipped": 0}
    day = today()
    for bind in binds:
        # 当日已有任意快照则跳过，避免重复打森空岛
        exists = (
            db.query(ArknightsBoxSnapshot.id)
            .filter(
                ArknightsBoxSnapshot.member_id == bind.member_id,
                ArknightsBoxSnapshot.sync_date == day,
            )
            .first()
        )
        if exists is not None:
            stats["skipped"] += 1
            continue
        try:
            out = sync_box_for_bind(db, bind)
            if out.get("ok"):
                stats["ok"] += 1
            else:
                stats["failed"] += 1
        except Exception:  # noqa: BLE001
            logger.exception("arknights box sync failed member_id=%s", bind.member_id)
            stats["failed"] += 1
            db.rollback()
    return stats


def box_sync_job_wrapper() -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running")
    db.add(job)
    db.commit()
    try:
        stats = run_arknights_box_sync_job(db)
        job.status = "ok"
        job.message = json.dumps(stats, ensure_ascii=False)
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("arknights box sync job failed")
        job.status = "error"
        job.message = str(exc)
        job.finished_at = now_naive()
        db.commit()
    finally:
        db.close()
