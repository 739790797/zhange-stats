"""战局准备房间 REST + WebSocket。"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session

from app.api.guides.schemas import (
    TarkovRaidRoomClaimsIn,
    TarkovRaidRoomDetailOut,
    TarkovRaidRoomObjectiveDonesIn,
    TarkovRaidRoomGameModeIn,
    TarkovRaidRoomJoinIn,
    TarkovRaidRoomLobbyOut,
    TarkovRaidRoomMapIn,
    TarkovRaidRoomMarkIn,
    TarkovRaidRoomPasswordIn,
    TarkovRaidRoomTaskProgressIn,
)
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.platform_deps import require_feature
from app.models.user import User
from app.services.tarkov import raid_room_ws as room_ws_svc
from app.services.tarkov import raid_rooms as rooms_svc
from app.services.tarkov.raid_room_hub import hub

router = APIRouter()
_FEATURE = Depends(require_feature("guides.tarkov"))


def _raise(exc: rooms_svc.RaidRoomError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _publish(public_id: str, event: str, snapshot: dict, extra: dict | None = None) -> None:
    payload = {"event": event, "snapshot": snapshot}
    if extra:
        payload.update(extra)
    payload["online_user_ids"] = list(hub.online_user_ids(public_id))
    hub.publish(public_id, payload)


@router.get(
    "/raid-rooms",
    response_model=TarkovRaidRoomLobbyOut,
    dependencies=[_FEATURE],
)
def list_tarkov_raid_rooms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomLobbyOut:
    online_by_public_id = {
        pid: hub.online_user_ids(pid)
        for pid in set(rooms_svc.SLOT_PUBLIC_IDS) | hub.known_public_ids()
    }
    data = rooms_svc.list_live_rooms(
        db, viewer=user, online_by_public_id=online_by_public_id
    )
    db.commit()
    return TarkovRaidRoomLobbyOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/map",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def set_tarkov_raid_room_map(
    public_id: str,
    body: TarkovRaidRoomMapIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.set_room_map(
            db,
            public_id,
            user,
            body.map,
            online_user_ids=hub.online_user_ids(public_id),
            log_phases=hub.log_phases(public_id),
        )
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    _publish(public_id, "snapshot", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.get(
    "/raid-rooms/{public_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def get_tarkov_raid_room(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.get_room(
            db,
            public_id,
            user,
            online_user_ids=hub.online_user_ids(public_id),
        )
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/join",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def join_tarkov_raid_room(
    public_id: str,
    body: TarkovRaidRoomJoinIn = Body(default_factory=TarkovRaidRoomJoinIn),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    payload = body
    try:
        data, joined_now, vacated = rooms_svc.join_room(
            db,
            public_id,
            user,
            game_mode=payload.game_mode,
            password=payload.password,
        )
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    for snap in vacated:
        vacated_id = str(snap.get("public_id") or "").strip()
        if vacated_id:
            _publish(
                vacated_id,
                "member_leave",
                snap,
                extra={"user_id": user.id},
            )
    if joined_now:
        _publish(
            public_id,
            "member_join",
            data,
            extra={"user_id": user.id, "display_name": user.display_name},
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/game-mode",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def set_tarkov_raid_room_game_mode(
    public_id: str,
    body: TarkovRaidRoomGameModeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.set_room_game_mode(db, public_id, user, body.game_mode)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    _publish(public_id, "snapshot", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/password",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def set_tarkov_raid_room_password(
    public_id: str,
    body: TarkovRaidRoomPasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.set_room_password(db, public_id, user, body.password)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    _publish(public_id, "snapshot", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/leave",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def leave_tarkov_raid_room(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.leave_room(db, public_id, user)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    _publish(public_id, "member_leave", data, extra={"user_id": user.id})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/reset",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def reset_tarkov_raid_room(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.reset_room(db, public_id, user)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    _publish(public_id, "reset", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.delete(
    "/raid-rooms/{public_id}/members/{user_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def remove_tarkov_raid_room_member(
    public_id: str,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.remove_member(db, public_id, user, user_id)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    _publish(public_id, "member_leave", data, extra={"user_id": user_id})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.put(
    "/raid-rooms/{public_id}/task-progress",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def put_tarkov_raid_room_task_progress(
    public_id: str,
    body: TarkovRaidRoomTaskProgressIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.set_member_task_progress(
            db,
            public_id,
            user,
            body.started_ids,
            body.done_ids,
        )
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    _publish(public_id, "task_progress", data, extra={"user_id": user.id})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.put(
    "/raid-rooms/{public_id}/claims/{task_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def claim_tarkov_raid_room_task(
    public_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, added = rooms_svc.claim_task(db, public_id, user, task_id)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    if added:
        _publish(
            public_id,
            "claim_add",
            data,
            extra={"task_id": task_id, "user_id": user.id},
        )
    else:
        _publish(public_id, "snapshot", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/claims/from-progress",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def seed_tarkov_raid_room_claims_from_progress(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, added = rooms_svc.seed_claims_from_progress(db, public_id, user)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if added:
        _publish(public_id, "claim_add", data, extra={"user_id": user.id})
    else:
        _publish(public_id, "snapshot", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/claims",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def claim_tarkov_raid_room_tasks(
    public_id: str,
    body: TarkovRaidRoomClaimsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, added = rooms_svc.claim_tasks(
            db, public_id, user, body.task_ids[:40]
        )
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if added:
        _publish(public_id, "claim_add", data, extra={"user_id": user.id})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.delete(
    "/raid-rooms/{public_id}/claims/{task_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def unclaim_tarkov_raid_room_task(
    public_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, removed = rooms_svc.unclaim_task(db, public_id, user, task_id)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    if removed:
        _publish(
            public_id,
            "claim_remove",
            data,
            extra={"task_id": task_id, "user_id": user.id},
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.put(
    "/raid-rooms/{public_id}/key-brings/{item_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def bring_tarkov_raid_room_key(
    public_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, added = rooms_svc.bring_key(db, public_id, user, item_id)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if added:
        _publish(
            public_id,
            "key_bring_add",
            data,
            extra={"item_id": item_id, "user_id": user.id},
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.delete(
    "/raid-rooms/{public_id}/key-brings/{item_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def unbring_tarkov_raid_room_key(
    public_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, removed = rooms_svc.unbring_key(db, public_id, user, item_id)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if removed:
        _publish(
            public_id,
            "key_bring_remove",
            data,
            extra={"item_id": item_id, "user_id": user.id},
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.put(
    "/raid-rooms/{public_id}/objective-dones",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def mark_tarkov_raid_room_objectives_done(
    public_id: str,
    body: TarkovRaidRoomObjectiveDonesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    pairs = [(item.task_id, item.objective_id) for item in body.items]
    try:
        data, added = rooms_svc.mark_objectives_done(db, public_id, user, pairs)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if added:
        _publish(
            public_id,
            "objective_done_add",
            data,
            extra={"items": [{"task_id": tid, "objective_id": oid} for tid, oid in added], "user_id": user.id},
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.put(
    "/raid-rooms/{public_id}/objective-dones/{task_id}/{objective_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def mark_tarkov_raid_room_objective_done(
    public_id: str,
    task_id: str,
    objective_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, added = rooms_svc.mark_objective_done(
            db, public_id, user, task_id, objective_id
        )
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if added:
        _publish(
            public_id,
            "objective_done_add",
            data,
            extra={
                "task_id": task_id,
                "objective_id": objective_id,
                "user_id": user.id,
            },
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.delete(
    "/raid-rooms/{public_id}/objective-dones/{task_id}/{objective_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def unmark_tarkov_raid_room_objective_done(
    public_id: str,
    task_id: str,
    objective_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, removed = rooms_svc.unmark_objective_done(
            db, public_id, user, task_id, objective_id
        )
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if removed:
        _publish(
            public_id,
            "objective_done_remove",
            data,
            extra={
                "task_id": task_id,
                "objective_id": objective_id,
                "user_id": user.id,
            },
        )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/marks",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def add_tarkov_raid_room_mark(
    public_id: str,
    body: TarkovRaidRoomMarkIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, mark = rooms_svc.add_mark(
            db,
            public_id,
            user,
            kind=body.kind,
            floor=body.floor,
            x=body.x,
            z=body.z,
            x2=body.x2,
            z2=body.z2,
            points=body.points,
        )
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    _publish(public_id, "mark_add", data, extra={"mark": mark})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.delete(
    "/raid-rooms/{public_id}/marks/undo",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def undo_tarkov_raid_room_mark(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, mark_id = rooms_svc.undo_own_mark(db, public_id, user)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if mark_id is not None:
        _publish(public_id, "mark_remove", data, extra={"mark_id": mark_id})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.delete(
    "/raid-rooms/{public_id}/marks/{mark_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def remove_tarkov_raid_room_mark(
    public_id: str,
    mark_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, removed = rooms_svc.remove_mark(db, public_id, user, mark_id)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    if removed:
        _publish(public_id, "mark_remove", data, extra={"mark_id": mark_id})
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/marks/clear",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def clear_tarkov_raid_room_marks(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.clear_marks(db, public_id, user)
    except rooms_svc.RaidRoomError as extra_exc:
        db.rollback()
        _raise(extra_exc)
        raise
    db.commit()
    _publish(public_id, "board_clear", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.websocket("/raid-rooms/{public_id}/ws")
async def tarkov_raid_room_ws(websocket: WebSocket, public_id: str) -> None:
    await websocket.accept()
    await room_ws_svc.run_room_session(websocket, public_id)
