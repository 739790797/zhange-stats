"""Durable, shared queue for bound Stronghold roles and official resources."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import partial
from random import randint

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.timeutil import ensure, now_naive, to_naive
from app.models.arknights_stronghold import (
    StrongholdActivity,
    StrongholdRole,
    StrongholdSyncControl,
    StrongholdSyncTarget,
    StrongholdVersion,
)
from app.models.skland import SklandBind
from app.models.member import Member
from app.models.user import User
from app.schemas.stronghold import StrongholdSyncIn, StrongholdSyncStatus
from app.services.job_execution_lock import JobExecutionBusy, job_execution_lock
from app.services.platform_features import is_feature_enabled
from app.services.scheduler_config import STRONGHOLD_SYNC_JOB_ID, load_scheduler_config
from app.services.skland import stronghold_source as source
from app.services.skland.arknights_identity import (
    is_joined_arknights_role,
    joined_arknights_uids,
    prefer_game_role_name,
    stronghold_binding_key,
)
from app.services.skland.attendance import list_roles
from app.services.skland.checkin import _looks_like_skland_auth_error, _session_for_bind, get_bind_for_member
from app.services.skland.client import GAME_ARKNIGHTS, SklandApiError, SklandRole, background_request_gate
from app.services.skland.session_cache import invalidate_skland_session
from app.services.skland.stronghold import StrongholdError, _lock_bind, persist_battles
from app.services.skland.stronghold_resources import (
    archive_assets,
    cached_source_versions,
    discover_activity_versions,
    ensure_version,
    save_game_catalog,
    save_resources,
)

from app.services.upstream_repos import RepoError

logger = logging.getLogger(__name__)
JOB_ID = STRONGHOLD_SYNC_JOB_ID
FEATURE = "skland.arknights.stronghold"
_ROLE_DISCOVERY = timedelta(days=1)
_ROLE_FLOOR = timedelta(minutes=5)
_ACTIVE_WINDOW = timedelta(hours=2)
_ACTIVITY_GRACE = timedelta(days=2)
_REQUEST_INTERVAL = 3.0
_MAX_TASKS_PER_TICK = 8


class _RequestGate:
    def __init__(self):
        self.last_started = -float("inf")

    def __call__(self):
        delay = self.last_started + _REQUEST_INTERVAL - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.last_started = time.monotonic()


def _key(bind: SklandBind) -> str:
    return stronghold_binding_key(bind.token_enc)


def _add_target(db, bind, now, channel="", uid="", role_name=""):
    target = StrongholdSyncTarget(
        bind_id=bind.id,
        channel_id=channel,
        uid=uid,
        binding_key=_key(bind),
        role_name=role_name[:96],
        due_at=now,
        status="queued",
    )
    db.add(target)
    return target


def _discover_roles(db: Session, bind: SklandBind, discovery: StrongholdSyncTarget, roles, now: datetime):
    seen = set()
    recorded = {
        (row.channel_id, row.uid): row
        for row in db.scalars(select(StrongholdRole).where(StrongholdRole.member_id == bind.member_id))
    }
    targets = {
        (target.channel_id, target.uid): target
        for target in db.scalars(
            select(StrongholdSyncTarget).where(StrongholdSyncTarget.bind_id == bind.id, StrongholdSyncTarget.uid != "")
        )
    }
    for role in roles:
        channel, uid = role.channel_master_id, role.uid
        if role.game_code != GAME_ARKNIGHTS or channel not in ("1", "2") or not re.fullmatch(r"[0-9]{1,32}", uid):
            continue
        identity = (channel, uid)
        if identity in seen:
            continue
        seen.add(identity)
        target = targets.get(identity)
        if target is None:
            _add_target(db, bind, now, channel, uid, role.role_name)
        else:
            target.role_name = prefer_game_role_name(role.role_name, target.role_name, uid) or ""
        if (existing := recorded.get(identity)) is not None:
            existing.role_name = prefer_game_role_name(role.role_name, existing.role_name, uid) or "未知角色"
    for identity, target in targets.items():
        if identity not in seen:
            db.delete(target)
    discovery.status = "idle"
    discovery.due_at = now + _ROLE_DISCOVERY
    discovery.last_success_at = now
    discovery.failures = 0
    discovery.requested = False


def register_binding_roles(db: Session, bind: SklandBind, roles) -> None:
    """The bind transaction already has an authenticated role list."""
    if not is_feature_enabled(db, FEATURE):
        return
    db.flush()
    db.execute(delete(StrongholdSyncTarget).where(StrongholdSyncTarget.bind_id == bind.id))
    now = now_naive()
    discovery = _add_target(db, bind, now)
    _discover_roles(db, bind, discovery, roles, now)


def _reset_discovery(db: Session, bind: SklandBind, now: datetime) -> StrongholdSyncTarget:
    db.execute(delete(StrongholdSyncTarget).where(StrongholdSyncTarget.bind_id == bind.id))
    return _add_target(db, bind, now)


def _seed_existing(db: Session, now: datetime) -> None:
    binds = db.execute(
        select(SklandBind.member_id, SklandBind.id, SklandBind.token_enc)
        .join(Member, Member.id == SklandBind.member_id)
        .join(User, User.id == Member.user_id)
        .where(User.anonymized_at.is_(None))
        .order_by(SklandBind.id)
    ).all()
    discoveries = dict(
        db.execute(
            select(StrongholdSyncTarget.bind_id, StrongholdSyncTarget.binding_key).where(StrongholdSyncTarget.uid == "")
        ).all()
    )
    db.commit()
    for member_id, bind_id, token_enc in binds:
        if discoveries.get(bind_id) == stronghold_binding_key(token_enc):
            continue
        try:
            bind = _lock_bind(db, member_id)
        except StrongholdError:
            db.rollback()
            continue
        existing = db.get(StrongholdSyncTarget, (bind.id, "", ""), populate_existing=True)
        if existing is None or existing.binding_key != _key(bind):
            _reset_discovery(db, bind, now + timedelta(seconds=randint(0, 55)))
        db.commit()


def _status(row: StrongholdSyncTarget, retry_until=None) -> StrongholdSyncStatus:
    state = row.status if row.uid or row.status in ("retrying", "reauth") else "discovering"
    next_sync = None if state == "reauth" else max(row.due_at, retry_until or row.due_at)
    return StrongholdSyncStatus(
        channel_id=row.channel_id or None,
        uid=row.uid or None,
        role_name=row.role_name or None,
        state=state,
        last_success_at=ensure(row.last_success_at) if row.last_success_at else None,
        next_sync_at=ensure(next_sync) if next_sync else None,
    )


def member_sync_status(db: Session, member_id: int | None) -> list[StrongholdSyncStatus]:
    if member_id is None or (bind := get_bind_for_member(db, member_id)) is None:
        return []
    included = db.scalars(joined_arknights_uids(member_id)).all()
    if not included:
        return []
    rows = list(
        db.scalars(
            select(StrongholdSyncTarget)
            .where(
                StrongholdSyncTarget.bind_id == bind.id,
                StrongholdSyncTarget.binding_key == _key(bind),
                or_(StrongholdSyncTarget.uid == "", StrongholdSyncTarget.uid.in_(included)),
            )
            .order_by(StrongholdSyncTarget.channel_id, StrongholdSyncTarget.uid)
        )
    )
    control = db.get(StrongholdSyncControl, 1)
    retry_until = control.retry_until if control else None
    if not rows:
        return [StrongholdSyncStatus(state="discovering")]
    roles = [row for row in rows if row.uid]
    if roles:
        return [_status(row, retry_until) for row in roles]
    if rows[0].status != "idle":
        return [_status(rows[0], retry_until)]
    return []


def enqueue(db: Session, member_id: int, selection: StrongholdSyncIn) -> StrongholdSyncStatus:
    if source.official_source is None:
        raise StrongholdError(503, "卫戍协议战绩同步暂不可用")
    if get_bind_for_member(db, member_id) is None:
        raise StrongholdError(404, "尚未绑定森空岛")
    bind = _lock_bind(db, member_id)
    if not is_joined_arknights_role(db, member_id, selection.uid):
        raise StrongholdError(404, "该明日方舟角色未加入本站")
    now = now_naive()
    discovery = db.get(StrongholdSyncTarget, (bind.id, "", ""))
    if discovery is None or discovery.binding_key != _key(bind):
        discovery = _reset_discovery(db, bind, now)
        row = None
    else:
        row = db.get(StrongholdSyncTarget, (bind.id, selection.channel_id, selection.uid))
    if row is None:
        if discovery.status == "idle":
            raise StrongholdError(404, "森空岛绑定下未找到该服务器角色")
        row = discovery
    if row.status not in ("reauth", "syncing"):
        row.requested = True
        floor = row.last_attempt_at + _ROLE_FLOOR if row.last_attempt_at else now
        if row.status != "retrying":
            row.due_at = max(now, floor)
            row.status = "queued"
    control = db.get(StrongholdSyncControl, 1)
    response = _status(row, control.retry_until if control else None)
    db.commit()
    return response


def _control(db: Session) -> StrongholdSyncControl:
    control = db.get(StrongholdSyncControl, 1)
    if control is None:
        control = StrongholdSyncControl(id=1)
        db.add(control)
        db.flush()
    return control


def _activity(db, activity_id, now):
    row = db.get(StrongholdActivity, activity_id)
    if row is None:
        row = StrongholdActivity(id=activity_id, resource_due_at=now)
        db.add(row)
        db.flush()
    return row


def _refresh_activity_catalog(db, control, now, cfg):
    if control.discovery_due_at is not None and control.discovery_due_at > now:
        return
    try:
        versions = discover_activity_versions()
    except (OSError, RepoError, ValueError):
        versions = []
    grouped = {}
    for activity, version, meta, catalog in versions:
        row = ensure_version(db, activity, version, meta)
        save_game_catalog(row, catalog, now)
        grouped.setdefault(activity, []).append(row)
    for activity, entries in grouped.items():
        row = _activity(db, activity, now)
        starts = [entry.starts_at for entry in entries if entry.starts_at]
        ends = [entry.ends_at for entry in entries if entry.ends_at]
        row.starts_at = min(starts, default=row.starts_at)
        row.ends_at = max(ends, default=row.ends_at) if len(ends) == len(entries) else None
    overrides = cfg.get("activity_ids", [])
    for activity in overrides:
        _activity(db, activity, now)
    if not grouped and not list(db.scalars(select(StrongholdActivity.id).limit(1))):
        _activity(db, source._ACTIVITY_ID, now)
    control.discovery_due_at = now + timedelta(minutes=15)
    db.commit()


def _active_activities(db, now, overrides):
    return list(
        db.scalars(
            select(StrongholdActivity.id)
            .where(
                or_(
                    StrongholdActivity.id.in_(overrides),
                    (
                        or_(StrongholdActivity.starts_at.is_(None), StrongholdActivity.starts_at <= now)
                        & or_(StrongholdActivity.ends_at.is_(None), StrongholdActivity.ends_at >= now - _ACTIVITY_GRACE)
                    ),
                )
            )
            .order_by(StrongholdActivity.id)
        )
    )


def _auth_error(error: SklandApiError) -> bool:
    return error.code in (401, 403, 10000) or _looks_like_skland_auth_error(error.message)


def _backoff_at(error: SklandApiError, now: datetime) -> datetime:
    value = error.retry_after or ""
    if value.isascii() and value.isdigit():
        try:
            return now + timedelta(seconds=max(1, int(value)))
        except (OverflowError, ValueError):
            pass
    try:
        return max(now + timedelta(seconds=1), to_naive(parsedate_to_datetime(value)))
    except (ValueError, TypeError, OverflowError):
        return now + timedelta(minutes=15)


def _renew_on_auth(db, bind, fetch):
    try:
        return fetch(_session_for_bind(db, bind))
    except SklandApiError as exc:
        if not _auth_error(exc):
            raise
    invalidate_skland_session(bind.member_id)
    return fetch(_session_for_bind(db, bind))


def _sync_history(db, bind, identity, role_name, cfg):
    bind_id, channel, uid = identity
    member_id, token_enc = bind.member_id, bind.token_enc
    role = SklandRole(GAME_ARKNIGHTS, "明日方舟", uid, role_name, "", channel)
    newest = None
    for activity in _active_activities(db, now_naive(), cfg["activity_ids"]):
        versions = cached_source_versions(db, activity)
        fetch = partial(source.official_source, role=role, activity_id=activity, versions=versions)
        batch = _renew_on_auth(db, bind, fetch)
        records = batch.records
        missing = {
            (battle.season_id, battle.version_id)
            for battle in records
            if battle.scene_id
            and battle.version_id
            and (battle.season_id != activity or battle.version_id not in versions)
        }
        persist_battles(db, member_id, bind_id, token_enc, role, records, resources_available=bool(versions))
        for discovered_activity, version in sorted(missing):
            archived = db.get(StrongholdVersion, (discovered_activity, version))
            if archived is None:  # This version is only present on snapshots that were not kept.
                continue
            row = _activity(db, discovered_activity, now_naive())
            # Fetch a newly encountered catalog immediately. A failed refresh keeps its retry deadline.
            if (
                not archived.catalog
                and row.last_resource_at is not None
                and row.resource_due_at > row.last_resource_at + timedelta(hours=23)
            ):
                row.resource_due_at = now_naive()
        db.commit()
        dates = [to_naive(record.ended_at) for record in records if record.scene_id]
        if dates:
            newest = max([*dates, newest] if newest else dates)
    return newest


def _attempt(db, target, cfg):
    now = now_naive()
    identity = (target.bind_id, target.channel_id, target.uid)
    binding_key = target.binding_key
    role_name = target.role_name
    member_id = db.scalar(select(SklandBind.member_id).where(SklandBind.id == target.bind_id))
    db.commit()
    try:
        bind = _lock_bind(db, member_id) if member_id is not None else None
    except StrongholdError:
        bind = None
    target = db.get(StrongholdSyncTarget, identity, populate_existing=True) if bind is not None else None
    if bind is None or bind.id != identity[0] or binding_key != _key(bind) or target is None:
        db.rollback()
        return False
    if identity[2] and not is_joined_arknights_role(db, bind.member_id, identity[2]):
        db.rollback()
        return False
    target.status = "syncing"
    target.requested = False
    target.last_attempt_at = now
    target.due_at = now + _ROLE_FLOOR  # A restarted process can reclaim this task.
    db.commit()
    try:
        if identity[2]:
            newest = _sync_history(db, bind, identity, role_name, cfg)
        else:
            roles = _renew_on_auth(db, bind, list_roles)
        bind = _lock_bind(db, member_id)
        if bind.id != identity[0] or _key(bind) != binding_key:
            db.rollback()
            return False
        current = db.get(StrongholdSyncTarget, identity, populate_existing=True)
        if current is None:
            db.rollback()
            return False
        now = now_naive()
        if identity[2]:
            if newest is not None and (current.latest_battle_at is None or newest > current.latest_battle_at):
                current.latest_battle_at = newest
            active = current.latest_battle_at and current.latest_battle_at >= now - _ACTIVE_WINDOW
            minutes = cfg["active_interval_minutes"] if active else cfg["interval_minutes"]
            current.due_at = now + timedelta(minutes=minutes, seconds=randint(0, 25))
            current.status, current.failures, current.last_success_at = "idle", 0, now
        else:
            _discover_roles(db, bind, current, roles, now)
        db.commit()
    except (SklandApiError, StrongholdError) as exc:
        db.rollback()
        try:
            bind = _lock_bind(db, member_id)
        except StrongholdError:
            bind = None
        current = (
            db.get(StrongholdSyncTarget, identity, populate_existing=True)
            if bind is not None and bind.id == identity[0] and _key(bind) == binding_key
            else None
        )
        if isinstance(exc, SklandApiError) and exc.code == 429:
            control = _control(db)
            control.retry_until = _backoff_at(exc, now_naive())
        if current is not None and current.binding_key == binding_key:
            current.failures += 1
            if isinstance(exc, SklandApiError) and _auth_error(exc):
                for row in db.scalars(
                    select(StrongholdSyncTarget).where(
                        StrongholdSyncTarget.bind_id == identity[0],
                        StrongholdSyncTarget.binding_key == binding_key,
                    )
                ):
                    row.status = "reauth"
            else:
                delay = (5, 15, 60)[min(current.failures - 1, 2)]
                current.due_at = now_naive() + timedelta(minutes=delay, seconds=randint(0, 25))
                current.status = "retrying"
        db.commit()
        logger.warning("Stronghold sync deferred kind=%s code=%s", type(exc).__name__, getattr(exc, "code", None))
        return False
    return True


def _refresh_one_resource(db, cfg):
    now = now_naive()
    due = db.scalar(
        select(StrongholdActivity)
        .where(
            StrongholdActivity.id.in_(_active_activities(db, now, cfg["activity_ids"])),
            StrongholdActivity.resource_due_at <= now,
        )
        .order_by(StrongholdActivity.resource_due_at)
        .limit(1)
    )
    bind = db.scalar(
        select(SklandBind)
        .join(StrongholdSyncTarget, StrongholdSyncTarget.bind_id == SklandBind.id)
        .join(Member, Member.id == SklandBind.member_id)
        .join(User, User.id == Member.user_id)
        .where(
            StrongholdSyncTarget.uid.in_(joined_arknights_uids(SklandBind.member_id)),
            StrongholdSyncTarget.status == "idle",
            User.anonymized_at.is_(None),
        )
        .order_by(StrongholdSyncTarget.last_success_at.desc())
        .limit(1)
    )
    if due is None or bind is None:
        return False
    activity = due.id
    try:
        versions = _renew_on_auth(db, bind, lambda session: source.fetch_official_resources(session, activity))
        now = now_naive()
        due = db.get(StrongholdActivity, activity)
        if versions:
            save_resources(db, activity, versions, now)
            due.last_resource_at = now
        due.resource_due_at = now + (timedelta(days=1) if versions else timedelta(hours=1))
    except SklandApiError as exc:
        due = db.get(StrongholdActivity, activity)
        if exc.code == 429:
            control = _control(db)
            control.retry_until = _backoff_at(exc, now_naive())
            due.resource_due_at = control.retry_until
        else:
            due.resource_due_at = now_naive() + timedelta(hours=1)
    db.commit()
    return True


def _run_tick(db: Session, cfg) -> bool:
    now = now_naive()
    control = _control(db)
    _refresh_activity_catalog(db, control, now, cfg)
    _seed_existing(db, now)
    deadline = time.monotonic() + 40
    did_work = False
    for _ in range(_MAX_TASKS_PER_TICK):
        control = db.get(StrongholdSyncControl, 1, populate_existing=True)
        if control.retry_until and control.retry_until > now_naive():
            return did_work
        if time.monotonic() >= deadline:
            return did_work
        target = db.scalar(
            select(StrongholdSyncTarget)
            .join(SklandBind, SklandBind.id == StrongholdSyncTarget.bind_id)
            .join(Member, Member.id == SklandBind.member_id)
            .join(User, User.id == Member.user_id)
            .where(
                StrongholdSyncTarget.due_at <= now_naive(),
                StrongholdSyncTarget.status != "reauth",
                or_(
                    StrongholdSyncTarget.uid == "",
                    StrongholdSyncTarget.uid.in_(joined_arknights_uids(SklandBind.member_id)),
                ),
                User.anonymized_at.is_(None),
            )
            .order_by(
                StrongholdSyncTarget.requested.desc(),
                StrongholdSyncTarget.due_at,
                StrongholdSyncTarget.bind_id,
                StrongholdSyncTarget.channel_id,
                StrongholdSyncTarget.uid,
            )
            .limit(1)
        )
        if target is None:
            break
        did_work = _attempt(db, target, cfg) or did_work
    control = db.get(StrongholdSyncControl, 1, populate_existing=True)
    if time.monotonic() < deadline and (not control.retry_until or control.retry_until <= now_naive()):
        did_work = _refresh_one_resource(db, cfg) or did_work
    if time.monotonic() < deadline:
        did_work = bool(archive_assets(db, deadline=deadline)) or did_work
    return did_work


def stronghold_sync_job_wrapper() -> bool:
    try:
        with job_execution_lock(JOB_ID), SessionLocal() as db:
            if source.official_source is None or not is_feature_enabled(db, FEATURE):
                return False
            cfg = load_scheduler_config(db)[JOB_ID]
            token = background_request_gate.set(_RequestGate())
            try:
                return _run_tick(db, cfg)
            finally:
                background_request_gate.reset(token)
    except JobExecutionBusy:
        return False
