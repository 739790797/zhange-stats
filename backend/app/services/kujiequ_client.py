"""库街区（Kurobbs）HTTP 客户端：短信登录、社区签到、战双/鸣潮游戏签到。"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from app.core.timeutil import now_naive, today
from app.services.checkin_common import CheckinResult

logger = logging.getLogger(__name__)

API_BASE = "https://api.kurobbs.com"
GAME_PGR = 2  # 战双帕弥什
GAME_WW = 3  # 鸣潮
GAME_NAMES = {GAME_PGR: "战双帕弥什", GAME_WW: "鸣潮"}

# App 客户端头（参考社区公开实现）
APP_VERSION = "2.2.1"
APP_VERSION_CODE = "2210"

# 库街区 APP 端极验 captchaId（官方人机验证，非绕过）
GEETEST_CAPTCHA_ID = "3f7e2d848ce0cb7e7d019d621e556ce2"


class KujiequApiError(Exception):
    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass
class KujiequCredentials:
    token: str
    user_id: str = ""
    user_name: str = ""
    phone: str = ""
    refresh_token: str = ""
    distinct_id: str = ""
    dev_code: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: str(v or "") for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KujiequCredentials:
        token = str(
            data.get("token")
            or data.get("access_token")
            or data.get("user_token")
            or ""
        ).strip()
        if not token:
            raise KujiequApiError("缺少 token，请粘贴库街区登录 token")
        return cls(
            token=token,
            user_id=str(data.get("user_id") or data.get("userId") or "").strip(),
            user_name=str(data.get("user_name") or data.get("userName") or "").strip(),
            phone=str(data.get("phone") or data.get("mobile") or "").strip(),
            refresh_token=str(
                data.get("refresh_token") or data.get("refreshToken") or ""
            ).strip(),
            distinct_id=str(
                data.get("distinct_id") or data.get("distinctId") or ""
            ).strip(),
            dev_code=str(data.get("dev_code") or data.get("devCode") or "").strip(),
        )


@dataclass
class GameRole:
    game_id: int
    game_name: str
    role_id: str
    role_name: str
    server_id: str
    server_name: str
    user_id: str


def mask_phone(phone: str | None) -> str | None:
    text = (phone or "").strip()
    if len(text) < 7:
        return text or None
    return f"{text[:3]}****{text[-4:]}"


def _ensure_device(creds: KujiequCredentials) -> KujiequCredentials:
    if not creds.distinct_id:
        creds.distinct_id = str(uuid.uuid4())
    if not creds.dev_code:
        creds.dev_code = secrets.token_hex(16).upper()
    return creds


def _headers(token: str | None = None, *, creds: KujiequCredentials | None = None) -> dict[str, str]:
    distinct = (creds.distinct_id if creds else "") or str(uuid.uuid4())
    dev = (creds.dev_code if creds else "") or secrets.token_hex(16).upper()
    headers = {
        "osVersion": "Android",
        "devCode": dev,
        "distinct_id": distinct,
        "countryCode": "CN",
        "ip": "10.0.2.233",
        "model": "2211133C",
        "source": "android",
        "lang": "zh-Hans",
        "version": APP_VERSION,
        "versionCode": APP_VERSION_CODE,
        "channelId": "2",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
        "User-Agent": "okhttp/3.11.0",
        "Host": "api.kurobbs.com",
    }
    if token:
        headers["token"] = token
        headers["Cookie"] = f"user_token={token}"
    return headers


def _post_form(
    path: str,
    form: dict[str, Any],
    *,
    token: str | None = None,
    creds: KujiequCredentials | None = None,
    timeout: int = 25,
) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    body = urllib.parse.urlencode(
        {k: "" if v is None else str(v) for k, v in form.items()}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers=_headers(token, creds=creds),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        raise KujiequApiError(f"HTTP {exc.code}: {raw[:200] or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise KujiequApiError(f"无法连接库街区: {exc}") from exc

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise KujiequApiError(f"库街区响应无效: {raw[:120]}") from exc
    if not isinstance(data, dict):
        raise KujiequApiError("库街区响应格式错误")
    return data


def _assert_ok(data: dict[str, Any], *, allow_codes: set[int] | None = None) -> dict[str, Any]:
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    if code_i == 200 or (allow_codes and code_i in allow_codes):
        return data
    msg = str(data.get("msg") or data.get("message") or "请求失败")
    if code_i in (220, 401):
        raise KujiequApiError("登录已过期，请重新绑定", code=code_i)
    raise KujiequApiError(msg, code=code_i)


@dataclass
class SmsSendResult:
    """短信发送结果。need_geetest=True 时需前端完成官方极验后再带 geeTestData 重试。"""

    ok: bool
    need_geetest: bool = False
    captcha_id: str = GEETEST_CAPTCHA_ID
    message: str = "验证码已发送"


def send_sms_captcha(phone: str, gee_test_data: str | None = None) -> SmsSendResult:
    phone = (phone or "").strip()
    if len(phone) < 6:
        raise KujiequApiError("请填写正确的手机号")
    # 传原始 JSON 字符串，由 urlencode 编码；勿预先 percent-encode，否则会双重编码
    gee = (gee_test_data or "").strip()
    data = _post_form("/user/getSmsCode", {"mobile": phone, "geeTestData": gee})
    _assert_ok(data)
    payload = data.get("data") or {}
    if isinstance(payload, dict) and payload.get("geeTest") is True:
        return SmsSendResult(
            ok=False,
            need_geetest=True,
            captcha_id=GEETEST_CAPTCHA_ID,
            message="请完成人机验证后重新发送",
        )
    return SmsSendResult(ok=True, message="验证码已发送")


def login_with_sms(phone: str, code: str) -> KujiequCredentials:
    phone = (phone or "").strip()
    code = (code or "").strip()
    if len(phone) < 6 or len(code) < 4:
        raise KujiequApiError("请填写手机号与验证码")
    creds = _ensure_device(KujiequCredentials(token=""))
    data = _post_form(
        "/user/sdkLogin",
        {
            "mobile": phone,
            "code": code,
            "devCode": creds.dev_code,
            "gameList": "",
        },
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    if not isinstance(payload, dict):
        raise KujiequApiError("登录响应无效")
    token = str(payload.get("token") or "").strip()
    if not token:
        raise KujiequApiError("登录未返回 token")
    creds.token = token
    creds.refresh_token = str(payload.get("refreshToken") or "").strip()
    creds.user_id = str(payload.get("userId") or "").strip()
    creds.user_name = str(payload.get("userName") or "").strip()
    creds.phone = phone
    return creds


def login_with_token(token: str, *, phone: str = "") -> KujiequCredentials:
    creds = _ensure_device(
        KujiequCredentials(token=(token or "").strip(), phone=(phone or "").strip())
    )
    if not creds.token:
        raise KujiequApiError("请填写 token")
    mine = fetch_mine(creds)
    creds.user_id = str(mine.get("user_id") or creds.user_id)
    creds.user_name = str(mine.get("user_name") or creds.user_name)
    return creds


def fetch_mine(creds: KujiequCredentials) -> dict[str, str]:
    creds = _ensure_device(creds)
    data = _post_form("/user/mineV2", {"type": "1"}, token=creds.token, creds=creds)
    _assert_ok(data)
    payload = data.get("data") or {}
    mine = payload.get("mine") if isinstance(payload, dict) else None
    if not isinstance(mine, dict):
        mine = payload if isinstance(payload, dict) else {}
    user_id = str(mine.get("userId") or mine.get("user_id") or "").strip()
    user_name = str(mine.get("userName") or mine.get("user_name") or "").strip()
    if not user_id and not user_name:
        # 有些版本直接在 data 根上
        user_id = str(payload.get("userId") or "").strip() if isinstance(payload, dict) else ""
        user_name = str(payload.get("userName") or "").strip() if isinstance(payload, dict) else ""
    if not user_id:
        raise KujiequApiError("无法获取库街区账号信息，请检查 token")
    return {"user_id": user_id, "user_name": user_name}


def list_roles_for_game(creds: KujiequCredentials, game_id: int) -> list[GameRole]:
    creds = _ensure_device(creds)
    data = _post_form(
        "/user/role/findRoleList",
        {"gameId": game_id},
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    rows = data.get("data") or []
    if not isinstance(rows, list):
        return []
    out: list[GameRole] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        role_id = str(row.get("roleId") or "").strip()
        server_id = str(row.get("serverId") or "").strip()
        if not role_id or not server_id:
            continue
        out.append(
            GameRole(
                game_id=int(row.get("gameId") or game_id),
                game_name=GAME_NAMES.get(game_id, f"游戏{game_id}"),
                role_id=role_id,
                role_name=str(row.get("roleName") or role_id).strip(),
                server_id=server_id,
                server_name=str(row.get("serverName") or server_id).strip(),
                user_id=str(row.get("userId") or creds.user_id or "").strip(),
            )
        )
    return out


def list_all_game_roles(creds: KujiequCredentials) -> list[GameRole]:
    roles: list[GameRole] = []
    for gid in (GAME_WW, GAME_PGR):
        try:
            roles.extend(list_roles_for_game(creds, gid))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            logger.warning("list roles gameId=%s failed: %s", gid, exc.message)
    return roles


def _format_goods_rows(rows: list[Any]) -> str | None:
    parts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("goodsName") or "").strip() or "奖励"
        num = row.get("goodsNum")
        if num is None:
            num = row.get("gainValue")
        if num is not None:
            parts.append(f"{name}×{num}" if name != "库洛币" else f"库洛币+{num}")
        else:
            parts.append(name)
    return " · ".join(parts) if parts else None


def _community_awards_from_tasks(creds: KujiequCredentials) -> str | None:
    """从每日任务进度读取「用户签到」奖励（已签后 info 接口不含奖励）。"""
    if not creds.user_id:
        return None
    try:
        data = _post_form(
            "/encourage/level/getTaskProcess",
            {"gameId": 0, "userId": creds.user_id},
            token=creds.token,
            creds=creds,
        )
        _assert_ok(data)
    except KujiequApiError as exc:
        logger.warning("kujiequ task process failed: %s", exc.message)
        return None
    payload = data.get("data") or {}
    tasks = payload.get("dailyTask") if isinstance(payload, dict) else None
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        remark = str(task.get("remark") or "")
        if "签到" not in remark:
            continue
        try:
            done = int(task.get("completeTimes") or 0)
            need = int(task.get("needActionTimes") or 1)
        except (TypeError, ValueError):
            continue
        if done < need:
            return None
        gold = task.get("gainGold")
        if gold is None:
            return None
        return f"库洛币+{gold}"
    return None


def _game_awards_from_records(creds: KujiequCredentials, role: GameRole) -> str | None:
    """从游戏签到领取记录（queryRecordV2）按北京自然日取今日奖励。"""
    try:
        data = _post_form(
            "/encourage/signIn/queryRecordV2",
            {
                "gameId": role.game_id,
                "serverId": role.server_id,
                "roleId": role.role_id,
                "userId": role.user_id or creds.user_id,
            },
            token=creds.token,
            creds=creds,
        )
        _assert_ok(data)
    except KujiequApiError as exc:
        logger.warning(
            "kujiequ queryRecord gameId=%s role=%s failed: %s",
            role.game_id,
            role.role_id,
            exc.message,
        )
        return None
    rows = data.get("data") or []
    if not isinstance(rows, list):
        return None
    day = today().isoformat()
    todays = [
        r
        for r in rows
        if isinstance(r, dict) and str(r.get("sigInDate") or "").startswith(day)
    ]
    return _format_goods_rows(todays)


def _awards_from_sign_payload(payload: dict[str, Any]) -> str | None:
    """解析签到成功响应：社区 gainVoList / 游戏 todayList。"""
    gains = payload.get("gainVoList")
    if isinstance(gains, list) and gains:
        parts: list[str] = []
        for g in gains:
            if isinstance(g, dict):
                parts.append(f"库洛币+{g.get('gainValue') or '?'}")
        if parts:
            return " · ".join(parts)
    today_list = payload.get("todayList")
    if isinstance(today_list, dict):
        today_list = [today_list]
    if isinstance(today_list, list) and today_list:
        return _format_goods_rows(today_list)
    return None


def query_community_today(creds: KujiequCredentials) -> CheckinResult:
    creds = _ensure_device(creds)
    data = _post_form(
        "/user/signIn/info",
        {"gameId": GAME_PGR},
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    has = bool(payload.get("hasSignIn")) if isinstance(payload, dict) else False
    days = payload.get("continueDays") if isinstance(payload, dict) else None
    extra = f"连签 {days} 天" if days is not None else None
    awards = _community_awards_from_tasks(creds) if has else None
    return CheckinResult(
        game_code="kujiequ",
        game_name="库街区",
        role_uid=creds.user_id or "community",
        role_name=creds.user_name or "社区账号",
        channel_name="社区签到",
        status="already" if has else "pending",
        message="今日已签到" if has else "今日未签到",
        awards_text=awards,
        extra_text=extra,
    )


def do_community_sign_in(creds: KujiequCredentials) -> CheckinResult:
    creds = _ensure_device(creds)
    data = _post_form(
        "/user/signIn",
        {"gameId": GAME_PGR},
        token=creds.token,
        creds=creds,
    )
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    msg = str(data.get("msg") or "")
    if code_i == 1511 or "重复" in msg:
        info = query_community_today(creds)
        return CheckinResult(
            game_code="kujiequ",
            game_name="库街区",
            role_uid=creds.user_id or "community",
            role_name=creds.user_name or "社区账号",
            channel_name="社区签到",
            status="already",
            message=msg or "今日已签到",
            awards_text=info.awards_text,
            extra_text=info.extra_text,
        )
    if code_i in (220, 401):
        raise KujiequApiError("登录已过期，请重新绑定", code=code_i)
    if code_i != 200 and not data.get("success"):
        raise KujiequApiError(msg or "社区签到失败", code=code_i)

    awards = None
    extra = None
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        awards = _awards_from_sign_payload(payload)
        days = payload.get("continueDays")
        if days is not None:
            extra = f"连签 {days} 天"
    if not awards:
        awards = _community_awards_from_tasks(creds)
    return CheckinResult(
        game_code="kujiequ",
        game_name="库街区",
        role_uid=creds.user_id or "community",
        role_name=creds.user_name or "社区账号",
        channel_name="社区签到",
        status="ok",
        message=msg or "签到成功",
        awards_text=awards,
        extra_text=extra,
    )


def query_game_today(creds: KujiequCredentials, role: GameRole) -> CheckinResult:
    creds = _ensure_device(creds)
    data = _post_form(
        "/encourage/signIn/initSignInV2",
        {
            "gameId": role.game_id,
            "serverId": role.server_id,
            "roleId": role.role_id,
            "userId": role.user_id or creds.user_id,
        },
        token=creds.token,
        creds=creds,
    )
    _assert_ok(data)
    payload = data.get("data") or {}
    signed = bool(payload.get("isSigIn")) if isinstance(payload, dict) else False
    days = payload.get("sigInNum") if isinstance(payload, dict) else None
    awards = _game_awards_from_records(creds, role) if signed else None
    return CheckinResult(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=role.server_name,
        status="already" if signed else "pending",
        message="今日已签到" if signed else "今日未签到",
        awards_text=awards,
        extra_text=f"本月已签 {days} 天" if days is not None else None,
    )


def do_game_sign_in(creds: KujiequCredentials, role: GameRole) -> CheckinResult:
    creds = _ensure_device(creds)
    month = f"{now_naive().month:02d}"
    data = _post_form(
        "/encourage/signIn/v2",
        {
            "gameId": role.game_id,
            "serverId": role.server_id,
            "roleId": role.role_id,
            "userId": role.user_id or creds.user_id,
            "reqMonth": month,
        },
        token=creds.token,
        creds=creds,
    )
    code = data.get("code")
    try:
        code_i = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_i = None
    msg = str(data.get("msg") or "")
    if code_i == 1511 or "重复" in msg:
        awards = _game_awards_from_records(creds, role)
        return CheckinResult(
            game_code=f"game_{role.game_id}",
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=role.server_name,
            status="already",
            message=msg or "今日已签到",
            awards_text=awards,
        )
    if code_i in (220, 401):
        raise KujiequApiError("登录已过期，请重新绑定", code=code_i)
    if code_i != 200 and not data.get("success"):
        return CheckinResult(
            game_code=f"game_{role.game_id}",
            game_name=role.game_name,
            role_uid=role.role_id,
            role_name=role.role_name,
            channel_name=role.server_name,
            status="error",
            message=msg or "游戏签到失败",
        )
    awards = None
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        awards = _awards_from_sign_payload(payload)
    if not awards:
        awards = _game_awards_from_records(creds, role)
    return CheckinResult(
        game_code=f"game_{role.game_id}",
        game_name=role.game_name,
        role_uid=role.role_id,
        role_name=role.role_name,
        channel_name=role.server_name,
        status="ok",
        message=msg or "签到成功",
        awards_text=awards,
    )


def query_today_all(creds: KujiequCredentials) -> tuple[KujiequCredentials, list[CheckinResult]]:
    creds = _ensure_device(creds)
    if not creds.user_id:
        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name

    results: list[CheckinResult] = [query_community_today(creds)]
    for role in list_all_game_roles(creds):
        try:
            results.append(query_game_today(creds, role))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            results.append(
                CheckinResult(
                    game_code=f"game_{role.game_id}",
                    game_name=role.game_name,
                    role_uid=role.role_id,
                    role_name=role.role_name,
                    channel_name=role.server_name,
                    status="error",
                    message=exc.message,
                )
            )
    return creds, results


def run_all_checkins(creds: KujiequCredentials) -> tuple[KujiequCredentials, list[CheckinResult]]:
    creds = _ensure_device(creds)
    if not creds.user_id:
        mine = fetch_mine(creds)
        creds.user_id = mine["user_id"]
        creds.user_name = mine["user_name"] or creds.user_name

    results: list[CheckinResult] = []
    try:
        results.append(do_community_sign_in(creds))
    except KujiequApiError as exc:
        if exc.code in (220, 401):
            raise
        results.append(
            CheckinResult(
                game_code="kujiequ",
                game_name="库街区",
                role_uid=creds.user_id or "community",
                role_name=creds.user_name or "社区账号",
                channel_name="社区签到",
                status="error",
                message=exc.message,
            )
        )

    for role in list_all_game_roles(creds):
        try:
            results.append(do_game_sign_in(creds, role))
        except KujiequApiError as exc:
            if exc.code in (220, 401):
                raise
            results.append(
                CheckinResult(
                    game_code=f"game_{role.game_id}",
                    game_name=role.game_name,
                    role_uid=role.role_id,
                    role_name=role.role_name,
                    channel_name=role.server_name,
                    status="error",
                    message=exc.message,
                )
            )
    return creds, results


def friendly_error_message(message: str) -> str:
    text = (message or "").strip() or "库街区请求失败"
    if "过期" in text or "失效" in text:
        return "凭证可能已失效，请重新绑定库街区"
    return text
