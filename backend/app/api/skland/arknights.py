"""森空岛：明日方舟盒子与图鉴。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.skland.helpers import _member_or_404
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.platform_deps import require_feature
from app.models.user import User
from app.schemas import (
    ArknightsAttendanceCalendarOut,
    ArknightsAttendanceDayOut,
    ArknightsBoxCompareOut,
    ArknightsCatalogOut,
    ArknightsCatalogSyncOut,
    ArknightsCompareCandidateOut,
    ArknightsCompareRoleOut,
    ArknightsCompareRowOut,
    ArknightsOperatorOut,
    ArknightsOwnedCharOut,
    ArknightsRogueCharOut,
    ArknightsRogueOut,
    ArknightsRogueOverviewOut,
    ArknightsRogueRecordOut,
    ArknightsRogueTopicOut,
    SklandRoleOut,
)
from app.schemas.checkin import CheckinAwardItem
from app.services.skland.arknights_box_compare import (
    build_box_compare,
    list_compare_candidates,
)
from app.services.skland.arknights_catalog import (
    ArknightsCatalogError,
    ensure_catalog,
    get_catalog_meta,
    list_operators,
    sync_from_upstream,
)
from app.services.skland.checkin import (
    get_arknights_attendance_calendar_for_member,
    get_arknights_rogue_for_member,
)
from app.services.skland.client import SklandApiError

router = APIRouter(tags=["skland"])


@router.get(
    "/arknights/attendance-calendar",
    response_model=ArknightsAttendanceCalendarOut,
    dependencies=[Depends(require_feature("skland.checkin"))],
)
def skland_arknights_attendance_calendar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    uid: str | None = Query(default=None, max_length=32),
    force: bool = Query(default=False),
):
    """明日方舟签到周期日历（第 N 天奖励，非公历日期）；默认读库，force 回源。"""
    member = _member_or_404(db, user)
    try:
        parsed, role, roles, synced_at, stale = (
            get_arknights_attendance_calendar_for_member(
                db, member, uid, force=force
            )
        )
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    days = [
        ArknightsAttendanceDayOut(
            day=int(d["day"]),
            claimed=bool(d["claimed"]),
            awards=[CheckinAwardItem(**a) for a in (d.get("awards") or [])],
        )
        for d in (parsed.get("days") or [])
        if isinstance(d, dict)
    ]
    return ArknightsAttendanceCalendarOut(
        uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        claimed_days=int(parsed.get("claimed_days") or 0),
        total_days=int(parsed.get("total_days") or 0),
        has_today_claim=bool(parsed.get("has_today_claim")),
        progress_reliable=bool(parsed.get("progress_reliable", True)),
        days=days,
        roles=[
            SklandRoleOut(
                game_code=r.game_code,
                game_name=r.game_name,
                uid=r.uid,
                role_name=r.role_name,
                channel_name=r.channel_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


def _rogue_record_out(rec) -> ArknightsRogueRecordOut:
    return ArknightsRogueRecordOut(
        record_id=rec.record_id,
        mode=rec.mode,
        mode_grade=rec.mode_grade,
        success=rec.success,
        score=rec.score,
        ending_text=rec.ending_text,
        start_ts=rec.start_ts,
        end_ts=rec.end_ts,
        zone_count=rec.zone_count,
        node_count=rec.node_count,
        relic_count=rec.relic_count,
        band_name=rec.band_name,
        last_stage=rec.last_stage,
        is_collect=rec.is_collect,
        squad=[
            ArknightsRogueCharOut(
                char_id=c.char_id,
                name=c.name,
                rarity=c.rarity,
                level=c.level,
                evolve_phase=c.evolve_phase,
                profession=c.profession,
            )
            for c in rec.squad
        ],
        tags=list(rec.tags or []),
    )


@router.get(
    "/arknights/rogue",
    response_model=ArknightsRogueOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_rogue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    uid: str | None = Query(default=None, max_length=32),
    topic_id: str | None = Query(
        default=None,
        max_length=32,
        description="主题 id（rogue_1…）或中文名；默认界园",
    ),
    force: bool = Query(default=False),
):
    """明日方舟肉鸽战绩：默认读库；force 或首次回源落库。"""
    member = _member_or_404(db, user)
    try:
        box, role, roles, synced_at, stale = get_arknights_rogue_for_member(
            db, member, uid, topic_id=topic_id, force=force
        )
    except SklandApiError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    ov = box.overview
    return ArknightsRogueOut(
        uid=role.uid,
        role_name=role.role_name,
        channel_name=role.channel_name,
        topic_id=box.topic_id,
        topic_name=box.topic_name,
        topics=[
            ArknightsRogueTopicOut(
                topic_id=t.topic_id,
                name=t.name,
                selected=t.selected,
                pic=t.pic,
            )
            for t in box.topics
        ],
        overview=ArknightsRogueOverviewOut(
            mode=ov.mode,
            mode_grade=ov.mode_grade,
            score=ov.score,
            bp_level=ov.bp_level,
            medal_current=ov.medal_current,
            medal_count=ov.medal_count,
            clear_difficulty=ov.clear_difficulty,
            clear_grade=ov.clear_grade,
            invest=ov.invest,
            relic=ov.relic,
            game_count=ov.game_count,
        ),
        records=[_rogue_record_out(r) for r in box.records],
        favour_records=[_rogue_record_out(r) for r in box.favour_records],
        roles=[
            SklandRoleOut(
                game_code=r.game_code,
                game_name=r.game_name,
                uid=r.uid,
                role_name=r.role_name,
                channel_name=r.channel_name,
            )
            for r in roles
        ],
        synced_at=synced_at.isoformat() if synced_at else None,
        stale=stale,
    )


@router.get(
    "/arknights/catalog",
    response_model=ArknightsCatalogOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """干员图鉴（可招募干员全集）。空库时自动从上游同步一次。"""
    _ = user
    try:
        ensure_catalog(db)
    except ArknightsCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    operators = [
        ArknightsOperatorOut(
            char_id=op.char_id,
            name=op.name,
            rarity=op.rarity,
            profession=op.profession,
            profession_label=op.profession_label,
            avatar_url=op.avatar_url,
        )
        for op in list_operators(db)
    ]
    meta = get_catalog_meta(db)
    return ArknightsCatalogOut(
        operators=operators,
        operator_count=len(operators),
        source_version=meta.source_version if meta else None,
        synced_at=meta.synced_at.isoformat() if meta and meta.synced_at else None,
    )


@router.post(
    "/arknights/catalog/sync",
    response_model=ArknightsCatalogSyncOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_catalog_sync(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """管理员：从 ArknightsGameResource 同步 character_table。"""
    try:
        result = sync_from_upstream(db)
    except ArknightsCatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ArknightsCatalogSyncOut(
        operator_count=int(result["operator_count"]),
        source_version=result.get("source_version"),
        synced_at=result.get("synced_at"),
    )


@router.get(
    "/arknights/box/compare-candidates",
    response_model=list[ArknightsCompareCandidateOut],
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_compare_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """盒子对比可选成员（站内有明日方舟账号的用户）。"""
    _member_or_404(db, user)
    rows = list_compare_candidates(db, user)
    return [ArknightsCompareCandidateOut(**r) for r in rows]


@router.get(
    "/arknights/box/compare",
    response_model=ArknightsBoxCompareOut,
    dependencies=[Depends(require_feature("skland.arknights"))],
)
def skland_arknights_box_compare(
    member_ids: str = Query(..., description="逗号分隔的成员 id，最多 5 人"),
    role_uids: str | None = Query(
        default=None,
        description="可选，格式 memberId:uid,memberId:uid，指定各成员渠道服角色",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """多用户盒子对比：统一图鉴顺序，未拥有不在 owned 中。"""
    _member_or_404(db, user)
    ids: list[int] = []
    for part in member_ids.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效的 member_id: {part}") from exc

    uid_map: dict[int, str] = {}
    if role_uids:
        for part in role_uids.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            mid_raw, _, uid_raw = part.partition(":")
            try:
                mid = int(mid_raw.strip())
            except ValueError:
                continue
            uid = uid_raw.strip()
            if uid:
                uid_map[mid] = uid

    try:
        data = build_box_compare(db, user, ids, role_uids=uid_map)
    except ArknightsCatalogError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ArknightsBoxCompareOut(
        catalog=[ArknightsOperatorOut(**c) for c in data["catalog"]],
        catalog_version=data.get("catalog_version"),
        catalog_synced_at=data.get("catalog_synced_at"),
        rows=[
            ArknightsCompareRowOut(
                member_id=r["member_id"],
                nickname=r["nickname"],
                avatar_url=r.get("avatar_url"),
                status=r["status"],
                message=r.get("message"),
                uid=r.get("uid"),
                role_name=r.get("role_name"),
                channel_name=r.get("channel_name"),
                player_name=r.get("player_name"),
                player_level=r.get("player_level"),
                char_count=r.get("char_count") or 0,
                owned={
                    cid: ArknightsOwnedCharOut(**owned)
                    for cid, owned in (r.get("owned") or {}).items()
                },
                roles=[
                    ArknightsCompareRoleOut(**role)
                    for role in (r.get("roles") or [])
                ],
            )
            for r in data["rows"]
        ],
    )
