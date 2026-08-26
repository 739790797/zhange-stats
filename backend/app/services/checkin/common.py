"""签到公共模型与状态约定（森空岛 / 塔吉多 / 后续平台共用）。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


STATUS_OK = "ok"
STATUS_ALREADY = "already"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"
STATUS_PENDING = "pending"
# 上游查询残缺、无法判定已签/未签（如方舟 B 服 GET records 常为空）
STATUS_UNKNOWN = "unknown"

SUCCESS_STATUSES = frozenset({STATUS_OK, STATUS_ALREADY})

# 今日 logs 来源：status=同步/查询缓存；action=真正执行签到
LOG_SOURCE_STATUS = "status"
LOG_SOURCE_ACTION = "action"

# 展示文案：ok / already 统一为「已签」
STATUS_LABELS: dict[str, str] = {
    STATUS_OK: "已签",
    STATUS_ALREADY: "已签",
    STATUS_ERROR: "失败",
    STATUS_SKIPPED: "跳过",
    STATUS_PENDING: "未签",
    STATUS_UNKNOWN: "待确认",
}


def format_upstream_request(
    method: str,
    url: str,
    body: Any = None,
) -> str:
    """管理端排障用：METHOD URL + body（不含敏感头）。"""
    lines = [f"{(method or 'GET').upper()} {url}".rstrip()]
    if body is None:
        return lines[0]
    if isinstance(body, (dict, list)):
        lines.append(json.dumps(body, ensure_ascii=False, indent=2))
    else:
        text = str(body).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def format_upstream_response(payload: Any) -> str | None:
    """管理端排障用：上游 HTTP body 原文（优先 pretty JSON）。"""
    if payload is None:
        return None
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False, indent=2)
    text = str(payload).strip()
    return text or None


@dataclass
class CheckinResult:
    game_code: str
    game_name: str
    role_uid: str
    role_name: str
    channel_name: str
    status: str  # ok | already | error | skipped | pending | unknown
    message: str
    awards_text: str | None = None
    extra_text: str | None = None
    # 结构化奖励（可选；方舟可含 icon_url）
    awards: list[dict[str, Any]] | None = None
    # 管理端排障：上游 HTTP 原文（不进用户侧 to_api_dict）
    upstream_request: str | None = None
    upstream_response: str | None = None

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
# 塔吉多等：经验流水把浏览/点赞任务误当成「今日奖励」
_TASK_EXP_AWARD_POLLUTION = re.compile(r"(点赞帖子|浏览帖子|分享帖子)")
# 旧版误用经验「签到奖励+N」；应被任务中心「塔塔币+N」覆盖
_WEAK_EXP_SIGNIN_AWARDS = re.compile(r"^签到奖励")


def is_placeholder_awards(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True
    if _PLACEHOLDER_AWARDS.fullmatch(raw):
        return True
    # 多段里若全是占位也视为不完整
    parts = [p.strip() for p in re.split(r"[·，,、]", raw) if p.strip()]
    return bool(parts) and all(_PLACEHOLDER_AWARDS.fullmatch(p) for p in parts)


def is_polluted_task_exp_awards(text: str | None) -> bool:
    """任务经验误入奖励文案（点赞/浏览帖子刷屏）视为无效，允许被清空或覆盖。"""
    raw = (text or "").strip()
    return bool(raw) and bool(_TASK_EXP_AWARD_POLLUTION.search(raw))


def is_weak_exp_signin_awards(text: str | None) -> bool:
    """经验流水里的「签到奖励」弱于官方塔塔币签到奖励。"""
    raw = (text or "").strip()
    return bool(raw) and bool(_WEAK_EXP_SIGNIN_AWARDS.match(raw))


def _awards_items_polluted(items: list[dict[str, Any]] | None) -> bool:
    if not items:
        return False
    for a in items:
        if not isinstance(a, dict):
            continue
        name = str(a.get("name") or "")
        if _TASK_EXP_AWARD_POLLUTION.search(name):
            return True
    return False


def _awards_items_weak_exp_signin(items: list[dict[str, Any]] | None) -> bool:
    if not items:
        return False
    names = [
        str(a.get("name") or "")
        for a in items
        if isinstance(a, dict) and a.get("name")
    ]
    if not names:
        return False
    return all(n == "签到奖励" or n == "签到" for n in names)


def award_item(
    *,
    name: str,
    count: int = 1,
    resource_id: Any = None,
    resource_type: Any = None,
    icon_url: str | None = None,
) -> dict[str, Any]:
    """跨平台结构化奖励条目（落 awards_json / API awards）。"""
    item: dict[str, Any] = {"name": str(name).strip() or "奖励", "count": int(count)}
    if resource_id is not None and str(resource_id).strip():
        item["resource_id"] = str(resource_id).strip()
    rtype = str(resource_type).strip() if resource_type is not None else ""
    if rtype:
        item["resource_type"] = rtype
    if icon_url and str(icon_url).strip():
        item["icon_url"] = str(icon_url).strip()
    return item


def awards_text_from_items(items: list[dict[str, Any]] | None) -> str | None:
    if not items:
        return None
    parts: list[str] = []
    for a in items:
        if not isinstance(a, dict) or not a.get("name"):
            continue
        name = str(a["name"]).strip()
        try:
            count = int(a.get("count") or 1)
        except (TypeError, ValueError):
            count = 1
        parts.append(f"{name}x{count}")
    return "、".join(parts) if parts else None


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
    """合并奖励文案：保留更完整的一侧；占位 / 任务经验污染视为无效，可被清空或升级。"""
    cur_raw = (current or "").strip() or None
    inc_raw = (incoming or "").strip() or None
    cur = (
        None
        if (
            is_placeholder_awards(cur_raw)
            or is_polluted_task_exp_awards(cur_raw)
            or is_weak_exp_signin_awards(cur_raw)
        )
        else cur_raw
    )
    inc = (
        None
        if (
            is_placeholder_awards(inc_raw)
            or is_polluted_task_exp_awards(inc_raw)
            or is_weak_exp_signin_awards(inc_raw)
        )
        else inc_raw
    )
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
    # 污染 / 弱经验签到条目视为无效，避免盖住任务中心塔塔币
    if _awards_items_polluted(current_items) or _awards_items_weak_exp_signin(
        current_items
    ):
        current_items = None
        if is_polluted_task_exp_awards(current_text) or is_weak_exp_signin_awards(
            current_text
        ):
            current_text = None
    if _awards_items_polluted(incoming_items) or _awards_items_weak_exp_signin(
        incoming_items
    ):
        incoming_items = None
        if is_polluted_task_exp_awards(incoming_text) or is_weak_exp_signin_awards(
            incoming_text
        ):
            incoming_text = None

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
    inc = (
        None
        if (
            is_placeholder_awards(incoming_text)
            or is_polluted_task_exp_awards(incoming_text)
            or is_weak_exp_signin_awards(incoming_text)
        )
        else (incoming_text or "").strip() or None
    )
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


def _is_bilibili_channel(channel_name: str | None) -> bool:
    name = (channel_name or "").strip().lower()
    if not name:
        return False
    return (
        "bilibili" in name
        or "哔哩" in (channel_name or "")
        or "b服" in name
        or "b 服" in name
    )


_QUERY_PENDING_MESSAGES = frozenset(
    {
        "今日尚未签到",
        "今日未签到",
        "尚未签到",
    }
)


def display_checkin_awards_summary(
    *,
    awards_text: str | None,
    message: str | None = None,
    status: str | None = None,
    channel_name: str | None = None,
    game_code: str | None = None,
) -> str | None:
    """执行记录摘要：优先 award；B 服无奖固定提示；不回落查询态「尚未签到」。"""
    del game_code  # 预留
    text = (awards_text or "").strip()
    if text:
        return text
    msg = (message or "").strip()
    bili = _is_bilibili_channel(channel_name)
    pending_like = msg in _QUERY_PENDING_MESSAGES or "尚未签到" in msg
    if is_success_status(status):
        if bili:
            return "B服不支持查询"
        if pending_like:
            return None
        # 「今日已签到」是状态句，不是奖励；只抽取「获得：」后的明细
        for prefix in (
            "今日已签到，获得：",
            "今日已签到：",
            "签到成功，获得：",
            "签到成功：",
        ):
            if msg.startswith(prefix):
                rest = msg[len(prefix) :].strip()
                return rest or None
        if "获得：" in msg:
            rest = msg.split("获得：", 1)[1].strip()
            return rest or None
        return None
    return msg or None


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


def upsert_day_checkin_logs(
    db: Any,
    log_model: Any,
    *,
    member_id: int,
    bind_id: int,
    checkin_date: Any,
    results: list[CheckinResult],
    now: Any,
    source: str = LOG_SOURCE_STATUS,
) -> None:
    """按今日角色键 upsert 签到/查询结果。

    source=status：打开页/同步官方的查询缓存。
    source=action：立即签到或调度真正执行。
    已有 action 行不会被 status 写回降成 status。
    """
    source = (
        LOG_SOURCE_ACTION
        if source == LOG_SOURCE_ACTION
        else LOG_SOURCE_STATUS
    )
    for r in results:
        role_uid = str(r.role_uid or "-")
        game_code = str(r.game_code or "")
        message = r.message or ""
        if r.extra_text:
            message = f"{message}\n{r.extra_text}" if message else r.extra_text
        # 明日方舟执行记录：成功态只落 award，不写状态句
        awards_text = r.awards_text
        if (
            source == LOG_SOURCE_ACTION
            and game_code == "arknights"
            and is_success_status(r.status)
        ):
            awards_text = (r.awards_text or "").strip() or None
            message = awards_text or ""
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
        extra: dict[str, Any] = {}
        if hasattr(log_model, "awards_json"):
            extra["awards_json"] = dumps_awards_json(r.awards)
        if row is None:
            create_kw: dict[str, Any] = dict(
                member_id=member_id,
                bind_id=bind_id,
                game_code=game_code,
                game_name=r.game_name or game_code,
                role_uid=role_uid,
                role_name=r.role_name or None,
                channel_name=r.channel_name or None,
                status=r.status,
                message=message or None,
                awards_text=awards_text,
                checkin_date=checkin_date,
                checked_at=now,
                **extra,
            )
            if hasattr(log_model, "source"):
                create_kw["source"] = source
            db.add(log_model(**create_kw))
        else:
            row.game_name = r.game_name or row.game_name
            row.role_name = r.role_name or row.role_name
            row.channel_name = r.channel_name or row.channel_name
            # 上游残缺查询（如 B 服 GET 无 records）不得把已签降成未签/待确认
            status_protected = is_success_status(row.status) and r.status in (
                STATUS_PENDING,
                STATUS_UNKNOWN,
            )
            if not status_protected:
                row.status = r.status
                # 状态被保护时，勿用「今日尚未签到」等查询文案覆盖执行摘要
                row.message = message or row.message
            # 奖励文案：同步残缺 / B 服「已签」空 awards 不得覆盖此前 POST 落库的明细
            prev_text = row.awards_text
            prev_items = loads_awards_json(getattr(row, "awards_json", None))
            row.awards_text = prefer_richer_awards(prev_text, awards_text)
            if hasattr(row, "awards_json"):
                row.awards_json = dumps_awards_json(
                    prefer_richer_award_items(
                        prev_text, prev_items, awards_text, r.awards
                    )
                )
            if (
                source == LOG_SOURCE_ACTION
                and game_code == "arknights"
                and is_success_status(r.status)
            ):
                # 方舟执行摘要只保留 award（合并后），不写「今日已签到」等状态句
                row.message = row.awards_text or ""
            # action 优先：status 同步不得把已执行记录改回「仅查询」
            if hasattr(row, "source"):
                prev_source = str(getattr(row, "source", "") or LOG_SOURCE_STATUS)
                if source == LOG_SOURCE_ACTION or prev_source != LOG_SOURCE_ACTION:
                    row.source = source
                if source == LOG_SOURCE_ACTION:
                    row.checked_at = now
                elif prev_source != LOG_SOURCE_ACTION:
                    row.checked_at = now
            else:
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
    source: str = LOG_SOURCE_STATUS,
) -> list[CheckinResult]:
    """写入并读回合并后的今日结果（供接口返回，避免带回残缺 awards）。

    logs 无独立 extra_text 列（写入时并入 message）；读回后从现场 results
    按角色键回填，避免追放每日任务等展示字段丢失。
    """
    if results:
        upsert_day_checkin_logs(
            db,
            log_model,
            member_id=member_id,
            bind_id=bind_id,
            checkin_date=checkin_date,
            results=results,
            now=now,
            source=source,
        )
        db.flush()
    cached = load_day_checkin_results(
        db,
        log_model,
        member_id=member_id,
        checkin_date=checkin_date,
    )
    if cached is None:
        return results
    extras = {
        (str(r.game_code or ""), str(r.role_uid or "")): r.extra_text
        for r in results
        if r.extra_text
    }
    if not extras:
        return cached
    for row in cached:
        key = (str(row.game_code or ""), str(row.role_uid or ""))
        text = extras.get(key)
        if text:
            row.extra_text = text
    return cached

