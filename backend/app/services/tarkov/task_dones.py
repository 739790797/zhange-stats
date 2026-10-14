"""塔科夫用户任务进度账：完成 / 进行中按 PVP/PVE 分开，供个人中心任务树。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.timeutil import now_naive, to_naive
from app.models.tarkov import (
    TarkovUserTaskCleared,
    TarkovUserTaskDone,
    TarkovUserTaskFailed,
    TarkovUserTaskObjectiveDone,
    TarkovUserTaskReset,
    TarkovUserTaskStarted,
)
from app.models.user import User
from app.services.tarkov.game_mode import current_game_mode, parse_game_mode

TASK_ID_MAX = 64
MERGE_MAX = 2000
OBJECTIVE_MERGE_MAX = 8000
CLEARED_MAX = 2000
PROFILE_ID_MAX = 64
RESET_REASONS = ("clear", "prestige", "profile")
CLOCK_FORMAT = "%Y-%m-%d %H:%M:%S"
# 回放下限只增不减、服务端撤不回：比服务器时钟还晚就是客户端时钟或时区算错了，拒掉。
# 留一点余量给客户端与服务器的时钟偏差。
RESET_FUTURE_SKEW = timedelta(minutes=10)
# MariaDB 1020（≥11.6.2 默认快照隔离：读过的行被并发事务改了）与 1213（死锁）：都已整笔回滚。
# 任务账写入撞上它们，说明同一账号的边界正在被别处改（多半是另一台设备在清空 / 重置）。
_CONTENDED_ERRNOS = frozenset({1020, 1213})


class TarkovTaskDonesError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_task_id(raw: str | None) -> str:
    ident = str(raw or "").strip().lower()
    if not ident or len(ident) > TASK_ID_MAX:
        raise TarkovTaskDonesError("任务 id 无效")
    return ident


def _mode(game_mode: str | None = None) -> str:
    return parse_game_mode(game_mode) if game_mode is not None else current_game_mode()


def _stamp(now: datetime | None = None) -> datetime:
    """边界时刻精确到秒：MySQL DATETIME 不带小数，存进去再读出来要和下发的一致。"""
    return to_naive(now or now_naive()).replace(microsecond=0)


def format_clock(value: datetime | None) -> str | None:
    if value is None:
        return None
    return to_naive(value).strftime(CLOCK_FORMAT)


def parse_clock(raw: str | None) -> datetime:
    """北京墙钟 `YYYY-MM-DD HH:MM:SS`（可带毫秒 / T / 时区）；向下取整到秒。"""
    text = str(raw or "").strip()
    if not text:
        raise TarkovTaskDonesError("边界时刻无效")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TarkovTaskDonesError("边界时刻无效") from exc
    return to_naive(parsed).replace(microsecond=0)


def _reset_row(
    db: Session,
    user_id: int,
    mode: str,
    *,
    create: bool = False,
    lock: bool = False,
) -> TarkovUserTaskReset | None:
    query = db.query(TarkovUserTaskReset).filter(
        TarkovUserTaskReset.user_id == user_id,
        TarkovUserTaskReset.game_mode == mode,
    )
    if create:
        _ensure_reset_row(db, user_id, mode)
    if lock:
        # 清空 / 推进下限 / 带 epoch 的写入要读到别的请求已提交的 epoch，并挡住同时进来的另一笔
        query = query.with_for_update()
    return query.one_or_none()


def _ensure_reset_row(db: Session, user_id: int, mode: str) -> None:
    """边界行不存在就先插上，再由调用方加锁读。

    顺序不能反：先 `SELECT … FOR UPDATE` 一行不存在的记录，InnoDB 拿的是间隙锁，两笔首次写边界
    （两个标签页 / 两台设备）都拿到间隙锁再各自插入，就互等成 1213 死锁，而死锁会回滚整笔事务，
    savepoint 兜不住。先插：撞主键的那笔等对方提交后得到 1062（只作废这一句），
    在 savepoint 里吞掉即可，随后的加锁读读到的是对方已提交的行。
    例外：MariaDB ≥11.6.2 默认快照隔离，加锁读碰上本事务读视图之后才提交的行会回 1020
    并整笔回滚；路由层把 1020 / 1213 回成 409（见 is_contended），前端重拉账号再来。
    """
    if _reset_row_exists(db, user_id, mode):
        return
    try:
        with db.begin_nested():
            db.add(
                TarkovUserTaskReset(
                    user_id=user_id,
                    game_mode=mode,
                    reset_at=None,
                    pending_clear_at=None,
                    profile_id="",
                    reason="",
                    epoch=0,
                    updated_at=_stamp(),
                )
            )
            db.flush()
    except IntegrityError:
        pass


def _reset_row_exists(db: Session, user_id: int, mode: str) -> bool:
    return (
        db.query(TarkovUserTaskReset.user_id)
        .filter(
            TarkovUserTaskReset.user_id == user_id,
            TarkovUserTaskReset.game_mode == mode,
        )
        .first()
        is not None
    )


def task_boundary(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    """回放下限（reset_at）、待定的清空（pending_clear_at）、所属游戏角色与版本号。"""
    row = _reset_row(db, user_id, _mode(game_mode))
    if row is None:
        return {
            "reset_at": None,
            "pending_clear_at": None,
            "profile_id": "",
            "epoch": 0,
        }
    return {
        "reset_at": format_clock(row.reset_at),
        "pending_clear_at": format_clock(row.pending_clear_at),
        "profile_id": str(row.profile_id or ""),
        "epoch": int(row.epoch or 0),
    }


def list_cleared(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[dict[str, str]]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskCleared)
        .filter(
            TarkovUserTaskCleared.user_id == user_id,
            TarkovUserTaskCleared.game_mode == mode,
        )
        .order_by(TarkovUserTaskCleared.task_id.asc())
        .all()
    )
    return [
        {"task_id": str(row.task_id), "cleared_at": format_clock(row.cleared_at) or ""}
        for row in rows
    ]


def _mark_cleared(
    db: Session,
    user_id: int,
    mode: str,
    task_ids: list[str],
    at: datetime,
) -> None:
    if not task_ids:
        return
    stamp = _stamp(at)
    have = {
        str(row.task_id): row
        for row in db.query(TarkovUserTaskCleared).filter(
            TarkovUserTaskCleared.user_id == user_id,
            TarkovUserTaskCleared.game_mode == mode,
        )
    }
    for ident in task_ids[:CLEARED_MAX]:
        row = have.get(ident)
        if row is None:
            db.add(
                TarkovUserTaskCleared(
                    user_id=user_id,
                    game_mode=mode,
                    task_id=ident,
                    cleared_at=stamp,
                )
            )
        elif to_naive(row.cleared_at) < stamp:
            row.cleared_at = stamp


def _release_cleared(
    db: Session,
    user_id: int,
    mode: str,
    task_ids: set[str],
) -> None:
    if not task_ids:
        return
    for row in db.query(TarkovUserTaskCleared).filter(
        TarkovUserTaskCleared.user_id == user_id,
        TarkovUserTaskCleared.game_mode == mode,
    ):
        if str(row.task_id) in task_ids:
            db.delete(row)


def _drop_cleared(
    db: Session,
    user_id: int,
    mode: str,
    *,
    upto: datetime | None = None,
) -> None:
    """单任务清除标记已被边界覆盖时删掉。

    upto=None：整表清空，全部删。给了 upto：只删不晚于下限的标记；晚于下限的仍要挡住
    下限之后、手动取消之前的那次完成（转生 / 换角色的下限可以早于手动取消）。
    """
    query = db.query(TarkovUserTaskCleared).filter(
        TarkovUserTaskCleared.user_id == user_id,
        TarkovUserTaskCleared.game_mode == mode,
    )
    if upto is not None:
        query = query.filter(TarkovUserTaskCleared.cleared_at <= upto)
    query.delete(synchronize_session=False)


def check_epoch(
    db: Session,
    user_id: int,
    expected: int | None,
    *,
    game_mode: str | None = None,
    required: bool = False,
) -> None:
    """带旧 epoch 的写入说明调用方的本机账是清空 / 转生之前的，拒掉免得把旧进度并回来。

    required：账号记过边界（epoch>0）后，批量写入与单任务 / 小步骤写入都必须带 epoch。不带的多半是还没和账号对过的新浏览器、
    或升级前缓存的旧页面，它们手里的账可能正是清空之前的。账号从没清空过（epoch 0）照旧放行。
    """
    row = _reset_row(db, user_id, _mode(game_mode), lock=True)
    current = int(row.epoch or 0) if row is not None else 0
    if expected is None:
        if required and current > 0:
            raise TarkovTaskDonesError("任务进度已在别处清空或重置，请刷新后再同步", 409)
        return
    if int(expected) != current:
        raise TarkovTaskDonesError("任务进度已在别处清空或重置，请刷新后再同步", 409)


def is_contended(exc: Exception) -> bool:
    """并发改同一账号边界时的瞬时错（见 _CONTENDED_ERRNOS）。路由按 409 回，前端会重拉账号再来。"""
    if not isinstance(exc, OperationalError):
        return False
    args = getattr(getattr(exc, "orig", None), "args", None) or ()
    try:
        return bool(args) and int(args[0]) in _CONTENDED_ERRNOS
    except (TypeError, ValueError):
        return False


def _wipe_ledger(db: Session, user_id: int, mode: str) -> None:
    for model in (
        TarkovUserTaskDone,
        TarkovUserTaskStarted,
        TarkovUserTaskFailed,
        TarkovUserTaskObjectiveDone,
    ):
        db.query(model).filter(
            model.user_id == user_id,
            model.game_mode == mode,
        ).delete(synchronize_session=False)


def clear_progress(
    db: Session,
    user: User,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """玩家点「清空进度」：清掉本模式完成 / 进行中 / 失败 / 小步骤，记下待定的清空时刻。

    下一次带日志的同步把它定成回放下限（换了角色或识别出转生时取转生点，否则取清空时刻）。
    """
    mode = _mode(game_mode)
    stamp = _stamp(now)
    # 先锁边界行再清账：同时进来、已过 epoch 检查的批量写入要么在清空之前提交，要么等清空提交后被 409
    row = _reset_row(db, user.id, mode, create=True, lock=True)
    assert row is not None
    _wipe_ledger(db, user.id, mode)
    _drop_cleared(db, user.id, mode)
    pending = row.pending_clear_at
    row.pending_clear_at = (
        stamp if pending is None or to_naive(pending) < stamp else to_naive(pending)
    )
    row.epoch = int(row.epoch or 0) + 1
    row.updated_at = stamp
    db.flush()
    return task_boundary(db, user.id, game_mode=mode)


def record_profile(
    db: Session,
    user: User,
    profile_id: str,
    *,
    game_mode: str | None = None,
) -> dict[str, Any]:
    """记下日志里当前模式的游戏 ProfileId（不动下限、不加 epoch）。

    这样之后在新浏览器 / 登出后同步时，账号知道当前角色是谁，日志里残留的旧角色不会被当成「换了角色」。
    """
    mode = _mode(game_mode)
    profile = str(profile_id or "").strip()
    if not profile or len(profile) > PROFILE_ID_MAX:
        raise TarkovTaskDonesError("ProfileId 无效")
    row = _reset_row(db, user.id, mode, create=True, lock=True)
    assert row is not None
    if row.profile_id != profile:
        row.profile_id = profile
        row.updated_at = _stamp()
        db.flush()
    return task_boundary(db, user.id, game_mode=mode)


def apply_reset(
    db: Session,
    user: User,
    *,
    reset_at: str,
    profile_id: str,
    reason: str,
    epoch: int,
    task_ids: list[Any],
    started_ids: list[Any] | None,
    failed_ids: list[Any] | None,
    objective_dones: list[Any] | None,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """推进回放下限（只增不减），并用本次日志回放结果整表替换本模式进度账。

    reason=clear 时下限不早于待定的清空时刻；prestige / profile 可以早于清空（转生之后、清空之前打的任务保留）。
    """
    mode = _mode(game_mode)
    if reason not in RESET_REASONS:
        raise TarkovTaskDonesError("重置原因无效")
    profile = str(profile_id or "").strip()
    if len(profile) > PROFILE_ID_MAX:
        raise TarkovTaskDonesError("ProfileId 无效")
    target = parse_clock(reset_at)
    stamp = _stamp(now)
    if target > stamp + RESET_FUTURE_SKEW:
        raise TarkovTaskDonesError("回放下限晚于当前时间，请检查电脑时钟与时区后再同步")
    # 先建好并锁住边界行，再比 epoch：先比的话是对不存在的行加锁读，会和建行互锁（见 _ensure_reset_row）
    row = _reset_row(db, user.id, mode, create=True, lock=True)
    assert row is not None
    check_epoch(db, user.id, epoch, game_mode=mode)
    if reason == "clear" and row.pending_clear_at is not None:
        target = max(target, to_naive(row.pending_clear_at))
    current = to_naive(row.reset_at) if row.reset_at is not None else None
    if current is not None and target < current:
        raise TarkovTaskDonesError("回放下限不能早于已记下的清空 / 转生时刻", 409)
    row.reset_at = target
    if profile:
        row.profile_id = profile
    row.reason = reason
    row.pending_clear_at = None
    row.epoch = int(row.epoch or 0) + 1
    row.updated_at = stamp
    write_progress(
        db,
        user,
        task_ids,
        started_ids if started_ids is not None else [],
        replace=True,
        game_mode=mode,
        now=stamp,
        objective_dones=objective_dones if objective_dones is not None else [],
        failed_ids=failed_ids if failed_ids is not None else [],
        mark_cleared=False,
    )
    # 被新下限覆盖的标记删掉；晚于下限的手动取消仍要挡住下限之后、取消之前的那次完成。
    # 整表替换拿掉的旧完成不另记标记：那是回放结果，不是玩家手动取消，记成「现在」会把
    # 别的设备上下限之后的真实完成也挡掉。
    _drop_cleared(db, user.id, mode, upto=target)
    db.flush()
    return task_boundary(db, user.id, game_mode=mode)


def list_task_ids(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskDone.task_id)
        .filter(
            TarkovUserTaskDone.user_id == user_id,
            TarkovUserTaskDone.game_mode == mode,
        )
        .order_by(TarkovUserTaskDone.created_at.asc(), TarkovUserTaskDone.task_id.asc())
        .all()
    )
    return [str(row[0]) for row in rows]


def list_started_ids(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskStarted.task_id)
        .filter(
            TarkovUserTaskStarted.user_id == user_id,
            TarkovUserTaskStarted.game_mode == mode,
        )
        .order_by(
            TarkovUserTaskStarted.created_at.asc(),
            TarkovUserTaskStarted.task_id.asc(),
        )
        .all()
    )
    return [str(row[0]) for row in rows]


def list_failed_ids(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskFailed.task_id)
        .filter(
            TarkovUserTaskFailed.user_id == user_id,
            TarkovUserTaskFailed.game_mode == mode,
        )
        .order_by(
            TarkovUserTaskFailed.created_at.asc(),
            TarkovUserTaskFailed.task_id.asc(),
        )
        .all()
    )
    return [str(row[0]) for row in rows]


def list_progress(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    done = list_task_ids(db, user_id, game_mode=game_mode)
    done_set = set(done)
    failed = [
        ident
        for ident in list_failed_ids(db, user_id, game_mode=game_mode)
        if ident not in done_set
    ]
    failed_set = set(failed)
    started = [
        ident
        for ident in list_started_ids(db, user_id, game_mode=game_mode)
        if ident not in done_set and ident not in failed_set
    ]
    return done, started, failed


def filter_visible_progress(
    done: list[str],
    started: list[str],
    catalog: set[str] | None,
    failed: list[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """进度账是冗余 id 表。目录里没有的（overlay disabled 等）只隐藏、不删行。

    catalog 为 None 表示图鉴不可用，原样返回。
    """
    failed_ids = failed or []
    if catalog is None:
        return done, started, failed_ids
    return (
        [ident for ident in done if ident in catalog],
        [ident for ident in started if ident in catalog],
        [ident for ident in failed_ids if ident in catalog],
    )


def list_objective_dones(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> list[dict[str, str]]:
    mode = _mode(game_mode)
    rows = (
        db.query(TarkovUserTaskObjectiveDone)
        .filter(
            TarkovUserTaskObjectiveDone.user_id == user_id,
            TarkovUserTaskObjectiveDone.game_mode == mode,
        )
        .order_by(
            TarkovUserTaskObjectiveDone.created_at.asc(),
            TarkovUserTaskObjectiveDone.task_id.asc(),
            TarkovUserTaskObjectiveDone.objective_id.asc(),
        )
        .all()
    )
    return [
        {"task_id": str(row.task_id), "objective_id": str(row.objective_id)}
        for row in rows
    ]


def account_progress(
    db: Session,
    user_id: int,
    *,
    game_mode: str | None = None,
) -> tuple[list[str], list[str], list[str], list[dict[str, str]]]:
    done, started, failed = list_progress(db, user_id, game_mode=game_mode)
    return done, started, failed, list_objective_dones(db, user_id, game_mode=game_mode)


def _started_rows(
    db: Session,
    user_id: int,
    mode: str,
) -> list[TarkovUserTaskStarted]:
    return (
        db.query(TarkovUserTaskStarted)
        .filter(
            TarkovUserTaskStarted.user_id == user_id,
            TarkovUserTaskStarted.game_mode == mode,
        )
        .all()
    )


def _failed_rows(
    db: Session,
    user_id: int,
    mode: str,
) -> list[TarkovUserTaskFailed]:
    return (
        db.query(TarkovUserTaskFailed)
        .filter(
            TarkovUserTaskFailed.user_id == user_id,
            TarkovUserTaskFailed.game_mode == mode,
        )
        .all()
    )


def _drop_failed(
    db: Session,
    user_id: int,
    mode: str,
    task_ids: set[str],
) -> None:
    if not task_ids:
        return
    for row in _failed_rows(db, user_id, mode):
        if str(row.task_id) in task_ids:
            db.delete(row)


def _drop_started(
    db: Session,
    user_id: int,
    mode: str,
    task_ids: set[str],
) -> None:
    if not task_ids:
        return
    for row in _started_rows(db, user_id, mode):
        if str(row.task_id) in task_ids:
            db.delete(row)


def add_done(
    db: Session,
    user: User,
    task_id: str,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> tuple[list[str], bool]:
    ident = normalize_task_id(task_id)
    mode = _mode(game_mode)
    existing = (
        db.query(TarkovUserTaskDone)
        .filter(
            TarkovUserTaskDone.user_id == user.id,
            TarkovUserTaskDone.game_mode == mode,
            TarkovUserTaskDone.task_id == ident,
        )
        .one_or_none()
    )
    added = False
    if existing is None:
        db.add(
            TarkovUserTaskDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=now or now_naive(),
            )
        )
        db.flush()
        added = True
    _drop_started(db, user.id, mode, {ident})
    _drop_failed(db, user.id, mode, {ident})
    _release_cleared(db, user.id, mode, {ident})
    db.flush()
    fill_objectives_for_done_tasks(
        db, user, [ident], game_mode=mode, now=now or now_naive()
    )
    return list_task_ids(db, user.id, game_mode=mode), added


def remove_done(
    db: Session,
    user: User,
    task_id: str,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> tuple[list[str], bool]:
    """从完成 / 进行中 / 失败三本账里拿掉该任务，使其回到未完成。

    拿掉的是已完成时记一笔清除时刻：日志里更早的完成事件不得把它粘回去。
    """
    ident = normalize_task_id(task_id)
    mode = _mode(game_mode)
    row = (
        db.query(TarkovUserTaskDone)
        .filter(
            TarkovUserTaskDone.user_id == user.id,
            TarkovUserTaskDone.game_mode == mode,
            TarkovUserTaskDone.task_id == ident,
        )
        .one_or_none()
    )
    started_rows = [
        item for item in _started_rows(db, user.id, mode) if str(item.task_id) == ident
    ]
    failed_rows = [
        item for item in _failed_rows(db, user.id, mode) if str(item.task_id) == ident
    ]
    removed = False
    if row is not None:
        db.delete(row)
        removed = True
        _mark_cleared(db, user.id, mode, [ident], now or now_naive())
    for item in started_rows:
        db.delete(item)
        removed = True
    for item in failed_rows:
        db.delete(item)
        removed = True
    if removed:
        db.flush()
    return list_task_ids(db, user.id, game_mode=mode), removed


def _incoming_ids(task_ids: list[Any] | None) -> list[str]:
    seen: set[str] = set()
    incoming: list[str] = []
    for raw in task_ids or []:
        try:
            ident = normalize_task_id(str(raw) if raw is not None else "")
        except TarkovTaskDonesError:
            continue
        if ident in seen:
            continue
        seen.add(ident)
        incoming.append(ident)
        if len(incoming) >= MERGE_MAX:
            break
    return incoming


def merge_dones(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = _incoming_ids(task_ids)
    have = set(list_task_ids(db, user.id, game_mode=mode))
    added: list[str] = []
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
        added.append(ident)
    db.flush()
    _drop_started(db, user.id, mode, have)
    _drop_failed(db, user.id, mode, have)
    _release_cleared(db, user.id, mode, set(added))
    db.flush()
    fill_objectives_for_done_tasks(
        db, user, added, game_mode=mode, now=stamp
    )
    return list_task_ids(db, user.id, game_mode=mode)


def replace_dones(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
    mark_cleared: bool = True,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = _incoming_ids(task_ids)
    wanted = set(incoming)
    rows = (
        db.query(TarkovUserTaskDone)
        .filter(
            TarkovUserTaskDone.user_id == user.id,
            TarkovUserTaskDone.game_mode == mode,
        )
        .all()
    )
    have = {str(row.task_id) for row in rows}
    removed: list[str] = []
    for row in rows:
        if str(row.task_id) not in wanted:
            removed.append(str(row.task_id))
            db.delete(row)
    added: list[str] = []
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
        added.append(ident)
    db.flush()
    _drop_started(db, user.id, mode, wanted)
    _drop_failed(db, user.id, mode, wanted)
    if mark_cleared:
        _mark_cleared(db, user.id, mode, removed, stamp)
    _release_cleared(db, user.id, mode, set(added))
    db.flush()
    fill_objectives_for_done_tasks(
        db, user, added, game_mode=mode, now=stamp
    )
    return list_task_ids(db, user.id, game_mode=mode)


def merge_starteds(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    done = set(list_task_ids(db, user.id, game_mode=mode))
    incoming = [ident for ident in _incoming_ids(task_ids) if ident not in done]
    have = set(list_started_ids(db, user.id, game_mode=mode))
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskStarted(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
    db.flush()
    _drop_failed(db, user.id, mode, set(incoming))
    db.flush()
    _done, started, _failed = list_progress(db, user.id, game_mode=mode)
    return started


def replace_starteds(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    done = set(list_task_ids(db, user.id, game_mode=mode))
    incoming = [ident for ident in _incoming_ids(task_ids) if ident not in done]
    wanted = set(incoming)
    rows = _started_rows(db, user.id, mode)
    have = {str(row.task_id) for row in rows}
    for row in rows:
        if str(row.task_id) not in wanted:
            db.delete(row)
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskStarted(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
    db.flush()
    _drop_failed(db, user.id, mode, wanted)
    db.flush()
    _done, started, _failed = list_progress(db, user.id, game_mode=mode)
    return started


def merge_faileds(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    done = set(list_task_ids(db, user.id, game_mode=mode))
    incoming = [ident for ident in _incoming_ids(task_ids) if ident not in done]
    have = set(list_failed_ids(db, user.id, game_mode=mode))
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskFailed(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
        have.add(ident)
    db.flush()
    _drop_started(db, user.id, mode, set(incoming))
    db.flush()
    _done, _started, failed = list_progress(db, user.id, game_mode=mode)
    return failed


def replace_faileds(
    db: Session,
    user: User,
    task_ids: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    done = set(list_task_ids(db, user.id, game_mode=mode))
    incoming = [ident for ident in _incoming_ids(task_ids) if ident not in done]
    wanted = set(incoming)
    rows = _failed_rows(db, user.id, mode)
    have = {str(row.task_id) for row in rows}
    for row in rows:
        if str(row.task_id) not in wanted:
            db.delete(row)
    for ident in incoming:
        if ident in have:
            continue
        db.add(
            TarkovUserTaskFailed(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                created_at=stamp,
            )
        )
    db.flush()
    _drop_started(db, user.id, mode, wanted)
    db.flush()
    _done, _started, failed = list_progress(db, user.id, game_mode=mode)
    return failed


def _incoming_objective_pairs(items: list[Any] | None) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    incoming: list[tuple[str, str]] = []
    for raw in items or []:
        if isinstance(raw, dict):
            task_raw = raw.get("task_id")
            obj_raw = raw.get("objective_id")
        else:
            continue
        try:
            task_id = normalize_task_id(str(task_raw) if task_raw is not None else "")
            objective_id = normalize_task_id(
                str(obj_raw) if obj_raw is not None else ""
            )
        except TarkovTaskDonesError:
            continue
        key = (task_id, objective_id)
        if key in seen:
            continue
        seen.add(key)
        incoming.append(key)
        if len(incoming) >= OBJECTIVE_MERGE_MAX:
            break
    return incoming


def _objective_row(
    db: Session,
    user_id: int,
    mode: str,
    task_id: str,
    objective_id: str,
) -> TarkovUserTaskObjectiveDone | None:
    return (
        db.query(TarkovUserTaskObjectiveDone)
        .filter(
            TarkovUserTaskObjectiveDone.user_id == user_id,
            TarkovUserTaskObjectiveDone.game_mode == mode,
            TarkovUserTaskObjectiveDone.task_id == task_id,
            TarkovUserTaskObjectiveDone.objective_id == objective_id,
        )
        .one_or_none()
    )


def merge_objective_dones(
    db: Session,
    user: User,
    items: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = _incoming_objective_pairs(items)
    have = {
        (row["task_id"], row["objective_id"])
        for row in list_objective_dones(db, user.id, game_mode=mode)
    }
    for task_id, objective_id in incoming:
        if (task_id, objective_id) in have:
            continue
        db.add(
            TarkovUserTaskObjectiveDone(
                user_id=user.id,
                game_mode=mode,
                task_id=task_id,
                objective_id=objective_id,
                created_at=stamp,
            )
        )
        have.add((task_id, objective_id))
    db.flush()
    return list_objective_dones(db, user.id, game_mode=mode)


def replace_objective_dones(
    db: Session,
    user: User,
    items: list[Any],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    mode = _mode(game_mode)
    stamp = now or now_naive()
    incoming = _incoming_objective_pairs(items)
    wanted = set(incoming)
    rows = (
        db.query(TarkovUserTaskObjectiveDone)
        .filter(
            TarkovUserTaskObjectiveDone.user_id == user.id,
            TarkovUserTaskObjectiveDone.game_mode == mode,
        )
        .all()
    )
    have = {(str(row.task_id), str(row.objective_id)) for row in rows}
    for row in rows:
        if (str(row.task_id), str(row.objective_id)) not in wanted:
            db.delete(row)
    for task_id, objective_id in incoming:
        if (task_id, objective_id) in have:
            continue
        db.add(
            TarkovUserTaskObjectiveDone(
                user_id=user.id,
                game_mode=mode,
                task_id=task_id,
                objective_id=objective_id,
                created_at=stamp,
            )
        )
    db.flush()
    return list_objective_dones(db, user.id, game_mode=mode)


def add_objective(
    db: Session,
    user: User,
    task_id: str,
    objective_id: str,
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> tuple[list[dict[str, str]], bool]:
    ident = normalize_task_id(task_id)
    oid = normalize_task_id(objective_id)
    mode = _mode(game_mode)
    existing = _objective_row(db, user.id, mode, ident, oid)
    added = False
    if existing is None:
        db.add(
            TarkovUserTaskObjectiveDone(
                user_id=user.id,
                game_mode=mode,
                task_id=ident,
                objective_id=oid,
                created_at=now or now_naive(),
            )
        )
        db.flush()
        added = True
    return list_objective_dones(db, user.id, game_mode=mode), added


def remove_objective(
    db: Session,
    user: User,
    task_id: str,
    objective_id: str,
    *,
    game_mode: str | None = None,
) -> tuple[list[dict[str, str]], bool]:
    ident = normalize_task_id(task_id)
    oid = normalize_task_id(objective_id)
    mode = _mode(game_mode)
    row = _objective_row(db, user.id, mode, ident, oid)
    removed = False
    if row is not None:
        db.delete(row)
        db.flush()
        removed = True
    return list_objective_dones(db, user.id, game_mode=mode), removed


def fill_objectives_for_done_tasks(
    db: Session,
    user: User,
    task_ids: list[str],
    *,
    game_mode: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    from app.services.tarkov.tasks import catalog_objective_ids

    wanted = [ident for ident in task_ids if ident]
    if not wanted:
        return list_objective_dones(db, user.id, game_mode=game_mode)
    catalog = catalog_objective_ids(db, wanted)
    pairs = [
        {"task_id": task_id, "objective_id": oid}
        for task_id, oids in catalog.items()
        for oid in oids
    ]
    if not pairs:
        return list_objective_dones(db, user.id, game_mode=game_mode)
    return merge_objective_dones(
        db, user, pairs, game_mode=game_mode, now=now
    )


def write_progress(
    db: Session,
    user: User,
    task_ids: list[Any],
    started_ids: list[Any] | None,
    *,
    replace: bool,
    game_mode: str | None = None,
    now: datetime | None = None,
    objective_dones: list[Any] | None = None,
    failed_ids: list[Any] | None = None,
    mark_cleared: bool = True,
) -> tuple[list[str], list[str], list[str]]:
    if replace:
        replace_dones(
            db, user, task_ids, game_mode=game_mode, now=now, mark_cleared=mark_cleared
        )
        if started_ids is not None:
            replace_starteds(db, user, started_ids, game_mode=game_mode, now=now)
        if failed_ids is not None:
            replace_faileds(db, user, failed_ids, game_mode=game_mode, now=now)
        if objective_dones is not None:
            replace_objective_dones(
                db, user, objective_dones, game_mode=game_mode, now=now
            )
            # 转生重置会交空列表清掉旧步骤；已完成任务仍按目录补齐，和标完成一致。
            if not _incoming_objective_pairs(objective_dones):
                fill_objectives_for_done_tasks(
                    db,
                    user,
                    list_task_ids(db, user.id, game_mode=_mode(game_mode)),
                    game_mode=game_mode,
                    now=now,
                )
    else:
        merge_dones(db, user, task_ids, game_mode=game_mode, now=now)
        if started_ids is not None:
            merge_starteds(db, user, started_ids, game_mode=game_mode, now=now)
        if failed_ids is not None:
            merge_faileds(db, user, failed_ids, game_mode=game_mode, now=now)
        if objective_dones is not None:
            merge_objective_dones(
                db, user, objective_dones, game_mode=game_mode, now=now
            )
    return list_progress(db, user.id, game_mode=game_mode)
