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


def day_results_payload(results: list[CheckinResult]) -> dict[str, Any]:
    """组装 status 用的今日结果（不访问上游）。"""
    if results:
        ok = all(r.status != "error" for r in results)
        summary = "\n".join(
            f"[{r.game_name}] {r.role_name}（{r.channel_name}）：{r.message}"
            for r in results
        )
    else:
        ok, summary = False, "未找到可签到目标"
    return {
        "ok": ok,
        "summary": summary,
        "results": results_to_api(results),
        "token_ok": True,
    }


def load_day_checkin_results(
    db: Any,
    log_model: Any,
    *,
    member_id: int,
    checkin_date: Any,
) -> list[CheckinResult] | None:
    """有今日日志则返回；无则 None（调用方应回源）。"""
    rows = (
        db.query(log_model)
        .filter(
            log_model.member_id == member_id,
            log_model.checkin_date == checkin_date,
        )
        .all()
    )
    if not rows:
        return None
    return [
        CheckinResult(
            game_code=str(row.game_code or ""),
            game_name=str(row.game_name or ""),
            role_uid=str(row.role_uid or ""),
            role_name=str(row.role_name or ""),
            channel_name=str(row.channel_name or ""),
            status=str(row.status or "pending"),
            message=str(row.message or ""),
            awards_text=row.awards_text,
        )
        for row in rows
    ]


def upsert_day_checkin_logs(
    db: Any,
    log_model: Any,
    *,
    member_id: int,
    bind_id: int,
    checkin_date: Any,
    results: list[CheckinResult],
    now: Any,
) -> None:
    """按今日角色键 upsert 签到/查询结果。"""
    for r in results:
        role_uid = str(r.role_uid or "-")
        game_code = str(r.game_code or "")
        message = r.message or ""
        if r.extra_text:
            message = f"{message}\n{r.extra_text}" if message else r.extra_text
        row = (
            db.query(log_model)
            .filter(
                log_model.member_id == member_id,
                log_model.checkin_date == checkin_date,
                log_model.game_code == game_code,
                log_model.role_uid == role_uid,
            )
            .one_or_none()
        )
        if row is None:
            db.add(
                log_model(
                    member_id=member_id,
                    bind_id=bind_id,
                    game_code=game_code,
                    game_name=r.game_name or game_code,
                    role_uid=role_uid,
                    role_name=r.role_name or None,
                    channel_name=r.channel_name or None,
                    status=r.status,
                    message=message or None,
                    awards_text=r.awards_text,
                    checkin_date=checkin_date,
                    checked_at=now,
                )
            )
        else:
            row.game_name = r.game_name or row.game_name
            row.role_name = r.role_name or row.role_name
            row.channel_name = r.channel_name or row.channel_name
            row.status = r.status
            row.message = message or None
            row.awards_text = r.awards_text
            row.checked_at = now


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

