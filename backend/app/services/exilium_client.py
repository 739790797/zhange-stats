"""少女前线2：追放官方社区（gf2-bbs）HTTP 客户端。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from app.services.checkin_common import CheckinResult

logger = logging.getLogger(__name__)

API_BASE = "https://gf2-bbs-api.exiliumgf.com"
BBS_ORIGIN = "https://gf2-bbs.exiliumgf.com"
# 官方前端硬编码的 AES-128 密钥（全站共用，非用户密钥）
AES_KEY = b"a86a86^oH$04r6A1"

GAME_CODE = "exilium_bbs"
GAME_NAME = "追放社区"

REQUEST_TIMEOUT = 25

COMMON_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": BBS_ORIGIN,
    "Referer": f"{BBS_ORIGIN}/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


class ExiliumApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        data: Any = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data


class ExiliumNeedGraphCaptcha(ExiliumApiError):
    """发送短信时需要图形验证码。"""

    def __init__(self, image: str):
        super().__init__("需要图形验证码", code=1008, data={"image": image})
        self.image = image


@dataclass
class ExiliumCredentials:
    token: str
    account_name: str | None = None
    password: str | None = None  # 明文仅存于加密凭证中，用于 token 失效后重登
    source: str | None = None  # phone | mail
    nickname: str | None = None
    user_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        data = {"token": self.token}
        if self.account_name:
            data["account_name"] = self.account_name
        if self.password:
            data["password"] = self.password
        if self.source:
            data["source"] = self.source
        if self.nickname:
            data["nickname"] = self.nickname
        if self.user_id:
            data["user_id"] = self.user_id
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ExiliumCredentials:
        token = str(raw.get("token") or "").strip()
        if not token:
            raise ExiliumApiError("凭证缺少 token")
        return cls(
            token=token,
            account_name=(str(raw["account_name"]).strip() if raw.get("account_name") else None),
            password=(str(raw["password"]) if raw.get("password") else None),
            source=(str(raw["source"]).strip() if raw.get("source") else None),
            nickname=(str(raw["nickname"]).strip() if raw.get("nickname") else None),
            user_id=(str(raw["user_id"]).strip() if raw.get("user_id") else None),
        )


def mask_account(account: str | None) -> str | None:
    text = (account or "").strip()
    if not text:
        return None
    if "@" in text:
        local, _, domain = text.partition("@")
        if len(local) <= 2:
            return f"*@{domain}"
        return f"{local[:2]}***@{domain}"
    if len(text) >= 7 and text.isdigit():
        return f"{text[:3]}****{text[-4:]}"
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}***{text[-2:]}"


def detect_source(account: str) -> str:
    return "mail" if "@" in account.strip() else "phone"


def _aes_encrypt(plain: str) -> str:
    key = AES_KEY
    padder = PKCS7(128).padder()
    padded = padder.update(plain.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(key))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    b64 = base64.b64encode(encrypted).decode("ascii")
    return b64.replace("+", "-").replace("/", "_").rstrip("=")


def encrypt_account_name(account: str) -> str:
    return _aes_encrypt(account.strip())


def encrypt_password(password: str) -> str:
    # 官方前端：先 MD5(明文密码) 再 AES
    digest = hashlib.md5(password.encode("utf-8")).hexdigest()
    return _aes_encrypt(digest)


def friendly_error_message(message: str | None) -> str:
    text = (message or "").strip() or "追放社区请求失败"
    mapping = {
        "token": "登录已失效，请重新绑定",
        "登录": "登录失败，请检查账号或重新绑定",
        "密码": "账号或密码错误",
        "验证码": "验证码错误或已过期",
        "积分": "积分不足",
        "上限": "已达兑换上限",
        "限购": "已达兑换上限",
    }
    for key, tip in mapping.items():
        if key in text:
            return tip
    return text


def _http(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> dict[str, Any]:
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    headers = dict(COMMON_HEADERS)
    data = None
    if method.upper() == "POST":
        headers["Content-Type"] = "application/json"
        data = json.dumps(body if body is not None else {}, ensure_ascii=False).encode(
            "utf-8"
        )
    if token:
        headers["Authorization"] = token

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        status = exc.code
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            raise ExiliumApiError(f"HTTP {status}", code=status) from exc
        if isinstance(payload, dict):
            code = payload.get("Code")
            msg = str(payload.get("Message") or f"HTTP {status}")
            raise ExiliumApiError(msg, code=int(code) if code is not None else status, data=payload.get("data")) from exc
        raise ExiliumApiError(f"HTTP {status}", code=status) from exc
    except urllib.error.URLError as exc:
        raise ExiliumApiError(f"无法连接追放社区: {exc}") from exc

    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ExiliumApiError("追放社区返回非 JSON") from exc
    if not isinstance(payload, dict):
        raise ExiliumApiError("追放社区返回格式无效")

    code = payload.get("Code")
    if code is not None and int(code) != 0:
        msg = str(payload.get("Message") or f"业务错误 Code={code}")
        raise ExiliumApiError(msg, code=int(code), data=payload.get("data"))
    if status >= 400:
        raise ExiliumApiError(f"HTTP {status}", code=status)
    data_out = payload.get("data")
    return data_out if isinstance(data_out, dict) else {"_raw": data_out}


def login_with_password(account: str, password: str) -> ExiliumCredentials:
    account = account.strip()
    if not account or not password:
        raise ExiliumApiError("请填写账号和密码")
    source = detect_source(account)
    data = _http(
        "POST",
        "/login/account",
        body={
            "account_name": encrypt_account_name(account),
            "passwd": encrypt_password(password),
            "source": source,
        },
    )
    account_info = data.get("account") if isinstance(data.get("account"), dict) else {}
    token = str(account_info.get("token") or "").strip()
    if not token:
        raise ExiliumApiError("登录成功但未返回 token")
    creds = ExiliumCredentials(
        token=token,
        account_name=account,
        password=password,
        source=source,
    )
    try:
        enrich_user_info(creds)
    except ExiliumApiError:
        logger.warning("exilium login ok but fetch user info failed")
    return creds


def send_sms(account: str, graph_code: str | None = None) -> None:
    """发送短信验证码。若需图形验证码则抛出 ExiliumNeedGraphCaptcha。"""
    account = account.strip()
    if not re.fullmatch(r"1\d{10}", account):
        raise ExiliumApiError("请输入有效的大陆手机号")
    body: dict[str, Any] = {
        "account_name": encrypt_account_name(account),
        "graph_code": (graph_code or "").strip(),
    }
    try:
        _http("POST", "/login/send_msg", body=body)
    except ExiliumApiError as exc:
        if exc.code == 1008:
            image = ""
            if isinstance(exc.data, dict):
                image = str(exc.data.get("code") or exc.data.get("img") or "")
            elif isinstance(exc.data, str):
                image = exc.data
            if image:
                raise ExiliumNeedGraphCaptcha(image) from exc
        raise


def login_with_sms(account: str, code: str) -> ExiliumCredentials:
    account = account.strip()
    code = (code or "").strip()
    if not re.fullmatch(r"1\d{10}", account):
        raise ExiliumApiError("请输入有效的大陆手机号")
    if not code:
        raise ExiliumApiError("请填写短信验证码")
    data = _http(
        "POST",
        "/login/sms",
        body={
            "account_name": encrypt_account_name(account),
            "code": code,
        },
    )
    account_info = data.get("account") if isinstance(data.get("account"), dict) else {}
    token = str(account_info.get("token") or "").strip()
    if not token:
        raise ExiliumApiError("登录成功但未返回 token")
    creds = ExiliumCredentials(
        token=token,
        account_name=account,
        source="phone",
    )
    try:
        enrich_user_info(creds)
    except ExiliumApiError:
        logger.warning("exilium sms login ok but fetch user info failed")
    return creds


@dataclass
class ExchangeItem:
    exchange_id: int
    item_name: str
    item_count: int
    item_pic: str
    item_context: str
    use_score: int
    exchange_count: int
    max_exchange_count: int
    cycle: str  # day | month | life
    remain_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exchange_id": self.exchange_id,
            "item_name": self.item_name,
            "item_count": self.item_count,
            "item_pic": self.item_pic,
            "item_context": self.item_context,
            "use_score": self.use_score,
            "exchange_count": self.exchange_count,
            "max_exchange_count": self.max_exchange_count,
            "cycle": self.cycle,
            "remain_seconds": self.remain_seconds,
        }


def _parse_user_payload(data: dict[str, Any]) -> dict[str, Any]:
    user = data.get("user") if isinstance(data.get("user"), dict) else data
    return user if isinstance(user, dict) else {}


def enrich_user_info(creds: ExiliumCredentials) -> ExiliumCredentials:
    data = _http("POST", "/community/member/info", token=creds.token, body={})
    user = _parse_user_payload(data)
    nick = user.get("nick_name") or user.get("nickname") or user.get("name")
    uid = user.get("user_id") or user.get("id") or user.get("uid")
    if nick:
        creds.nickname = str(nick).strip()
    if uid is not None:
        creds.user_id = str(uid).strip()
    return creds


def get_user_score(creds: ExiliumCredentials) -> int:
    data = _http("POST", "/community/member/info", token=creds.token, body={})
    user = _parse_user_payload(data)
    try:
        return int(user.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_remain_seconds(raw: dict[str, Any]) -> int | None:
    for key in ("remain_seconds", "remain_time", "left_time", "countdown"):
        if raw.get(key) is None:
            continue
        try:
            n = int(raw[key])
            return n if n >= 0 else None
        except (TypeError, ValueError):
            continue
    return None


def list_exchange_items(creds: ExiliumCredentials) -> list[ExchangeItem]:
    data = _http("GET", "/community/item/exchange_list", token=creds.token)
    raw_list = data.get("list") if isinstance(data.get("list"), list) else []
    items: list[ExchangeItem] = []
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        exchange_id = _to_int(row.get("exchange_id"), -1)
        if exchange_id < 0:
            continue
        items.append(
            ExchangeItem(
                exchange_id=exchange_id,
                item_name=str(row.get("item_name") or "").strip() or f"物品#{exchange_id}",
                item_count=_to_int(row.get("item_count"), 1),
                item_pic=str(row.get("item_pic") or "").strip(),
                item_context=str(row.get("item_context") or "").strip(),
                use_score=_to_int(row.get("use_score"), 0),
                exchange_count=_to_int(row.get("exchange_count"), 0),
                max_exchange_count=_to_int(row.get("max_exchange_count"), 0),
                cycle=str(row.get("cycle") or "day").strip().lower() or "day",
                remain_seconds=_parse_remain_seconds(row),
            )
        )
    return items


def exchange_item(creds: ExiliumCredentials, exchange_id: int) -> dict[str, Any]:
    if exchange_id <= 0:
        raise ExiliumApiError("无效的兑换物品")
    try:
        data = _http(
            "POST",
            "/community/item/exchange",
            token=creds.token,
            body={"exchange_id": int(exchange_id)},
        )
    except ExiliumApiError as exc:
        raise ExiliumApiError(
            friendly_error_message(exc.message) or "兑换失败",
            code=exc.code,
            data=exc.data,
        ) from exc
    return data if isinstance(data, dict) else {}


@dataclass
class ScoreLogItem:
    score: int
    reason: str
    log_time: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "reason": self.reason,
            "log_time": self.log_time,
        }


def list_score_logs(
    creds: ExiliumCredentials,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    data = _http(
        "GET",
        f"/community/member/score_log?page={page}&page_size={page_size}",
        token=creds.token,
    )
    raw_list = data.get("list") if isinstance(data.get("list"), list) else []
    items: list[ScoreLogItem] = []
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        items.append(
            ScoreLogItem(
                score=_to_int(row.get("score"), 0),
                reason=str(row.get("reason") or "").strip() or "积分变动",
                log_time=str(row.get("log_time") or "").strip(),
            )
        )
    return {
        "list": [item.to_dict() for item in items],
        "total": _to_int(data.get("total"), len(items)),
        "page": page,
        "page_size": page_size,
    }


def ensure_session(creds: ExiliumCredentials) -> ExiliumCredentials:
    """探活；失败且有密码则重登。"""
    try:
        enrich_user_info(creds)
        return creds
    except ExiliumApiError as exc:
        if creds.account_name and creds.password:
            logger.info("exilium token invalid, re-login with password")
            return login_with_password(creds.account_name, creds.password)
        raise ExiliumApiError(
            friendly_error_message(exc.message) or "登录已失效，请重新绑定",
            code=exc.code,
        ) from exc


def get_sign_in_status(creds: ExiliumCredentials) -> bool:
    data = _http(
        "GET",
        "/community/task/get_current_sign_in_status",
        token=creds.token,
    )
    return bool(data.get("has_sign_in"))


def sign_in(creds: ExiliumCredentials) -> CheckinResult:
    data = _http("POST", "/community/task/sign_in", token=creds.token, body={})
    item = str(data.get("get_item_name") or "").strip()
    count = data.get("get_item_count")
    exp = data.get("get_exp")
    score = data.get("get_score")
    parts: list[str] = []
    if item:
        parts.append(f"{item}*{count}" if count is not None else item)
    if exp is not None:
        parts.append(f"经验+{exp}")
    if score is not None:
        parts.append(f"积分+{score}")
    awards = "，".join(parts) if parts else None
    role_name = creds.nickname or mask_account(creds.account_name) or "社区账号"
    return CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=creds.user_id or creds.account_name or "-",
        role_name=role_name,
        channel_name="官方社区",
        status="ok",
        message="签到成功" + (f"：{awards}" if awards else ""),
        awards_text=awards,
    )


def _awards_from_score_log(creds: ExiliumCredentials) -> str | None:
    """已签到时官方不再返回奖励明细，从积分变动记录（points_Log）补全。"""
    from app.core.timeutil import today as beijing_today

    try:
        data = list_score_logs(creds, page=1, page_size=30)
    except ExiliumApiError:
        return None
    day = beijing_today().isoformat()
    for row in data.get("list") or []:
        if not isinstance(row, dict):
            continue
        reason = str(row.get("reason") or "").strip()
        log_time = str(row.get("log_time") or "").strip()
        if reason != "签到":
            continue
        if not log_time.startswith(day):
            continue
        score = _to_int(row.get("score"), 0)
        return f"积分+{score}" if score else "签到奖励已发放"
    return None


def _today_task_score_summary(creds: ExiliumCredentials) -> tuple[int, int]:
    """今日「任务」积分条目数与总分（浏览/点赞/分享完成后各记一条）。"""
    from app.core.timeutil import today as beijing_today

    try:
        data = list_score_logs(creds, page=1, page_size=30)
    except ExiliumApiError:
        return 0, 0
    day = beijing_today().isoformat()
    count = 0
    total = 0
    for row in data.get("list") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("reason") or "").strip() != "任务":
            continue
        if not str(row.get("log_time") or "").startswith(day):
            continue
        count += 1
        total += _to_int(row.get("score"), 0)
    return count, total


def _tasks_extra_text(*, view: int, like: int, share: int, score: int | None = None) -> str:
    parts = [f"浏览 {view}/3", f"点赞 {like}/3", f"分享 {share}/1"]
    text = "每日任务：" + " · ".join(parts)
    if score and score > 0:
        text += f"（积分+{score}）"
    return text


def list_topic_ids(
    creds: ExiliumCredentials,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """拉取帖子列表（含 topic_id / is_like）。"""
    data = _http(
        "GET",
        "/community/topic/list?sort_type=2",
        token=creds.token,
    )
    raw = data.get("list") if isinstance(data.get("list"), list) else []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        tid = _to_int(row.get("topic_id"), 0)
        if tid <= 0:
            continue
        out.append(
            {
                "topic_id": tid,
                "is_like": bool(row.get("is_like")),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out


def view_topic(creds: ExiliumCredentials, topic_id: int) -> None:
    tid = int(topic_id)
    _http("GET", f"/community/topic/{tid}?id={tid}", token=creds.token)


def like_topic(creds: ExiliumCredentials, topic_id: int) -> None:
    tid = int(topic_id)
    _http("GET", f"/community/topic/like/{tid}?id={tid}", token=creds.token)


def share_topic(creds: ExiliumCredentials, topic_id: int) -> None:
    tid = int(topic_id)
    _http("GET", f"/community/topic/share/{tid}?id={tid}", token=creds.token)


def complete_daily_tasks(creds: ExiliumCredentials) -> dict[str, Any]:
    """完成每日任务：浏览×3、点赞×3、分享×1。"""
    import time

    before_count, before_score = _today_task_score_summary(creds)
    if before_count >= 3:
        return {
            "view": 3,
            "like": 3,
            "share": 1,
            "score": before_score,
            "skipped": True,
            "text": _tasks_extra_text(view=3, like=3, share=1, score=before_score),
        }

    topics = list_topic_ids(creds, limit=5)
    if len(topics) < 3:
        raise ExiliumApiError("帖子列表不足，无法完成每日任务")

    view_n = 0
    like_n = 0
    share_n = 0
    errors: list[str] = []

    for item in topics[:3]:
        tid = int(item["topic_id"])
        try:
            view_topic(creds, tid)
            view_n += 1
        except ExiliumApiError as exc:
            errors.append(f"浏览失败:{exc.message}")
        time.sleep(0.35)

    for item in topics[:3]:
        tid = int(item["topic_id"])
        try:
            # 已点赞则跳过，避免 toggle 取消
            if not item.get("is_like"):
                like_topic(creds, tid)
            like_n += 1
        except ExiliumApiError as exc:
            errors.append(f"点赞失败:{exc.message}")
        time.sleep(0.35)

    try:
        share_topic(creds, int(topics[0]["topic_id"]))
        share_n = 1
    except ExiliumApiError as exc:
        errors.append(f"分享失败:{exc.message}")

    after_count, after_score = _today_task_score_summary(creds)
    gained = max(0, after_score - before_score)
    text = _tasks_extra_text(
        view=view_n,
        like=like_n,
        share=share_n,
        score=after_score if after_count else gained,
    )
    if errors:
        text += "（部分失败）"
    return {
        "view": view_n,
        "like": like_n,
        "share": share_n,
        "score": after_score,
        "gained": gained,
        "skipped": False,
        "text": text,
        "errors": errors,
    }


def _attach_daily_tasks(creds: ExiliumCredentials, result: CheckinResult) -> CheckinResult:
    """在签到结果上附加每日任务执行情况。"""
    if result.status == "error":
        return result
    try:
        tasks = complete_daily_tasks(creds)
        result.extra_text = str(tasks.get("text") or "") or None
    except ExiliumApiError as exc:
        result.extra_text = f"每日任务失败：{exc.message}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("exilium daily tasks failed")
        result.extra_text = f"每日任务失败：{exc}"
    return result


def _tasks_extra_from_score_log(creds: ExiliumCredentials) -> str | None:
    count, score = _today_task_score_summary(creds)
    if count <= 0:
        return "每日任务：未完成（点击立即签到可一并完成）"
    if count >= 3:
        return _tasks_extra_text(view=3, like=3, share=1, score=score)
    return f"每日任务：已领 {count}/3 项（积分+{score}）"


def _already_result(creds: ExiliumCredentials) -> CheckinResult:
    role_name = creds.nickname or mask_account(creds.account_name) or "社区账号"
    awards = _awards_from_score_log(creds)
    return CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=creds.user_id or creds.account_name or "-",
        role_name=role_name,
        channel_name="官方社区",
        status="already",
        message="今日已签到" + (f"：{awards}" if awards else ""),
        awards_text=awards,
    )


def query_today(creds: ExiliumCredentials) -> tuple[ExiliumCredentials, list[CheckinResult]]:
    working = ensure_session(creds)
    signed = get_sign_in_status(working)
    if signed:
        result = _already_result(working)
        result.extra_text = _tasks_extra_from_score_log(working)
        return working, [result]
    role_name = working.nickname or mask_account(working.account_name) or "社区账号"
    result = CheckinResult(
        game_code=GAME_CODE,
        game_name=GAME_NAME,
        role_uid=working.user_id or working.account_name or "-",
        role_name=role_name,
        channel_name="官方社区",
        status="pending",
        message="今日未签到",
        extra_text=_tasks_extra_from_score_log(working),
    )
    return working, [result]


def checkin(creds: ExiliumCredentials, *, force: bool = False) -> tuple[ExiliumCredentials, CheckinResult]:
    _ = force
    working = ensure_session(creds)
    signed = get_sign_in_status(working)
    if signed:
        result = _already_result(working)
    else:
        try:
            result = sign_in(working)
        except ExiliumApiError as exc:
            msg = exc.message or ""
            already = any(k in msg for k in ("已签到", "重复", "already", "签到过"))
            if already:
                result = _already_result(working)
            else:
                role_name = working.nickname or mask_account(working.account_name) or "社区账号"
                result = CheckinResult(
                    game_code=GAME_CODE,
                    game_name=GAME_NAME,
                    role_uid=working.user_id or working.account_name or "-",
                    role_name=role_name,
                    channel_name="官方社区",
                    status="error",
                    message=friendly_error_message(msg),
                )
                return working, result
    return working, _attach_daily_tasks(working, result)
