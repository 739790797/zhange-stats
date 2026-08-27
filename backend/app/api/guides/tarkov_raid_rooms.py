"""战局准备房间 REST + WebSocket。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy.orm import Session

from app.api.guides.schemas import (
    TarkovRaidRoomCreateIn,
    TarkovRaidRoomDetailOut,
    TarkovRaidRoomLobbyOut,
    TarkovRaidRoomMarkIn,
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
    hub.publish(public_id, payload)


@router.get(
    "/raid-rooms",
    response_model=TarkovRaidRoomLobbyOut,
    dependencies=[_FEATURE],
)
def list_tarkov_raid_rooms(
    map_slug: str | None = Query(default=None, alias="map", max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomLobbyOut:
    data = rooms_svc.list_live_rooms(db, map_slug=map_slug, viewer=user)
    db.commit()
    return TarkovRaidRoomLobbyOut.model_validate(data)


@router.post(
    "/raid-rooms",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def create_tarkov_raid_room(
    body: TarkovRaidRoomCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.create_room(db, user, map_slug=body.map, title=body.title)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
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
        data, archived_now = rooms_svc.get_room(
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
    if archived_now:
        _publish(public_id, "archived", data)
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/join",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def join_tarkov_raid_room(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data, joined_now = rooms_svc.join_room(db, public_id, user)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    if joined_now:
        _publish(
            public_id,
            "member_join",
            data,
            extra={"user_id": user.id, "display_name": user.display_name},
        )
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
    "/raid-rooms/{public_id}/close",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def close_tarkov_raid_room(
    public_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    try:
        data = rooms_svc.close_room(db, public_id, user)
    except rooms_svc.RaidRoomError as exc:
        db.rollback()
        _raise(exc)
        raise
    db.commit()
    _publish(public_id, "archived", data)
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
