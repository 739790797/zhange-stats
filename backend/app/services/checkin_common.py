"""签到公共模型与状态约定（森空岛 / 塔吉多 / 后续平台共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STATUS_OK = "ok"
STATUS_ALREADY = "already"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"
STATUS_PENDING = "pending"

SUCCESS_STATUSES = frozenset({STATUS_OK, STATUS_ALREADY})

# 展示文案：ok / already 统一为「已签」
STATUS_LABELS: dict[str, str] = {
    STATUS_OK: "已签",
    STATUS_ALREADY: "已签",
    STATUS_ERROR: "失败",
    STATUS_SKIPPED: "跳过",
    STATUS_PENDING: "未签",
}


@dataclass
class CheckinResult:
    game_code: str
    game_name: str
    role_uid: str
    role_name: str
    channel_name: str
    status: str  # ok | already | error | skipped
    message: str
    awards_text: str | None = None
    extra_text: str | None = None

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "game_code": self.game_code,
            "game_name": self.game_name,
            "role_uid": self.role_uid,
            "role_name": self.role_name,
            "channel_name": self.channel_name,
            "status": self.status,
            "status_label": status_label(self.status),
            "message": self.message,
            "awards_text": self.awards_text,
            "extra_text": self.extra_text,
        }


def is_success_status(status: str | None) -> bool:
    return (status or "") in SUCCESS_STATUSES


def status_label(status: str | None) -> str:
    key = (status or "").strip()
    return STATUS_LABELS.get(key, key or "-")


def summarize_results(results: list[CheckinResult], *, empty_message: str) -> tuple[bool, str]:
    if not results:
        return False, empty_message
    okish = all(is_success_status(r.status) for r in results)
    lines = [
        f"[{r.game_name}] {r.role_name}（{r.channel_name}）：{r.message}" for r in results
    ]
    return okish, "\n".join(lines)


def results_to_api(results: list[CheckinResult]) -> list[dict[str, Any]]:
    return [r.to_api_dict() for r in results]


def log_row_to_api(
    *,
    id: int,
    game_code: str,
    game_name: str,
    role_uid: str,
    role_name: str | None,
    channel_name: str | None,
    status: str,
    message: str | None,
    awards_text: str | None,
    checkin_date: str,
    checked_at: Any,
) -> dict[str, Any]:
    """统一签到记录 API 字段（含 status_label）。"""
    return {
        "id": id,
        "game_code": game_code,
        "game_name": game_name,
        "role_uid": role_uid,
        "role_name": role_name,
        "channel_name": channel_name,
        "status": status,
        "status_label": status_label(status),
        "message": message,
        "awards_text": awards_text,
        "checkin_date": checkin_date,
        "checked_at": checked_at,
    }

