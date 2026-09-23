"""签到调度队列：到点后按成员分批，不另建队列表。

用户设定的时分是入队时间。之后 30 分钟内，今天还没有成功 action 的成员留在队列里。
每分钟取出 ceil(还在排队的人数 / 窗口剩余分钟) 个，按 member_id 排序。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

RoleKey = tuple[str, str]

CHECKIN_QUEUE_WINDOW_MINUTES = 30
_MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class CheckinQueueItem:
    member_id: int
    role_key: RoleKey | None
    hour: int
    minute: int


def elapsed_scheduled_minutes(
    scheduled_hour: int,
    scheduled_minute: int,
    now_hour: int,
    now_minute: int,
) -> int | None:
    """设定时分到现在过了几分钟。未到点或已超出窗口则返回 None。"""
    delta = (
        (int(now_hour) * 60 + int(now_minute))
        - (int(scheduled_hour) * 60 + int(scheduled_minute))
    ) % _MINUTES_PER_DAY
    if delta >= CHECKIN_QUEUE_WINDOW_MINUTES:
        return None
    return delta


def minutes_left_in_window(elapsed: int) -> int:
    return max(1, CHECKIN_QUEUE_WINDOW_MINUTES - int(elapsed))


def queue_batch_size(waiting: int, minutes_left: int) -> int:
    """本分钟取出人数。窗口最后一分钟取完剩下的人。"""
    if waiting <= 0:
        return 0
    left = max(1, int(minutes_left))
    return max(1, (int(waiting) + left - 1) // left)


def plan_checkin_queue(
    items: list[CheckinQueueItem],
    *,
    now: datetime,
) -> dict[int, set[RoleKey] | None]:
    """从已到点且未成功的条目里，选出本分钟要签的成员。

    返回 member_id → role_keys。None 表示旧绑定、签该成员的全部角色。
    """
    pending: dict[int, tuple[int, set[RoleKey] | None]] = {}
    for item in items:
        elapsed = elapsed_scheduled_minutes(
            item.hour, item.minute, now.hour, now.minute
        )
        if elapsed is None:
            continue
        left = minutes_left_in_window(elapsed)
        member_id = int(item.member_id)
        current = pending.get(member_id)
        if current is None:
            roles: set[RoleKey] | None = (
                None if item.role_key is None else {item.role_key}
            )
            pending[member_id] = (left, roles)
            continue
        tight_left, roles = current
        if item.role_key is None or roles is None:
            roles = None
        else:
            roles = set(roles)
            roles.add(item.role_key)
        pending[member_id] = (min(tight_left, left), roles)

    grouped: dict[int, list[int]] = {}
    for member_id, (left, _) in pending.items():
        grouped.setdefault(left, []).append(member_id)

    selected: dict[int, set[RoleKey] | None] = {}
    for minutes_left in sorted(grouped):
        ordered = sorted(grouped[minutes_left])
        take = queue_batch_size(len(ordered), minutes_left)
        for member_id in ordered[:take]:
            roles = pending[member_id][1]
            selected[member_id] = None if roles is None else set(roles)
    return selected
