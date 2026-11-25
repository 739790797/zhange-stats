"""Import official Stronghold perspectives and build the site-wide diary."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import case, func, select, tuple_, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.timeutil import day_bounds, ensure, now_naive, to_naive, today
from app.models.arknights_stronghold import (
    StrongholdMatch,
    StrongholdMatchAlias,
    StrongholdRecord,
    StrongholdRecordAlias,
    StrongholdRecordBond,
    StrongholdRole,
    StrongholdVersion,
)
from app.models.member import Member
from app.models.skland import SklandBind
from app.models.user import User
from app.schemas.stronghold import (
    StrongholdBattleData,
    StrongholdBondOut,
    StrongholdCommunityOut,
    StrongholdMatchOut,
    StrongholdMemberOut,
    StrongholdOwnOut,
    StrongholdRecordDetailOut,
    StrongholdRecordOut,
    StrongholdRoleOut,
    StrongholdScopeOut,
    StrongholdSyncOut,
)
from app.services.skland import stronghold_source
from app.services.skland.arknights_identity import (
    game_role_name,
    is_joined_arknights_role,
    prefer_game_role_name,
    resolve_game_role_names,
)
from app.services.skland.client import SklandRole
from app.services.skland.stronghold_diary import aggregate_diary
from app.services.skland.stronghold_resources import (
    display_entry,
    ensure_version,
    operator_effect,
    version_key,
    version_out,
)
from app.services.skland.stronghold_source import RoleBattle

logger = logging.getLogger(__name__)


class StrongholdError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _snapshot_order(ended_at: datetime, view_key: str | None) -> tuple[datetime, str]:
    return to_naive(ended_at), view_key or ""


def _lock_bind(db: Session, member_id: int) -> SklandBind:
    if db.get_bind().dialect.name == "sqlite":
        table = SklandBind.__table__
        db.execute(table.update().where(table.c.member_id == member_id).values(updated_at=table.c.updated_at))
    bind = db.scalar(
        select(SklandBind)
        .where(SklandBind.member_id == member_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if bind is None:
        raise StrongholdError(409, "森空岛绑定已变化，请重新同步")
    return bind


def _locked_match(db: Session, match_id: str) -> StrongholdMatch | None:
    return db.scalar(
        select(StrongholdMatch)
        .where(StrongholdMatch.id == match_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _match_role_record(db: Session, match_id: str, role_id: int) -> StrongholdRecord | None:
    return db.scalar(
        select(StrongholdRecord)
        .where(StrongholdRecord.match_id == match_id, StrongholdRecord.role_id == role_id)
        .with_for_update()
    )


def _last_record_end(db: Session, match_id: str):
    return db.scalar(
        select(StrongholdRecord.ended_at)
        .where(StrongholdRecord.match_id == match_id)
        .order_by(StrongholdRecord.ended_at.desc())
        .limit(1)
        .with_for_update()
    )


def _scene_match(
    db: Session, source: RoleBattle | StrongholdRecord, key: str, unscoped_key: str, legacy: StrongholdMatch | None
):
    by_scene = (
        select(StrongholdMatch)
        .where(StrongholdMatch.season_id == source.season_id, StrongholdMatch.scene_key.in_((key, unscoped_key)))
        .order_by((StrongholdMatch.scene_key == key).desc())
        .limit(1)
    )
    existing = db.scalar(by_scene)
    if existing is not None and (locked := _locked_match(db, existing.id)) is not None:
        return locked, False
    try:
        with db.begin_nested():
            if legacy is not None:
                legacy.scene_key = key
                db.flush()
                return legacy, False
            match = StrongholdMatch(
                id=uuid4().hex,
                source_key=key,
                scene_key=key,
                version_id=source.version_id,
                season_id=source.season_id,
                season_label=source.season_label,
                difficulty_id=source.difficulty_id,
                difficulty_label=source.difficulty_label,
                ended_at=to_naive(source.ended_at),
                mode_type=source.mode_type,
                success=False,
            )
            db.add(match)
            db.flush()
        return match, True
    except IntegrityError:
        match = db.scalar(by_scene.with_for_update().execution_options(populate_existing=True))
        if match is None:
            raise
        return match, False


def _relink_record(db: Session, record: StrongholdRecord, previous: StrongholdMatch, match: StrongholdMatch):
    linked = _match_role_record(db, match.id, record.role_id)
    if linked is not None:
        keep, discard = linked, record
        if _snapshot_order(record.ended_at, record.source_view_key) > _snapshot_order(
            linked.ended_at, linked.source_view_key
        ):
            keep, discard = record, linked
        db.execute(
            update(StrongholdRecordAlias).where(StrongholdRecordAlias.record_id == discard.id).values(record_id=keep.id)
        )
        db.add(StrongholdRecordAlias(id=discard.id, record_id=keep.id))
        db.delete(discard)
        db.flush()
        record = keep
    record.match_id = match.id
    db.flush()
    # Other legacy perspectives keep their links until they supply the same scene key themselves.
    if remaining := _last_record_end(db, previous.id):
        previous.ended_at = remaining
    else:
        db.execute(
            update(StrongholdMatchAlias).where(StrongholdMatchAlias.match_id == previous.id).values(match_id=match.id)
        )
        db.add(StrongholdMatchAlias(id=previous.id, match_id=match.id))
        db.delete(previous)
    return record


def _merge_operator(existing: dict, current: dict) -> dict:
    result = {**existing, **current}
    for field in ("equipment", "traits"):
        if field in current:
            prior = {item["id"]: item for item in existing.get(field, [])}
            result[field] = [{**prior.get(item["id"], {}), **item} for item in current[field]]
    return result


def _update_record(db: Session, record: StrongholdRecord, battle: RoleBattle) -> None:
    record.ended_at = to_naive(battle.ended_at)
    version_changed = battle.version_id is not None and battle.version_id != record.version_id
    record.version_id = battle.version_id or record.version_id
    record.difficulty_id = battle.difficulty_id
    record.difficulty_label = battle.difficulty_label
    if battle.season_label != "卫戍协议":
        record.season_label = battle.season_label
    for column, value in (
        ("mode_type", battle.mode_type),
        ("complete_state", battle.completed),
        ("pass_round", battle.pass_round),
    ):
        if value is not None:
            setattr(record, column, value)
    details = dict(record.details or {})
    if version_changed or (battle.strategy_id is not None and battle.strategy_id != record.strategy_id):
        details.pop("strategy_icon_url", None)
        details.pop("strategy_description", None)
        record.strategy_name = None
    if battle.strategy_id is not None:
        record.strategy_id = battle.strategy_id
        record.strategy_name = battle.strategy_name or record.strategy_name
    extra = battle.battle.model_dump(mode="json", exclude_none=True)
    if "bosses" in extra:
        prior = {item["id"]: item for item in details.get("bosses", [])}
        extra["bosses"] = [{**prior.get(item["id"], {}), **item} for item in extra["bosses"]]
    details.update(extra)
    record.details = details or None
    if battle.roster is not None:
        existing = {entry["id"]: entry for entry in record.roster or []}
        record.roster = [
            _merge_operator(existing.get(op.id, {}), op.model_dump(exclude_none=True)) for op in battle.roster
        ]
    if battle.bonds is not None:
        record.bonds_known = True
        old = {
            bond.bond_id: bond
            for bond in db.scalars(select(StrongholdRecordBond).where(StrongholdRecordBond.view_id == record.id))
        }
        for bond in battle.bonds:
            stored = old.pop(bond.bond_id, None)
            if stored is None:
                stored = StrongholdRecordBond(view_id=record.id, bond_id=bond.bond_id)
                db.add(stored)
            stored.name = bond.name or (None if version_changed else stored.name)
            stored.icon_url = bond.icon_url or (None if version_changed else stored.icon_url)
            stored.active = bond.active
            stored.layer = bond.layer
            stored.layer_scope = bond.layer_scope
        for stored in old.values():
            db.delete(stored)
    elif version_changed:
        for stored in db.scalars(select(StrongholdRecordBond).where(StrongholdRecordBond.view_id == record.id)):
            stored.name = None
            stored.icon_url = None


def _store_battle(db: Session, role_id: int, battle: RoleBattle, scene_key: str) -> tuple[bool, bool]:
    view_key = _digest(battle.upstream_view_id)
    snapshot_key = _digest(battle.model_dump_json())
    unscoped_key = _digest(f"scene:{battle.scene_id}")
    compatible_keys = (scene_key, unscoped_key)
    record = db.scalar(
        select(StrongholdRecord)
        .where(
            StrongholdRecord.role_id == role_id,
            StrongholdRecord.season_id == battle.season_id,
            StrongholdRecord.source_view_key == view_key,
        )
        .with_for_update()
    )
    previous = _locked_match(db, record.match_id) if record is not None else None
    if previous is not None and previous.scene_key is not None and previous.scene_key not in compatible_keys:
        raise StrongholdError(502, "该角色的官方对局标识有冲突，本次未保存")
    legacy = previous if previous is not None and previous.season_id == battle.season_id else None
    if legacy is not None and legacy.scene_key in compatible_keys and record.snapshot_key == snapshot_key:
        return False, False
    # An old unscoped match can contain records from another activity. Move just the reported record.
    incoming_order = _snapshot_order(battle.ended_at, view_key)
    source = (
        record
        if record is not None and incoming_order < _snapshot_order(record.ended_at, record.source_view_key)
        else battle
    )
    match, new_match = _scene_match(db, source, scene_key, unscoped_key, legacy)
    relinked = previous is not None and previous.id != match.id
    if relinked:
        record = _relink_record(db, record, previous, match)
    if record is None:
        record = _match_role_record(db, match.id, role_id)
    new_record = record is None
    if record is None:
        record = StrongholdRecord(
            id=uuid4().hex,
            role_id=role_id,
            match_id=match.id,
            season_id=battle.season_id,
            season_label=battle.season_label,
            version_id=battle.version_id,
            difficulty_id=battle.difficulty_id,
            difficulty_label=battle.difficulty_label,
            ended_at=to_naive(battle.ended_at),
        )
        db.add(record)
    elif incoming_order < _snapshot_order(record.ended_at, record.source_view_key):
        if relinked:
            match.ended_at = _last_record_end(db, match.id) or match.ended_at
        return new_match, False
    record.source_view_key = view_key
    record.snapshot_key = snapshot_key
    _update_record(db, record, battle)
    if match.season_id == battle.season_id:
        match.version_id = match.version_id or battle.version_id
        if battle.version_id == match.version_id and battle.season_label != "卫戍协议":
            match.season_label = battle.season_label
    match.mode_type = match.mode_type or battle.mode_type
    if match.difficulty_id == "unknown" and battle.difficulty_id != "unknown":
        match.difficulty_id, match.difficulty_label = battle.difficulty_id, battle.difficulty_label
    db.flush()
    match.ended_at = _last_record_end(db, match.id) or match.ended_at
    return new_match, new_record


def _persist_sync(
    db: Session,
    member_id: int,
    bind_id: int,
    token_enc: str,
    source_role: SklandRole,
    prepared: dict[str, RoleBattle],
    skipped: int,
    resources_available: bool,
) -> StrongholdSyncOut:
    current = _lock_bind(db, member_id)
    if current.id != bind_id or current.token_enc != token_enc:
        raise StrongholdError(409, "森空岛绑定已变化，请重新同步")
    if not is_joined_arknights_role(db, member_id, source_role.uid):
        raise StrongholdError(404, "该明日方舟角色未加入本站")
    role = db.scalar(
        select(StrongholdRole).where(
            StrongholdRole.member_id == member_id,
            StrongholdRole.channel_id == source_role.channel_master_id,
            StrongholdRole.uid == source_role.uid,
        )
    )
    synced_at = now_naive()
    if role is None:
        role = StrongholdRole(member_id=member_id, channel_id=source_role.channel_master_id, uid=source_role.uid)
        db.add(role)
    role.role_name = prefer_game_role_name(source_role.role_name, role.role_name, source_role.uid) or "未知角色"
    role.synced_at = synced_at
    versions = {(row.season_id, row.version_id) for row in prepared.values() if row.version_id}
    for activity, version in sorted(versions):
        ensure_version(db, activity, version)
    db.flush()
    new_matches = new_records = 0
    for scene_key, battle in sorted(prepared.items()):
        created_match, created_record = _store_battle(db, role.id, battle, scene_key)
        new_matches += created_match
        new_records += created_record
    result = StrongholdSyncOut(
        role_id=role.id,
        new_matches=new_matches,
        new_records=new_records,
        records_seen=len(prepared) + skipped,
        skipped=skipped,
        resources_available=resources_available,
        synced_at=ensure(synced_at),
    )
    db.commit()
    return result


def persist_battles(
    db: Session,
    member_id: int,
    bind_id: int,
    token_enc: str,
    role: SklandRole,
    battles,
    *,
    resources_available: bool = False,
) -> StrongholdSyncOut:
    prepared: dict[str, RoleBattle] = {}
    source_views: dict[tuple[str, str], RoleBattle] = {}
    skipped = 0
    for value in battles:
        battle = RoleBattle.model_validate(value)
        bond_ids = [bond.bond_id for bond in battle.bonds or []]
        if not battle.upstream_view_id.startswith(f"{role.uid}-") or len(set(bond_ids)) != len(bond_ids):
            raise StrongholdError(502, "官方战报角色或盟约不一致，本次未保存")
        if not battle.scene_id:
            skipped += 1
            continue
        view = battle.upstream_view_id
        if source_views.setdefault((battle.season_id, view), battle) != battle:
            raise StrongholdError(502, "官方战绩存在互相矛盾的重复记录，本次未保存")
        scene_key = _digest(f"scene-activity:{battle.season_id}:{battle.scene_id}")
        previous = prepared.get(scene_key)
        if previous is None or _snapshot_order(battle.ended_at, _digest(view)) > _snapshot_order(
            previous.ended_at, _digest(previous.upstream_view_id)
        ):
            prepared[scene_key] = battle
    if skipped:
        logger.warning("Stronghold skipped records without sceneId count=%d", skipped)
    for attempt in range(3):
        try:
            return _persist_sync(db, member_id, bind_id, token_enc, role, prepared, skipped, resources_available)
        except (IntegrityError, OperationalError) as exc:
            db.rollback()
            if isinstance(exc, OperationalError):
                text = str(exc.orig).lower()
                if "database is locked" not in text and (
                    not exc.orig.args or exc.orig.args[0] not in (1020, 1205, 1213)
                ):
                    raise
            if attempt == 2:
                raise StrongholdError(409, "战绩正在同步，请重试") from exc
    raise AssertionError("unreachable")


def _scope_out(row) -> StrongholdScopeOut:
    return StrongholdScopeOut(
        season_id=row.season_id,
        season_label=row.season_label,
        difficulty_id=row.difficulty_id,
        difficulty_label=row.difficulty_label,
        mode_type=row.mode_type,
        version_key=version_key(row.season_id, getattr(row, "version_id", None)),
    )


def _filters(model, season, difficulty, mode, version):
    conditions = []
    if season:
        conditions.append(model.season_id == season)
    if difficulty:
        conditions.append(model.difficulty_id == difficulty)
    if mode:
        conditions.append(model.mode_type == mode)
    if version and ":" in version:
        activity, version_id = version.split(":", 1)
        conditions.extend((model.season_id == activity, model.version_id == version_id))
    return conditions


def _scopes(db, model, *conditions):
    columns = (
        model.season_id,
        model.season_label,
        model.difficulty_id,
        model.difficulty_label,
        model.mode_type,
        model.version_id,
    )
    rows = db.execute(
        select(*columns).where(*conditions).group_by(*columns).order_by(func.max(model.ended_at).desc(), *columns)
    )
    return [_scope_out(row) for row in rows]


def _version(db, activity: str, version_id: str | None):
    return db.get(StrongholdVersion, (activity, version_id)) if version_id else None


def _record_out(db, row, *, strategy: dict | None = None) -> StrongholdRecordOut:
    if strategy is None:
        strategy = display_entry(_version(db, row.season_id, row.version_id), "strategy", row.strategy_id)
    detail = row.details or {}
    return StrongholdRecordOut(
        **_scope_out(row).model_dump(),
        id=row.id,
        match_id=row.match_id,
        ended_at=ensure(row.ended_at),
        completed=row.complete_state,
        pass_round=row.pass_round,
        strategy_id=row.strategy_id,
        strategy_name=strategy.get("name") or row.strategy_name,
        strategy_icon_url=strategy.get("icon_url") or detail.get("strategy_icon_url"),
        strategy_description=strategy.get("description") or detail.get("strategy_description"),
    )


def _record_bonds(db, ids):
    result = defaultdict(list)
    for bond in db.scalars(
        select(StrongholdRecordBond)
        .where(StrongholdRecordBond.view_id.in_(ids))
        .order_by(StrongholdRecordBond.layer.desc(), StrongholdRecordBond.bond_id)
    ):
        result[bond.view_id].append(bond)
    return result


def _record_detail(db, record, bonds, *, role_name=None, author=None, player_group_id=None, is_own=False):
    version = _version(db, record.season_id, record.version_id)
    strategy = display_entry(version, "strategy", record.strategy_id)
    result = []
    for bond in bonds.get(record.id, []) if record.bonds_known else []:
        entry = display_entry(version, "bond", bond.bond_id)
        result.append(
            StrongholdBondOut(
                bond_id=bond.bond_id,
                name=entry.get("name") or bond.name,
                description=entry.get("description"),
                icon_url=entry.get("icon_url") or bond.icon_url,
                active=bond.active,
                layer=bond.layer,
                layer_scope=bond.layer_scope,
                is_core=entry.get("is_core"),
                activation_count=entry.get("activation_count"),
                activation_rule=entry.get("activation_rule"),
                operators=entry.get("operators"),
                show_operators=entry.get("show_operators"),
            )
        )
    roster = None if record.roster is None else [dict(operator) for operator in record.roster]
    for operator in roster or []:
        unit = display_entry(version, "operator", operator["id"])
        operator.update(normal_chess_id=unit.get("normal_chess_id"), is_elite=unit.get("is_elite"))
        if (operator.get("char_id") or unit.get("char_id")) == unit.get(
            "primary_char_id"
        ) and "primary_char_id" in unit:
            for field in ("char_id", "name", "profession"):
                if operator.get(field) is None and field in unit:
                    operator[field] = unit[field]
        if operator.get("tier") is None:
            operator["tier"] = unit.get("tier")
        if operator.get("traits") is None and "traits" in unit:
            operator["traits"] = [{"id": key} for key in unit["traits"]]
        for group in ("skill", "module"):
            operator[group] = operator_effect(version, group, operator.get(f"{group}_id"), unit.get(f"{group}_level"))
        for field, group in (("equipment", "equipment"), ("traits", "trait")):
            if operator.get(field) is not None:
                operator[field] = [{**item, **display_entry(version, group, item["id"])} for item in operator[field]]
    summary = _record_out(db, record, strategy=strategy)
    facts = dict(record.details or {})
    if facts.get("bosses") is not None:
        facts["bosses"] = [{**display_entry(version, "boss_display", item["id"]), **item} for item in facts["bosses"]]
    return StrongholdRecordDetailOut(
        **summary.model_dump(),
        author=author,
        role_name=game_role_name(role_name),
        player_group_id=player_group_id,
        is_own=is_own,
        own_role_id=record.role_id if is_own else None,
        strategy_promoter=strategy.get("promoter"),
        strategy_initial_hp=strategy.get("initial_hp"),
        roster=roster,
        bonds=result if record.bonds_known else None,
        battle=StrongholdBattleData.model_validate(
            {
                **facts,
                "strategy_icon_url": summary.strategy_icon_url,
                "strategy_description": summary.strategy_description,
            }
        ),
        version=version_out(version) if version else None,
    )


def _matches_out(db, matches, member_id, *, detail=False, role_names=None):
    if not matches:
        return []
    ids = [match.id for match in matches]
    columns = (
        (StrongholdRecord,)
        if detail
        else (
            StrongholdRecord.id,
            StrongholdRecord.match_id,
            StrongholdRecord.ended_at,
            StrongholdRecord.complete_state,
            StrongholdRecord.details,
        )
    )
    rows = db.execute(
        select(
            *columns,
            Member.id.label("member_id"),
            Member.nickname,
            Member.avatar_url,
            StrongholdRole.role_name,
            StrongholdRole.channel_id,
            StrongholdRole.uid,
        )
        .select_from(StrongholdRecord)
        .join(StrongholdRole, StrongholdRole.id == StrongholdRecord.role_id)
        .join(Member, Member.id == StrongholdRole.member_id)
        .join(User, User.id == Member.user_id)
        .where(StrongholdRecord.match_id.in_(ids), User.anonymized_at.is_(None))
        .order_by(Member.id, StrongholdRecord.id)
    ).all()
    if role_names is None:
        role_names = resolve_game_role_names(
            db, {(row.member_id, row.channel_id, row.uid): row.role_name for row in rows}
        )
    bond_map = _record_bonds(db, [row[0].id for row in rows]) if detail else {}
    participants, views, own, outcomes = defaultdict(dict), defaultdict(list), {}, defaultdict(set)
    player_groups = {}
    participant_names = defaultdict(set)
    latest_team_end: dict[str, datetime] = {}
    multi_ids = {match.id for match in matches if match.mode_type == "multi"}
    for row in rows:
        record = row[0] if detail else row
        person_id, nickname, avatar_url, role_name, channel, uid = row[len(columns) :]
        name = role_names.get((person_id, channel, uid), game_role_name(role_name, uid))
        person = StrongholdMemberOut(
            id=person_id, nickname=nickname, avatar_url=avatar_url, role_names=[name] if name else []
        )
        participants[record.match_id][person_id] = person
        if name:
            participant_names[record.match_id, person_id].add(name)
        if person_id == member_id:
            own.setdefault(record.match_id, record.id)
        match_id = record.match_id
        if match_id in multi_ids:
            value = (record.details or {}).get("team_completed")
            if value is not None:
                ended_at = ensure(record.ended_at)
                previous = latest_team_end.get(match_id)
                if previous is None or ended_at > previous:
                    latest_team_end[match_id] = ended_at
                    outcomes[match_id] = {value}
                elif ended_at == previous:
                    outcomes[match_id].add(value)
        elif record.complete_state is not None:
            outcomes[match_id].add(record.complete_state)
        if detail:
            group = player_groups.setdefault((match_id, channel, uid), record.id)
            views[match_id].append(
                _record_detail(
                    db,
                    record,
                    bond_map,
                    role_name=name,
                    author=person,
                    player_group_id=group,
                    is_own=person_id == member_id,
                )
            )
    result = []
    for match in matches:
        version = _version(db, match.season_id, match.version_id)
        results = outcomes[match.id]
        success = next(iter(results)) if len(results) == 1 else None
        # Only the pre-scene format stored a whole-match result; new rows store the scene key as source_key.
        if (
            not results
            and match.mode_type is None
            and match.identity_kind == "verified"
            and match.source_key != match.scene_key
        ):
            success = match.success
        result.append(
            StrongholdMatchOut(
                **_scope_out(match).model_dump(),
                id=match.id,
                ended_at=ensure(match.ended_at),
                success=success,
                version=version_out(version) if version else None,
                participants=[
                    person.model_copy(update={"role_names": sorted(participant_names[match.id, person.id])})
                    for person in participants[match.id].values()
                ],
                views=views[match.id],
                my_record_id=own.get(match.id),
            )
        )
    return result


def _visible_views(*columns):
    return (
        select(*columns)
        .select_from(StrongholdRecord)
        .join(StrongholdRole, StrongholdRole.id == StrongholdRecord.role_id)
        .join(Member, Member.id == StrongholdRole.member_id)
        .join(User, User.id == Member.user_id)
        .where(User.anonymized_at.is_(None))
    )


def _has_record(member_id: int | None = None):
    query = _visible_views(StrongholdRecord.id).where(StrongholdRecord.match_id == StrongholdMatch.id)
    if member_id is not None:
        query = query.where(StrongholdRole.member_id == member_id)
    return query.exists()


def _diary_metrics(db, scoped, contributor):
    records = (
        _visible_views(
            StrongholdRecord.id,
            StrongholdRecord.match_id,
            StrongholdRecord.complete_state,
            StrongholdRecord.pass_round,
            StrongholdRecord.bonds_known,
            StrongholdRole.channel_id,
            StrongholdRole.uid,
            StrongholdRole.role_name,
            Member.id.label("member_id"),
            Member.nickname,
            Member.avatar_url,
        )
        .join(scoped, scoped.c.id == StrongholdRecord.match_id)
        .subquery()
    )
    bonds = db.execute(
        select(
            records.c.match_id,
            records.c.channel_id,
            records.c.uid,
            scoped.c.season_id,
            scoped.c.version_id,
            StrongholdRecordBond.bond_id,
            StrongholdRecordBond.name,
            StrongholdRecordBond.icon_url,
            StrongholdRecordBond.active,
            StrongholdRecordBond.layer,
            StrongholdRecordBond.layer_scope,
        )
        .join(records, records.c.id == StrongholdRecordBond.view_id)
        .join(scoped, scoped.c.id == records.c.match_id)
    )
    versions = {}

    def bond_display(identity):
        activity, version_id, bond_id = identity
        key = (activity, version_id)
        if key not in versions:
            versions[key] = _version(db, activity, version_id)
        version = versions[key]
        entry = display_entry(version, "bond", bond_id)
        return {
            **{field: entry[field] for field in ("name", "icon_url", "description") if field in entry},
            "version_key": version_key(activity, version_id),
            "version_label": version.label if version else version_id,
        }

    views = db.execute(select(records)).all()
    names = resolve_game_role_names(db, {(row.member_id, row.channel_id, row.uid): row.role_name for row in views})
    metrics = aggregate_diary(
        views,
        bonds,
        db.scalar(select(func.count()).select_from(scoped)) or 0,
        bond_display,
        contributor,
        names,
    )
    return metrics, names


def _versions_for(db, model, conditions, *, include_published: bool = False):
    latest = func.max(model.ended_at).label("last_played")
    rows = db.execute(
        select(model.season_id, model.version_id, latest)
        .where(
            *conditions,
            model.version_id.is_not(None),
        )
        .group_by(model.season_id, model.version_id)
    ).all()
    played = {(activity, revision): ended_at for activity, revision, ended_at in rows}
    query = select(StrongholdVersion)
    if not include_published:
        if not played:
            return []
        query = query.where(tuple_(StrongholdVersion.season_id, StrongholdVersion.version_id).in_(list(played)))
    versions = db.scalars(query.order_by(StrongholdVersion.starts_at.desc(), StrongholdVersion.version_id.desc()))
    return [version_out(row, played.get((row.season_id, row.version_id))) for row in versions]


def community(
    db, member_id, *, selected_date, season, difficulty, mode, version=None, contributor=None, offset=0, limit=12
):
    current = today()
    selected_date = selected_date or current
    start, end = (to_naive(value) for value in day_bounds(selected_date))
    day = (
        _has_record(),
        StrongholdMatch.ended_at >= start,
        StrongholdMatch.ended_at < end,
        *_filters(StrongholdMatch, None, None, None, version),
    )
    scoped = select(StrongholdMatch.id, StrongholdMatch.season_id, StrongholdMatch.version_id).where(*day).subquery()
    (ranking, popular, layers, coverage, filtered_names), names = _diary_metrics(db, scoped, contributor)
    filters = (*day, *_filters(StrongholdMatch, season, difficulty, mode, None))
    if contributor is not None:
        filters = (*filters, _has_record(contributor))
    total = db.scalar(select(func.count()).select_from(StrongholdMatch).where(*filters)) or 0
    matches = list(
        db.scalars(
            select(StrongholdMatch)
            .where(*filters)
            .order_by(StrongholdMatch.ended_at.desc(), StrongholdMatch.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return StrongholdCommunityOut(
        matches=_matches_out(db, matches, member_id, role_names=names),
        total=total,
        scopes=_scopes(db, StrongholdMatch, *day),
        versions=_versions_for(db, StrongholdMatch, (_has_record(),), include_published=True),
        date=selected_date,
        today=current,
        ranking=ranking,
        filtered_role_names=filtered_names,
        popular_bonds=popular,
        layers=layers,
        coverage=coverage,
    )


def _owned_record(member_id):
    return (
        select(1).where(StrongholdRole.id == StrongholdRecord.role_id, StrongholdRole.member_id == member_id).exists()
    )


def own_matches(
    db, member_id, *, season, difficulty, mode, version=None, role_id=None, result=None, offset=0, limit=12
):
    from app.services.skland.stronghold_sync import member_sync_status

    own = _owned_record(member_id)
    role_scope = (own, StrongholdRecord.role_id == role_id) if role_id is not None else (own,)
    scoped = (*role_scope, *_filters(StrongholdRecord, season, difficulty, mode, version))
    scoped_total, wins, known_results = db.execute(
        select(
            func.count(),
            func.count(case((StrongholdRecord.complete_state.is_(True), 1))),
            func.count(StrongholdRecord.complete_state),
        )
        .select_from(StrongholdRecord)
        .where(*scoped)
    ).one()
    result_filter = {
        "complete": StrongholdRecord.complete_state.is_(True),
        "interrupted": StrongholdRecord.complete_state.is_(False),
        "unknown": StrongholdRecord.complete_state.is_(None),
    }
    where = (*scoped, result_filter[result]) if result else scoped
    records = db.scalars(
        select(StrongholdRecord)
        .where(*where)
        .order_by(StrongholdRecord.ended_at.desc(), StrongholdRecord.id.desc())
        .offset(offset)
        .limit(limit)
    )
    roles = list(
        db.scalars(
            select(StrongholdRole)
            .where(StrongholdRole.member_id == member_id)
            .order_by(StrongholdRole.channel_id, StrongholdRole.uid)
        )
    )
    status = member_sync_status(db, member_id)
    candidates = {(member_id, row.channel_id, row.uid): row.role_name for row in status if row.channel_id and row.uid}
    for row in roles:
        key = (member_id, row.channel_id, row.uid)
        candidates[key] = prefer_game_role_name(candidates.get(key), row.role_name, row.uid)
    names = resolve_game_role_names(db, candidates)
    return StrongholdOwnOut(
        records=[_record_out(db, row) for row in records],
        total=db.scalar(select(func.count()).select_from(StrongholdRecord).where(*where)) or 0,
        scopes=_scopes(db, StrongholdRecord, *role_scope, *_filters(StrongholdRecord, None, None, None, version)),
        versions=_versions_for(db, StrongholdRecord, (own,), include_published=True),
        roles=[
            StrongholdRoleOut(
                id=row.id,
                uid=row.uid,
                channel_id=row.channel_id,
                role_name=names[(member_id, row.channel_id, row.uid)] or "未知角色",
                synced_at=ensure(row.synced_at),
            )
            for row in roles
        ],
        sync_available=stronghold_source.official_source is not None,
        sync_status=[
            row.model_copy(update={"role_name": names.get((member_id, row.channel_id, row.uid))})
            if row.channel_id and row.uid
            else row
            for row in status
        ],
        wins=wins,
        known_results=known_results,
        scoped_total=scoped_total,
    )


def get_own_record(db, view_id, member_id):
    alias = db.get(StrongholdRecordAlias, view_id)
    if alias is not None:
        view_id = alias.record_id
    row = db.execute(
        select(StrongholdRecord, StrongholdRole.role_name, StrongholdRole.channel_id, StrongholdRole.uid)
        .join(StrongholdRole, StrongholdRole.id == StrongholdRecord.role_id)
        .where(StrongholdRecord.id == view_id, StrongholdRole.member_id == member_id)
    ).one_or_none()
    if row is None:
        raise StrongholdError(404, "未找到此个人战报")
    record, role_name, channel, uid = row
    key = (member_id, channel, uid)
    name = resolve_game_role_names(db, {key: role_name})[key]
    return _record_detail(db, record, _record_bonds(db, [record.id]), role_name=name, is_own=True)


def get_report(db, match_id, member_id):
    alias = db.get(StrongholdMatchAlias, match_id)
    match_id = alias.match_id if alias else match_id
    match = db.scalar(select(StrongholdMatch).where(StrongholdMatch.id == match_id, _has_record()))
    if match is None:
        raise StrongholdError(404, "战报不存在")
    return _matches_out(db, [match], member_id, detail=True)[0]
