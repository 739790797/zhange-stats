"""签到公共模型与状态约定（森空岛 / 塔吉多 / 后续平台共用）。"""

from __future__ import annotations

import re
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
    # 结构化奖励（可选；方舟可含 icon_url）
    awards: list[dict[str, Any]] | None = None

    def to_api_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
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
        if self.awards:
            out["awards"] = self.awards
        return out


def is_success_status(status: str | None) -> bool:
    return (status or "") in SUCCESS_STATUSES


# 「奖励×2」等占位：签到响应缺物品名时的回退文案，不算完整奖励
_PLACEHOLDER_AWARDS = re.compile(
    r"^(?:奖励|reward)(?:\s*[×xX*＊]\s*\d+)?$",
    re.IGNORECASE,
)


def is_placeholder_awards(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True
    if _PLACEHOLDER_AWARDS.fullmatch(raw):
        return True
    # 多段里若全是占位也视为不完整
    parts = [p.strip() for p in re.split(r"[·，,、]", raw) if p.strip()]
    return bool(parts) and all(_PLACEHOLDER_AWARDS.fullmatch(p) for p in parts)


def awards_richness(text: str | None) -> tuple[int, int, int]:
    """越大越完整：(信息档, 分段数, 字符数)。占位文案档位最低。"""
    raw = (text or "").strip()
    if not raw:
        return (0, 0, 0)
    if is_placeholder_awards(raw):
        return (1, 0, len(raw))
    parts = [p.strip() for p in re.split(r"[·，,、/]", raw) if p.strip()]
    # 仅「积分+N」比带道具名的描述更弱
    only_score = bool(re.fullmatch(r"积分\s*[+＋]\s*\d+", raw))
    tier = 2 if only_score else 3
    return (tier, len(parts), len(raw))


def prefer_richer_awards(current: str | None, incoming: str | None) -> str | None:
    """合并奖励文案：保留更完整的一侧；「奖励×N」占位视为无效，可被清空或升级。"""
    cur = None if is_placeholder_awards(current) else (current or "").strip() or None
    inc = None if is_placeholder_awards(incoming) else (incoming or "").strip() or None
    if not inc:
        return cur
    if not cur:
        return inc
    if awards_richness(inc) >= awards_richness(cur):
        return inc
    return cur


def prefer_richer_award_items(
    current_text: str | None,
    current_items: list[dict[str, Any]] | None,
    incoming_text: str | None,
    incoming_items: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """与 prefer_richer_awards 同步选择结构化奖励列表；同等文案时优先带图标。"""
    merged = prefer_richer_awards(current_text, incoming_text)
    if merged is None:
        return None

    def _icon_score(items: list[dict[str, Any]] | None) -> int:
        if not items:
            return 0
        return sum(
            1
            for a in items
            if isinstance(a, dict) and str(a.get("icon_url") or "").strip()
        )

    cur_items = list(current_items) if current_items else None
    inc_items = list(incoming_items) if incoming_items else None
    inc = None if is_placeholder_awards(incoming_text) else (incoming_text or "").strip() or None
    if merged == inc and inc_items:
        # 文案同等时若旧列表图标更多，保留旧列表
        if (
            cur_items
            and awards_richness(current_text) == awards_richness(incoming_text)
            and _icon_score(cur_items) > _icon_score(inc_items)
        ):
            return cur_items
        return inc_items
    if cur_items:
        if inc_items and _icon_score(inc_items) > _icon_score(cur_items):
            return inc_items
        return cur_items
    if inc_items:
        return inc_items
    return None


def dumps_awards_json(awards: list[dict[str, Any]] | None) -> str | None:
    if not awards:
        return None
    import json

    return json.dumps(awards, ensure_ascii=False)


def loads_awards_json(raw: str | None) -> list[dict[str, Any]] | None:
    if not raw or not str(raw).strip():
        return None
    import json

    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, list) or not data:
        return None
    out: list[dict[str, Any]] = []
    for row in data:
        if isinstance(row, dict) and row.get("name"):
            out.append(row)
    return out or None


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
            awards=loads_awards_json(getattr(row, "awards_json", None)),
        )
        for row in rows
    ]


def today_done_from_logs(
    db: Any,
    log_model: Any,
    *,
    member_id: int,
    checkin_date: Any,
    role_keys: set[tuple[str, str]] | None = None,
) -> list[CheckinResult] | None:
    """今日 logs 全部为成功态则返回结果，否则 None。调度跳过以 logs 为准。

    role_keys: 仅检查这些 (game_code, role_uid)；为 None 时检查全日全部角色。
    """
    cached = load_day_checkin_results(
        db, log_model, member_id=member_id, checkin_date=checkin_date
    )
    if not cached:
        return None
    if role_keys is None:
        if all(is_success_status(r.status) for r in cached):
            return cached
        return None
    by_key = {(r.game_code, r.role_uid): r for r in cached}
    selected: list[CheckinResult] = []
    for key in role_keys:
        row = by_key.get(key)
        if row is None or not is_success_status(row.status):
            return None
        selected.append(row)
    return selected if selected else None


def apply_bind_last_checkin(
    bind: Any,
    *,
    now: Any,
    checkin_date: Any,
    ok: bool,
    summary: str,
) -> None:
    """写入 bind.last_checkin_*（反规范化：任务列表 / 兼容旧跳过逻辑）。

    今日按角色详情只信 *_checkin_logs；status 查询路径不得调用本函数。
    """
    bind.last_checkin_at = now
    bind.last_checkin_date = checkin_date
    bind.last_checkin_ok = ok
    bind.last_checkin_summary = summary
    if hasattr(bind, "updated_at"):
        bind.updated_at = now


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
                    **(
                        {"awards_json": dumps_awards_json(r.awards)}
                        if hasattr(log_model, "awards_json")
                        else {}
                    ),
                )
            )
        else:
            row.game_name = r.game_name or row.game_name
            row.role_name = r.role_name or row.role_name
            row.channel_name = r.channel_name or row.channel_name
            # 上游残缺查询（如 B 服 GET 无 records）不得把已签降成未签
            if not (
                is_success_status(row.status) and r.status == STATUS_PENDING
            ):
                row.status = r.status
            row.message = message or row.message
            # 奖励文案：同步残缺结果不得覆盖签到时已写入的完整明细
            prev_text = row.awards_text
            prev_items = loads_awards_json(getattr(row, "awards_json", None))
            row.awards_text = prefer_richer_awards(prev_text, r.awards_text)
            if hasattr(row, "awards_json"):
                row.awards_json = dumps_awards_json(
                    prefer_richer_award_items(
                        prev_text, prev_items, r.awards_text, r.awards
                    )
                )
            row.checked_at = now


def upsert_and_reload_day_results(
    db: Any,
    log_model: Any,
    *,
    member_id: int,
    bind_id: int,
    checkin_date: Any,
    results: list[CheckinResult],
    now: Any,
) -> list[CheckinResult]:
    """写入并读回合并后的今日结果（供接口返回，避免带回残缺 awards）。"""
    if results:
        upsert_day_checkin_logs(
            db,
            log_model,
            member_id=member_id,
            bind_id=bind_id,
            checkin_date=checkin_date,
            results=results,
            now=now,
        )
        db.flush()
    cached = load_day_checkin_results(
        db,
        log_model,
        member_id=member_id,
        checkin_date=checkin_date,
    )
    return cached if cached is not None else results


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

