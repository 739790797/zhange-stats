"""签到队列：到点后按成员分批，失败的人留在窗口里。"""

from __future__ import annotations

from datetime import datetime

from app.core.timeutil import BEIJING
from app.services.checkin.queue import (
    CHECKIN_QUEUE_WINDOW_MINUTES,
    CheckinQueueItem,
    elapsed_scheduled_minutes,
    plan_checkin_queue,
    queue_batch_size,
)


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 24, hour, minute, tzinfo=BEIJING)


def _item(member_id: int, hour: int = 0, minute: int = 5, role: str = "1") -> CheckinQueueItem:
    return CheckinQueueItem(
        member_id=member_id,
        role_key=("arknights", role),
        hour=hour,
        minute=minute,
    )


def test_queue_batch_size_spreads_across_window() -> None:
    assert queue_batch_size(0, 30) == 0
    assert queue_batch_size(10, 30) == 1
    assert queue_batch_size(31, 30) == 2
    assert queue_batch_size(10, 1) == 10


def test_elapsed_window_edges_and_midnight() -> None:
    assert elapsed_scheduled_minutes(0, 5, 0, 5) == 0
    assert elapsed_scheduled_minutes(0, 5, 0, 34) == 29
    assert elapsed_scheduled_minutes(0, 5, 0, 35) is None
    assert elapsed_scheduled_minutes(0, 5, 0, 0) is None
    assert elapsed_scheduled_minutes(23, 50, 0, 10) == 20
    assert elapsed_scheduled_minutes(23, 50, 0, 20) is None
    assert CHECKIN_QUEUE_WINDOW_MINUTES == 30


def test_plan_takes_lowest_member_first_at_default_time() -> None:
    items = [_item(member_id) for member_id in range(10, 0, -1)]
    selected = plan_checkin_queue(items, now=_at(0, 5))
    assert list(selected) == [1]
    assert selected[1] == {("arknights", "1")}


def test_plan_takes_everyone_on_last_window_minute() -> None:
    items = [_item(member_id) for member_id in (3, 1, 2)]
    selected = plan_checkin_queue(items, now=_at(0, 34))
    assert list(selected) == [1, 2, 3]


def test_plan_drops_cohort_after_window() -> None:
    items = [_item(1), _item(2, hour=8, minute=0)]
    assert plan_checkin_queue(items, now=_at(0, 35)) == {}
    later = plan_checkin_queue(items, now=_at(8, 0))
    assert list(later) == [2]


def test_plan_merges_roles_and_keeps_tighter_window() -> None:
    items = [
        _item(1, hour=0, minute=5, role="a"),
        _item(1, hour=0, minute=20, role="b"),
        _item(2, hour=0, minute=20, role="c"),
    ]
    selected = plan_checkin_queue(items, now=_at(0, 20))
    assert set(selected) == {1, 2}
    assert selected[1] == {("arknights", "a"), ("arknights", "b")}
    assert selected[2] == {("arknights", "c")}


def test_plan_separate_slots_do_not_share_a_batch() -> None:
    early = [_item(member_id, hour=23, minute=50) for member_id in range(1, 16)]
    default = [_item(member_id, hour=0, minute=5, role="d") for member_id in range(20, 30)]
    selected = plan_checkin_queue(early + default, now=_at(0, 5))
    early_ids = [member_id for member_id in selected if member_id < 20]
    default_ids = [member_id for member_id in selected if member_id >= 20]
    assert len(early_ids) == 1
    assert len(default_ids) == 1
