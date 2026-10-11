"""调度签到的当日重试账：按 (平台, 成员, 角色, 北京日期) 记尝试次数与下次可试时间。

失败按 1 / 3 / 9 分钟退避，每天最多 4 次；凭证失效、要验证码、找不到角色、今日已完成
记为当日终态，不再排队。只服务 due_only 队列，存短时 KV（Redis 或进程内），不建表；
手动「立即签到」不读也不写。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from app.core.ephemeral_kv import ephemeral_delete, ephemeral_get, ephemeral_set
from app.core.timeutil import day_bounds, ensure
from app.core.timeutil import now as now_beijing
from app.services.checkin.common import is_success_status
from app.services.checkin.queue import CheckinQueueItem
from app.services.checkin.role_prefs import RoleKey, role_key

RETRY_BACKOFF_MINUTES: tuple[int, ...] = (1, 3, 9)
MAX_ATTEMPTS_PER_DAY = len(RETRY_BACKOFF_MINUTES) + 1

TERMINAL_AUTH = "auth"
TERMINAL_CAPTCHA = "captcha"
TERMINAL_NO_ROLES = "no_roles"
TERMINAL_DONE = "done"

# 各平台 friendly_error 的凭证类文案都落在「重新绑定 / 重新登录」上
_AUTH_HINTS = (
    "重新绑定",
    "重新登录",
    "重新扫码",
    "登录已失效",
    "登录失效",
    "登录已过期",
    "凭证已损坏",
    "凭证格式无效",
    "凭证可能已失效",
    "unauthorized",
)
_CAPTCHA_HINTS = ("人机验证", "验证码", "captcha", "geetest")

_KEY_PREFIX = "checkin-attempts"
_ALL_ROLES = "*"


@dataclass(frozen=True)
class AttemptState:
    attempts: int = 0
    next_at: float = 0.0
    terminal: str | None = None

    def ready(self, now: datetime) -> bool:
        if self.terminal or self.attempts >= MAX_ATTEMPTS_PER_DAY:
            return False
        return ensure(now).timestamp() >= self.next_at


def classify_terminal_failure(messages: Iterable[str | None]) -> str | None:
    """凭证失效 / 要验证码：当天再试也不会好，返回终态；其余视为可退避重试。"""
    for raw in messages:
        text = (raw or "").strip().lower()
        if not text:
            continue
        if any(hint in text for hint in _CAPTCHA_HINTS):
            return TERMINAL_CAPTCHA
        if any(hint in text for hint in _AUTH_HINTS):
            return TERMINAL_AUTH
    return None


def _role_part(key: RoleKey | None) -> str:
    return _ALL_ROLES if key is None else f"{key[0]}/{key[1]}"


def _kv_key(platform: str, member_id: int, now: datetime) -> str:
    return f"{_KEY_PREFIX}:{platform}:{ensure(now).date().isoformat()}:{int(member_id)}"


def load_attempts(platform: str, member_id: int, *, now: datetime) -> dict[str, AttemptState]:
    raw = ephemeral_get(_kv_key(platform, member_id, now))
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, AttemptState] = {}
    for part, row in data.items():
        if not isinstance(row, dict):
            continue
        try:
            out[str(part)] = AttemptState(
                attempts=int(row.get("n") or 0),
                next_at=float(row.get("next") or 0),
                terminal=str(row["terminal"]) if row.get("terminal") else None,
            )
        except (TypeError, ValueError):
            continue
    return out


def _save_attempts(
    platform: str, member_id: int, states: dict[str, AttemptState], *, now: datetime
) -> None:
    t = ensure(now)
    _, day_end = day_bounds(t.date())
    payload = {
        part: {"n": s.attempts, "next": s.next_at, "terminal": s.terminal}
        for part, s in states.items()
    }
    ephemeral_set(
        _kv_key(platform, member_id, t),
        json.dumps(payload, separators=(",", ":")),
        ttl_sec=max(60, int((day_end - t).total_seconds()) + 60),
    )


def record_checkin_attempt(
    platform: str,
    member_id: int,
    role_keys: Iterable[RoleKey] | None,
    *,
    now: datetime,
    terminal: str | None = None,
) -> None:
    """记一次没成功的调度签到；terminal 非空表示这些角色今天不再排队。"""
    t = ensure(now)
    # 按整分钟算下次可试时间：调度每分钟一跳，秒数对齐会白白多等一跳
    tick = t.replace(second=0, microsecond=0)
    states = load_attempts(platform, member_id, now=t)
    parts = [_ALL_ROLES] if role_keys is None else [_role_part(k) for k in role_keys]
    for part in parts:
        prev = states.get(part, AttemptState())
        attempts = prev.attempts + 1
        delay = RETRY_BACKOFF_MINUTES[min(attempts, len(RETRY_BACKOFF_MINUTES)) - 1]
        states[part] = AttemptState(
            attempts=attempts,
            next_at=(tick + timedelta(minutes=delay)).timestamp(),
            terminal=terminal or prev.terminal,
        )
    _save_attempts(platform, member_id, states, now=t)


def record_checkin_outcome(
    platform: str,
    member_id: int,
    role_keys: set[RoleKey] | None,
    out: dict[str, Any],
    *,
    now: datetime,
) -> None:
    """按一次调度执行的返回记账：成功不记；跳过=今日已完成；没匹配到角色=当日终止；其余退避。"""
    if out.get("skipped"):
        record_checkin_attempt(platform, member_id, role_keys, now=now, terminal=TERMINAL_DONE)
        return
    if out.get("no_targets"):
        record_checkin_attempt(
            platform, member_id, role_keys, now=now, terminal=TERMINAL_NO_ROLES
        )
        return
    results = [r for r in out.get("results") or [] if isinstance(r, dict)]
    if role_keys is None:
        if out.get("ok"):
            return
        errors = [r.get("message") for r in results if r.get("status") == "error"]
        record_checkin_attempt(
            platform, member_id, None, now=now, terminal=classify_terminal_failure(errors)
        )
        return
    by_key = {
        role_key(str(r.get("game_code") or ""), str(r.get("role_uid") or "")): r
        for r in results
    }
    missing = {k for k in role_keys if k not in by_key}
    failed = {
        k
        for k in role_keys
        if k in by_key and not is_success_status(by_key[k].get("status"))
    }
    if missing:
        record_checkin_attempt(
            platform, member_id, missing, now=now, terminal=TERMINAL_NO_ROLES
        )
    failed_by_terminal: dict[str | None, set[RoleKey]] = {}
    for k in failed:
        terminal = classify_terminal_failure([by_key[k].get("message")])
        failed_by_terminal.setdefault(terminal, set()).add(k)
    for terminal, keys in failed_by_terminal.items():
        record_checkin_attempt(platform, member_id, keys, now=now, terminal=terminal)


def clear_checkin_attempts(platform: str, member_id: int, *, now: datetime | None = None) -> None:
    ephemeral_delete(_kv_key(platform, member_id, now or now_beijing()))


def filter_retry_ready(
    platform: str, items: list[CheckinQueueItem], *, now: datetime
) -> list[CheckinQueueItem]:
    """去掉退避中 / 当日已终止的条目，其余带上已尝试次数供队列排序。"""
    cache: dict[int, dict[str, AttemptState]] = {}
    out: list[CheckinQueueItem] = []
    for item in items:
        states = cache.get(item.member_id)
        if states is None:
            states = load_attempts(platform, item.member_id, now=now)
            cache[item.member_id] = states
        state = states.get(_role_part(item.role_key))
        if state is None:
            out.append(item)
        elif state.ready(now):
            out.append(replace(item, attempts=state.attempts))
    return out
