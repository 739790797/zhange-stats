"""联机大厅房间 REST + WebSocket。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, WebSocket
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.guides.schemas import (
    TarkovRaidRoomClaimsIn,
    TarkovRaidRoomCreateIn,
    TarkovRaidRoomDetailOut,
    TarkovRaidRoomObjectiveDonesIn,
    TarkovRaidRoomHostIn,
    TarkovRaidRoomJoinIn,
    TarkovRaidRoomLobbyOut,
    TarkovRaidRoomMineOut,
    TarkovRaidRoomMapIn,
    TarkovRaidRoomMarkIn,
    TarkovRaidRoomMarkMoveIn,
    TarkovRaidRoomTaskProgressIn,
)
from app.core.database import get_db
from app.core.deps import get_current_user, get_optional_user
from app.core.platform_deps import require_feature
from app.core.rate_limit import client_ip, platform_limiter
from app.core.security import hash_password
from app.core.ws_origin import CLOSE_ORIGIN_FORBIDDEN, websocket_origin_allowed
from app.models.user import User
from app.services.tarkov import raid_room_ws as room_ws_svc
from app.services.tarkov import raid_rooms as rooms_svc
from app.services.tarkov.raid_room_hub import hub

router = APIRouter()
_FEATURE = Depends(require_feature("guides.tarkov"))
_T = TypeVar("_T")


def _raise(exc: rooms_svc.RaidRoomError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


WRITE_LIMIT_PER_MINUTE = 120


def _hit_room_write(user: User) -> None:
    """房间写操作按账号限流：每次都要改库，还会给全房推一帧。"""
    platform_limiter.hit(
        f"tarkov-raid-write:uid:{user.id}",
        limit=WRITE_LIMIT_PER_MINUTE,
        window_sec=60,
    )


def _stamp_seq(result: _T) -> _T:
    """响应给调用方：快照里带上本笔事务的 seq，前端据此丢弃更旧的帧。"""
    target = result[0] if isinstance(result, tuple) and result else result
    if isinstance(target, dict):
        target["seq"] = hub.current_seq(str(target.get("public_id") or ""))
    return result


def room_action(
    db: Session,
    public_id: str,
    run: Callable[[], _T],
    publish: Callable[[_T], None] | None = None,
    extra_keys: Callable[[], list[str]] | None = None,
) -> _T:
    """房间写操作统一出口：按房间串行；失败回滚；commit 后才踢 socket / 关房。

    `publish` 在 commit 之后、**仍持有房间锁**时调用：广播必须在锁内入队，否则并发写的
    广播会按「谁先抢到 CPU」而不是「谁先提交」的顺序发出，后到的旧快照会盖掉新状态。
    `extra_keys` 给换房用的**其他房间号**（旧房）：和 `key` 一起按房间号排序后上锁，
    两笔换房不会以相反顺序互等；不给也能跑（`_require_room_locks` 会报缺锁后补锁重跑）。
    """
    try:
        result = rooms_svc.run_in_room_tx(
            db,
            run,
            key=public_id,
            on_commit=publish,
            extra_keys=extra_keys,
        )
    except rooms_svc.RaidRoomError as exc:
        _raise(exc)
        raise
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="房间状态刚变过，请刷新后重试") from exc
    return _stamp_seq(result)


def _my_other_rooms(db: Session, user: User, keep: str) -> Callable[[], list[str]]:
    """本人在座的其他房间号（换房时要连旧房的锁一起拿）。"""

    def keys() -> list[str]:
        return [pid for pid in rooms_svc.occupant_public_ids(db, user.id) if pid != keep]

    return keys


def read_action(run: Callable[[], _T]) -> _T:
    """只读路径（大厅 / 我的房间 / 房间预览）：不占房间锁，只做错误映射与错误码转换。"""
    try:
        return run()
    except rooms_svc.RaidRoomError as exc:
        _raise(exc)
        raise


_SNAPSHOT_WS_EVENTS = frozenset({"member_join", "member_leave", "snapshot"})
_PATCH_WS_FIELDS: dict[str, tuple[str, ...]] = {
    "claim_add": ("claims",),
    "claim_remove": ("claims",),
    "key_bring_add": ("key_brings",),
    "key_bring_remove": ("key_brings",),
    "objective_done_add": ("objective_dones",),
    "objective_done_remove": ("objective_dones",),
    "task_progress": ("map_overlap", "task_progress"),
    "key_own_change": ("key_owns",),
    "board_clear": ("marks",),
    "view_map": ("view_maps",),
}


def room_ws_payload(
    event: str,
    snapshot: dict,
    extra: dict | None = None,
    *,
    online_user_ids: list[int] | None = None,
    online_clients: list[dict] | None = None,
) -> dict:
    """成员进离/换图等仍带整份 snapshot；画笔/声明只发补丁。"""
    extra = dict(extra or {})
    if event in _SNAPSHOT_WS_EVENTS:
        payload: dict = {"event": event, "snapshot": snapshot, **extra}
    else:
        payload = {"event": event, **extra}
        for field in _PATCH_WS_FIELDS.get(event, ()):
            if field not in payload:
                payload[field] = snapshot.get(field)
    payload["online_user_ids"] = list(online_user_ids or [])
    if online_clients is not None:
        payload["online_clients"] = online_clients
    return payload


def _publish(
    public_id: str,
    event: str,
    snapshot: dict,
    extra: dict | None = None,
    *,
    seq: int | None = None,
) -> None:
    """广播房间事件。seq 缺省由 hub 现占，调用方在房间锁内传入帧的提交顺序。"""
    payload = room_ws_payload(
        event,
        _strip_viewer_flags(snapshot),
        extra,
        online_user_ids=list(hub.online_user_ids(public_id)),
        online_clients=hub.online_clients(public_id),
    )
    if seq:
        payload["seq"] = seq
    hub.publish(public_id, payload)


def _publisher(
    public_id: str,
    event: str,
    extra_fn: Callable[[dict], dict | None] | None = None,
    *,
    when: Callable[[object], bool] | None = None,
) -> Callable[[object], None]:
    """包一层：事务 commit 后（仍在房间锁内）按快照发广播。

    `when` 收到事务的完整返回值（通常是 `(snapshot, added)`）；返回 False 则不发。
    """

    def publish(result: object) -> None:
        if when is not None and not when(result):
            return
        snapshot = _snapshot_of(result)
        if snapshot is None:
            return
        extra = extra_fn(result) if extra_fn is not None else None
        _publish(public_id, event, snapshot, extra=extra)

    return publish


def _result_item(index: int, result: object) -> object:
    if isinstance(result, tuple) and len(result) > index:
        return result[index]
    return None


def _result_mark(index: int) -> Callable[[object], dict | None]:
    def extra(result: object) -> dict | None:
        mark = _result_item(index, result)
        return {"mark": mark} if isinstance(mark, dict) else None

    return extra


def _result_flag(index: int) -> Callable[[object], bool]:
    """判断事务返回元组里第 index 项（added / removed 计数）是否为真。"""

    def check(result: object) -> bool:
        if isinstance(result, tuple) and len(result) > index:
            return bool(result[index])
        return False

    return check


def _snapshot_of(result: object) -> dict | None:
    target = result[0] if isinstance(result, tuple) and result else result
    if isinstance(target, dict):
        return target
    return None


_VIEWER_FIELDS = ("is_host", "is_member", "can_edit")


def _strip_viewer_flags(snapshot: dict) -> dict:
    """快照按发起人视角生成；广播给全员前去掉视角字段，各端自己按 user_id 推导。"""
    if not isinstance(snapshot, dict):
        return snapshot
    return {key: value for key, value in snapshot.items() if key not in _VIEWER_FIELDS}


def _vacated_of(result: object) -> list[dict]:
    if isinstance(result, tuple) and len(result) >= 3 and isinstance(result[2], list):
        return result[2]
    return []


def _publish_vacated(vacated: list[dict], user_id: int) -> None:
    """在 room_action 的 on_commit 里调用：旧房的锁（extra_keys）此时仍握在手里。

    必须在**同一段**持锁里发：先出锁再回锁的话，旧房里插进来的一笔写会先拿到 seq N，
    这帧完整快照再拿 N+1，晚到却更旧，把那笔写在各端盖掉。
    """
    for snap in vacated:
        vacated_id = str(snap.get("public_id") or "").strip()
        if not vacated_id:
            continue
        # room_lock 可重入：on_commit 里旧房的锁已在手，这里只是兜底。
        with rooms_svc.room_lock(vacated_id):
            _publish(
                vacated_id,
                "member_leave",
                snap,
                extra={"user_id": user_id},
                seq=hub.reserve_seq(vacated_id),
            )


@router.get(
    "/raid-rooms",
    response_model=TarkovRaidRoomLobbyOut,
    dependencies=[_FEATURE],
)
def list_tarkov_raid_rooms(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> TarkovRaidRoomLobbyOut:
    """分页列出当前模式的公开房间（listed、无密码、仍有人在座）。

    限流：每 IP / 每账号 40 次/分钟。私密房不出现；自己的私密房在 `mine`。
    """
    ip = client_ip(request)
    platform_limiter.hit(
        f"tarkov-raid-lobby:ip:{ip}",
        limit=rooms_svc.LOBBY_RATE_LIMIT,
        window_sec=rooms_svc.LOBBY_RATE_WINDOW_SEC,
    )
    if user is not None:
        _, lobby_uid = rooms_svc.lobby_rate_limit_keys(ip, user.id)
        platform_limiter.hit(
            lobby_uid,
            limit=rooms_svc.LOBBY_RATE_LIMIT,
            window_sec=rooms_svc.LOBBY_RATE_WINDOW_SEC,
        )
    online_by_public_id = {
        pid: hub.online_user_ids(pid) for pid in hub.known_public_ids()
    }
    data = read_action(
        lambda: rooms_svc.list_live_rooms(
            db,
            viewer=user,
            online_by_public_id=online_by_public_id,
            page=page,
            page_size=page_size,
            prune=rooms_svc.room_prune_due(),
        )
    )
    return TarkovRaidRoomLobbyOut.model_validate(data)


@router.get(
    "/raid-rooms/mine",
    response_model=TarkovRaidRoomMineOut,
    dependencies=[_FEATURE],
)
def get_my_tarkov_raid_room(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomMineOut:
    online_by_public_id = {
        pid: hub.online_user_ids(pid) for pid in hub.known_public_ids()
    }
    item = read_action(
        lambda: rooms_svc.get_my_live_room(db, user, online_by_public_id=online_by_public_id)
    )
    return TarkovRaidRoomMineOut(item=item)


@router.post(
    "/raid-rooms",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def create_tarkov_raid_room(
    request: Request,
    body: TarkovRaidRoomCreateIn = Body(default_factory=TarkovRaidRoomCreateIn),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    ip = client_ip(request)
    platform_limiter.hit(f"tarkov-raid-create:ip:{ip}", limit=20, window_sec=600)
    platform_limiter.hit(f"tarkov-raid-create:uid:{user.id}", limit=10, window_sec=600)
    # 密码哈希（bcrypt）在事务外先算：不能占着房间锁跑上百毫秒。
    is_listed, raw_password = rooms_svc.clean_create_visibility(bool(body.listed), body.password)
    password_hash = hash_password(raw_password) if raw_password else None
    title = body.title
    listed = is_listed
    game_mode = body.game_mode
    published: list[str] = []

    def run() -> object:
        return rooms_svc.create_room(
            db,
            user,
            title=title,
            password=raw_password or None,
            password_hash=password_hash,
            listed=listed,
            game_mode=game_mode,
        )

    def publish(result: object) -> None:
        _publish_vacated(_vacated_of(result), user.id)
        snapshot = _snapshot_of(result)
        if snapshot is None:
            return
        pid = str(snapshot.get("public_id") or "")
        published.append(pid)
        if pid:
            # 新房第一帧按真实房间号占 seq；没人连就不占，免得空房在 _seq 里留条目。
            _publish(
                pid,
                "member_join",
                snapshot,
                extra={"user_id": user.id, "display_name": user.display_name},
                seq=hub.reserve_seq(pid),
            )

    data, _joined_now, _vacated = room_action(
        db,
        "",
        run,
        publish,
        # 建房也要先腾掉旧房的座位：旧房的锁一并按房间号排序拿好。
        extra_keys=_my_other_rooms(db, user, ""),
    )
    return TarkovRaidRoomDetailOut.model_validate(data)


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
    # 每次都要改库 + 给全房推一整帧快照，和别的写操作同一个限流桶。
    _hit_room_write(user)
    map_slug = body.map

    def on_commit(result: object) -> None:
        # 查看图先落 hub 再广播，帧里 view_maps / can_edit 与进程内状态一致。
        rooms_svc.apply_view_map(public_id, user.id, map_slug)
        _publisher(public_id, "snapshot")(result)

    data = room_action(
        db,
        public_id,
        lambda: rooms_svc.set_room_map(
            db,
            public_id,
            user,
            map_slug,
            online_user_ids=hub.online_user_ids(public_id),
            log_phases=hub.log_phases(public_id),
        ),
        on_commit,
    )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.get(
    "/raid-rooms/{public_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def get_tarkov_raid_room(
    request: Request,
    public_id: str,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> TarkovRaidRoomDetailOut:
    """取房间详情。未入座只返回标题、模式、人数、是否要密码，不含地图、查看图、棋盘与人员名单。

    只读：过期座位回收改由节流的 prune 完成，这个接口不再写库（未登录也能打）。
    """
    platform_limiter.hit(
        f"tarkov-raid-room-get:ip:{client_ip(request)}",
        limit=rooms_svc.ROOM_GET_RATE_LIMIT,
        window_sec=rooms_svc.ROOM_GET_RATE_WINDOW_SEC,
    )
    data = read_action(
        lambda: rooms_svc.get_room(
            db,
            public_id,
            user,
            online_user_ids=hub.online_user_ids(public_id),
            prune=rooms_svc.room_prune_due(),
        )
    )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/join",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def join_tarkov_raid_room(
    request: Request,
    public_id: str,
    body: TarkovRaidRoomJoinIn = Body(default_factory=TarkovRaidRoomJoinIn),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    """加入房间。有密码须带明文；成功与失败（含密码错误）都计入限流。

    限流：每 IP+房间、每账号+房间各 10 次/10 分钟。
    """
    ip = client_ip(request)
    join_ip, join_uid = rooms_svc.join_rate_limit_keys(ip, user.id, public_id)
    platform_limiter.hit(
        join_ip,
        limit=rooms_svc.JOIN_RATE_LIMIT,
        window_sec=rooms_svc.JOIN_RATE_WINDOW_SEC,
    )
    platform_limiter.hit(
        join_uid,
        limit=rooms_svc.JOIN_RATE_LIMIT,
        window_sec=rooms_svc.JOIN_RATE_WINDOW_SEC,
    )
    # 口令（bcrypt）在锁外先校验：不能占着房间锁跑。
    password = body.password
    password_checked = read_action(
        lambda: rooms_svc.verify_join_password(db, public_id, password)
    )
    announced: list[bool] = []

    def run() -> object:
        result = rooms_svc.join_room(
            db,
            public_id,
            user,
            game_mode=None,
            password=password,
            password_checked=password_checked,
        )
        announced.append(bool(result[1]))
        return result

    def publish(result: object) -> None:
        _publish_vacated(_vacated_of(result), user.id)
        if not announced or not announced[-1]:
            return
        _publish(
            public_id,
            "member_join",
            _snapshot_of(result) or {},
            extra={"user_id": user.id, "display_name": user.display_name},
        )

    data, joined_now, _vacated = room_action(
        db,
        public_id,
        run,
        publish,
        extra_keys=_my_other_rooms(db, user, public_id),
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
    _hit_room_write(user)

    def publish(result: object) -> None:
        # 房间因此解散时没有广播对象，只留踢 socket 的副作用。
        broadcast = result[1] if isinstance(result, tuple) and len(result) > 1 else None
        if isinstance(broadcast, dict):
            _publish(public_id, "member_leave", broadcast, extra={"user_id": user.id})

    data, _broadcast = room_action(
        db,
        public_id,
        lambda: rooms_svc.leave_room(db, public_id, user),
        publish,
    )
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
    _hit_room_write(user)
    data = room_action(db, public_id, lambda: rooms_svc.reset_room(db, public_id, user))
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
    _hit_room_write(user)
    data = room_action(
        db,
        public_id,
        lambda: rooms_svc.remove_member(db, public_id, user, user_id),
        _publisher(public_id, "member_leave", lambda _result: {"user_id": user_id}),
    )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.post(
    "/raid-rooms/{public_id}/host",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def transfer_tarkov_raid_room_host(
    public_id: str,
    body: TarkovRaidRoomHostIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    """房主把房主转让给在座成员。"""
    _hit_room_write(user)
    target = body.user_id
    data = room_action(
        db,
        public_id,
        lambda: rooms_svc.transfer_host(db, public_id, user, target),
        _publisher(public_id, "snapshot"),
    )
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
    # 一次最多 400 + 800 个 id，还要重算重叠并推整帧，和别的写操作同一个限流桶。
    _hit_room_write(user)
    started_ids = body.started_ids
    done_ids = body.done_ids
    data = room_action(
        db,
        public_id,
        lambda: rooms_svc.set_member_task_progress(
            db,
            public_id,
            user,
            started_ids,
            done_ids,
        ),
        _publisher(public_id, "task_progress", lambda _result: {"user_id": user.id}),
    )
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
    _hit_room_write(user)
    task = task_id
    data, _added = room_action(
        db,
        public_id,
        lambda: rooms_svc.claim_task(db, public_id, user, task),
        _publisher(
            public_id,
            "claim_add",
            lambda _result: {"task_id": task, "user_id": user.id},
            when=_result_flag(1),
        ),
    )
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
    _hit_room_write(user)
    task_ids = body.task_ids[:40]
    data, _added = room_action(
        db,
        public_id,
        lambda: rooms_svc.claim_tasks(db, public_id, user, task_ids),
        _publisher(
            public_id,
            "claim_add",
            lambda _result: {"user_id": user.id},
            when=_result_flag(1),
        ),
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
    _hit_room_write(user)
    task = task_id
    data, _removed = room_action(
        db,
        public_id,
        lambda: rooms_svc.unclaim_task(db, public_id, user, task),
        _publisher(
            public_id,
            "claim_remove",
            lambda _result: {"task_id": task, "user_id": user.id},
            when=_result_flag(1),
        ),
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
    _hit_room_write(user)
    item = item_id
    data, _added = room_action(
        db,
        public_id,
        lambda: rooms_svc.bring_key(db, public_id, user, item),
        _publisher(
            public_id,
            "key_bring_add",
            lambda _result: {"item_id": item, "user_id": user.id},
            when=_result_flag(1),
        ),
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
    _hit_room_write(user)
    item = item_id
    data, _removed = room_action(
        db,
        public_id,
        lambda: rooms_svc.unbring_key(db, public_id, user, item),
        _publisher(
            public_id,
            "key_bring_remove",
            lambda _result: {"item_id": item, "user_id": user.id},
            when=_result_flag(1),
        ),
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
    _hit_room_write(user)
    pairs = [(item.task_id, item.objective_id) for item in body.items]

    def extra_of(result: object) -> dict | None:
        added = result[1] if isinstance(result, tuple) and len(result) > 1 else None
        if not added:
            return None
        return {
            "items": [{"task_id": tid, "objective_id": oid} for tid, oid in added],
            "user_id": user.id,
        }

    data, _added = room_action(
        db,
        public_id,
        lambda: rooms_svc.mark_objectives_done(db, public_id, user, pairs),
        _publisher(public_id, "objective_done_add", extra_of, when=_result_flag(1)),
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
    _hit_room_write(user)
    task = task_id
    obj = objective_id
    data, _added = room_action(
        db,
        public_id,
        lambda: rooms_svc.mark_objective_done(db, public_id, user, task, obj),
        _publisher(
            public_id,
            "objective_done_add",
            lambda _result: {"task_id": task, "objective_id": obj, "user_id": user.id},
            when=_result_flag(1),
        ),
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
    _hit_room_write(user)
    task = task_id
    obj = objective_id
    data, _removed = room_action(
        db,
        public_id,
        lambda: rooms_svc.unmark_objective_done(db, public_id, user, task, obj),
        _publisher(
            public_id,
            "objective_done_remove",
            lambda _result: {"task_id": task, "objective_id": obj, "user_id": user.id},
            when=_result_flag(1),
        ),
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
    _hit_room_write(user)
    kind = body.kind
    floor = body.floor
    x = body.x
    z = body.z
    x2 = body.x2
    z2 = body.z2
    points = body.points
    label = body.label
    data, _mark = room_action(
        db,
        public_id,
        lambda: rooms_svc.add_mark(
            db,
            public_id,
            user,
            kind=kind,
            floor=floor,
            x=x,
            z=z,
            x2=x2,
            z2=z2,
            points=points,
            label=label,
        ),
        _publisher(public_id, "mark_add", _result_mark(1)),
    )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.patch(
    "/raid-rooms/{public_id}/marks/{mark_id}",
    response_model=TarkovRaidRoomDetailOut,
    dependencies=[_FEATURE],
)
def move_tarkov_raid_room_mark(
    public_id: str,
    mark_id: int,
    body: TarkovRaidRoomMarkMoveIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TarkovRaidRoomDetailOut:
    _hit_room_write(user)
    x = body.x
    z = body.z
    data, _mark = room_action(
        db,
        public_id,
        lambda: rooms_svc.move_text_mark(db, public_id, user, mark_id, x=x, z=z),
        _publisher(
            public_id,
            "mark_move",
            _result_mark(1),
            when=lambda result: isinstance(_result_item(1, result), dict),
        ),
    )
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
    _hit_room_write(user)
    data, _mark_id = room_action(
        db,
        public_id,
        lambda: rooms_svc.undo_own_mark(db, public_id, user),
        _publisher(
            public_id,
            "mark_remove",
            lambda result: {"mark_id": _result_item(1, result)},
            when=lambda result: _result_item(1, result) is not None,
        ),
    )
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
    _hit_room_write(user)
    data, _removed = room_action(
        db,
        public_id,
        lambda: rooms_svc.remove_mark(db, public_id, user, mark_id),
        _publisher(
            public_id,
            "mark_remove",
            lambda _result: {"mark_id": mark_id},
            when=_result_flag(1),
        ),
    )
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
    _hit_room_write(user)
    cleared_map = read_action(lambda: hub.view_map_of(public_id, user.id))
    data = room_action(
        db,
        public_id,
        lambda: rooms_svc.clear_marks(db, public_id, user),
        _publisher(
            public_id,
            "board_clear",
            lambda _result: {"map_slug": cleared_map},
        ),
    )
    return TarkovRaidRoomDetailOut.model_validate(data)


@router.websocket("/raid-rooms/{public_id}/ws")
async def tarkov_raid_room_ws(websocket: WebSocket, public_id: str) -> None:
    allowed = websocket_origin_allowed(websocket)
    await websocket.accept()
    if not allowed:
        await websocket.close(code=CLOSE_ORIGIN_FORBIDDEN)
        return
    await room_ws_svc.run_room_session(websocket, public_id)
