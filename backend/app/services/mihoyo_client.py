"""米游社（MiHoYo BBS）HTTP 客户端。"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import string
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import unquote

import httpx

logger = logging.getLogger(__name__)

BBS_API = "https://bbs-api.miyoushe.com"
TAKUMI_API = "https://api-takumi.mihoyo.com"
TAKUMI_MIYOUSHE = "https://api-takumi.miyoushe.com"
MALL_API = "https://api-takumi.miyoushe.com"

# 与 MihoyoBBSTools 2.109.0 对齐（salt 与 version 必须配套）
SALT_APP = "47f15f1b66bee46b816115d8e8e6ebb6"
SALT_WEB = "d9200c846b10886e8c874fc33c8f308b"
SALT_X4 = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"
SALT_X6 = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"
MYS_VERSION = "2.109.0"
MYS_CLIENT_TYPE = "2"
MYS_CLIENT_TYPE_WEB = "5"

REQUEST_TIMEOUT = 25

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36 "
    f"miHoYoBBS/{MYS_VERSION}"
)

BBS_FORUMS: list[dict[str, str]] = [
    {"gid": "1", "forum_id": "1", "name": "崩坏3"},
    {"gid": "2", "forum_id": "26", "name": "原神"},
    {"gid": "3", "forum_id": "30", "name": "崩坏2"},
    {"gid": "4", "forum_id": "37", "name": "未定事件簿"},
    {"gid": "5", "forum_id": "34", "name": "大别野"},
    {"gid": "6", "forum_id": "52", "name": "星穹铁道"},
    {"gid": "8", "forum_id": "57", "name": "绝区零"},
]

GAME_BIZ_META: dict[str, dict[str, str]] = {
    "hk4e_cn": {
        "game_code": "genshin",
        "game_name": "原神",
        "act_id": "e202009291139501",
        "sign_kind": "bbs_sign",
    },
    "bh3_cn": {
        "game_code": "bh3",
        "game_name": "崩坏3",
        "act_id": "e202207181446311",
        "sign_kind": "luna",
    },
    "bh2_cn": {
        "game_code": "bh2",
        "game_name": "崩坏2",
        "act_id": "e202203291431091",
        "sign_kind": "luna",
    },
    "hkrpg_cn": {
        "game_code": "starrail",
        "game_name": "崩坏：星穹铁道",
        "act_id": "e20230424103532",
        "sign_kind": "luna",
    },
    "nap_cn": {
        "game_code": "zzz",
        "game_name": "绝区零",
        "act_id": "e20240603125433",
        "sign_kind": "luna",
    },
}

REGION_LABELS: dict[str, str] = {
    "cn_gf01": "官服",
    "cn_qd01": "B服",
    "os_usa": "美服",
    "os_euro": "欧服",
    "os_asia": "亚服",
    "os_cht": "港澳台",
}


class MihoyoApiError(Exception):
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


@dataclass
class MihoyoCredentials:
    cookie: str
    ltuid: str = ""
    account_id: str = ""
    login_ticket: str = ""
    stoken: str = ""
    stuid: str = ""
    mid: str = ""
    nickname: str = ""
    device_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: str(v or "") for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MihoyoCredentials:
        cookie = str(data.get("cookie") or "").strip()
        if not cookie:
            raise MihoyoApiError("缺少 Cookie，请重新绑定")
        creds = cls(
            cookie=cookie,
            ltuid=str(data.get("ltuid") or "").strip(),
            account_id=str(data.get("account_id") or data.get("account_id_v2") or "").strip(),
            login_ticket=str(data.get("login_ticket") or "").strip(),
            stoken=str(data.get("stoken") or "").strip(),
            stuid=str(data.get("stuid") or "").strip(),
            mid=str(data.get("mid") or "").strip(),
            nickname=str(data.get("nickname") or "").strip(),
            device_id=str(data.get("device_id") or "").strip(),
        )
        return _normalize_creds(creds)


@dataclass
class GameRole:
    game_biz: str
    game_code: str
    game_name: str
    role_uid: str
    role_name: str
    region: str
    channel_name: str


@dataclass
class ExchangeItem:
    goods_id: str
    goods_name: str
    goods_num: int = 1
    goods_img: str = ""
    price: int = 0
    exchange_limit: int = 0
    exchanged_count: int = 0
    next_exchange_time: str | None = None
    game_biz: str = ""
    game_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goods_id": self.goods_id,
            "goods_name": self.goods_name,
            "goods_num": self.goods_num,
            "goods_img": self.goods_img,
            "price": self.price,
            "exchange_limit": self.exchange_limit,
            "exchanged_count": self.exchanged_count,
            "next_exchange_time": self.next_exchange_time,
            "game_biz": self.game_biz,
            "game_name": self.game_name,
        }


def mask_account(account: str | None) -> str | None:
    text = (account or "").strip()
    if not text:
        return None
    if len(text) >= 7 and text.isdigit():
        return f"{text[:3]}****{text[-4:]}"
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}***{text[-2:]}"


def friendly_error_message(message: str | None) -> str:
    text = (message or "").strip() or "米游社请求失败"
    mapping = {
        "登录失效": "登录已失效，请重新绑定",
        "Cookie": "Cookie 无效，请重新绑定",
        "stoken": "Stoken 无效，请重新绑定",
        "invalid request": "上游请求参数无效，请重新扫码绑定后再试",
        "验证码": "需要人机验证，请稍后重试",
        "米游币": "米游币不足",
        "库存": "商品库存不足",
        "上限": "已达兑换上限",
    }
    for key, tip in mapping.items():
        if key.lower() in text.lower():
            return tip
    return text


def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _random_str(n: int = 6) -> str:
    return "".join(random.sample(string.digits + string.ascii_letters, n)).lower()


def generate_ds_sign() -> str:
    """App 端简单 DS（salt_app）。"""
    ts = str(int(time.time()))
    rnd = _random_str(6)
    chk = _md5_hex(f"salt={SALT_APP}&t={ts}&r={rnd}")
    return f"{ts},{rnd},{chk}"


def generate_ds_web() -> str:
    ts = str(int(time.time()))
    rnd = _random_str(6)
    chk = _md5_hex(f"salt={SALT_WEB}&t={ts}&r={rnd}")
    return f"{ts},{rnd},{chk}"


def generate_ds_x6(*, query: str = "", body: str = "") -> str:
    """带 query/body 的 DS（讨论区签到 / 任务等）。"""
    ts = str(int(time.time()))
    rnd = str(random.randint(100001, 200000))
    chk = _md5_hex(f"salt={SALT_X6}&t={ts}&r={rnd}&b={body}&q={query}")
    return f"{ts},{rnd},{chk}"


def generate_ds_x4(*, query: str = "", body: str = "") -> str:
    """Web DS2（4X salt）：client_type=5 的部分接口。"""
    ts = str(int(time.time()))
    rnd = _random_str(6)
    chk = _md5_hex(f"salt={SALT_X4}&t={ts}&r={rnd}&b={body}&q={query}")
    return f"{ts},{rnd},{chk}"


def generate_ds_discuss(gid: str) -> str:
    """兼容旧调用：POST 讨论区签到 body。"""
    body = json.dumps({"gids": gid}, separators=(",", ":"), ensure_ascii=False)
    return generate_ds_x6(body=body)


def parse_cookie_string(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    if not text:
        raise MihoyoApiError("Cookie 不能为空")
    if text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1].strip()
    out: dict[str, str] = {}
    for part in text.split(";"):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        key, val = piece.split("=", 1)
        out[key.strip()] = unquote(val.strip())
    if not out:
        raise MihoyoApiError("Cookie 格式无效")
    return out


def _cookie_kv(creds: MihoyoCredentials) -> dict[str, str]:
    base = parse_cookie_string(creds.cookie)
    if creds.login_ticket:
        base["login_ticket"] = creds.login_ticket
    if creds.stuid:
        base["stuid"] = creds.stuid
    if creds.stoken:
        base["stoken"] = creds.stoken
    if creds.mid:
        # v2 stoken 必须带 mid，否则米游社接口会拒
        base["mid"] = creds.mid
        base.setdefault("account_mid_v2", creds.mid)
        base.setdefault("ltmid_v2", creds.mid)
    if creds.ltuid:
        base["ltuid"] = creds.ltuid
        base["ltuid_v2"] = creds.ltuid
    if creds.account_id:
        base["account_id"] = creds.account_id
        base["account_id_v2"] = creds.account_id
    return base


def cookie_header(creds: MihoyoCredentials) -> str:
    return "; ".join(f"{k}={v}" for k, v in _cookie_kv(creds).items())


def _ensure_device_id(creds: MihoyoCredentials) -> MihoyoCredentials:
    if not creds.device_id:
        creds.device_id = str(uuid.uuid3(uuid.NAMESPACE_URL, creds.cookie))
    return creds


def _normalize_creds(creds: MihoyoCredentials) -> MihoyoCredentials:
    kv = parse_cookie_string(creds.cookie)
    if not creds.ltuid:
        creds.ltuid = kv.get("ltuid_v2") or kv.get("ltuid") or ""
    if not creds.account_id:
        creds.account_id = kv.get("account_id_v2") or kv.get("account_id") or ""
    if not creds.login_ticket:
        creds.login_ticket = kv.get("login_ticket") or ""
    if not creds.stoken:
        creds.stoken = kv.get("stoken") or ""
    if not creds.stuid:
        creds.stuid = kv.get("stuid") or creds.ltuid or creds.account_id
    if not creds.mid:
        creds.mid = (
            kv.get("mid") or kv.get("account_mid_v2") or kv.get("ltmid_v2") or ""
        )
    return _ensure_device_id(creds)


def _bbs_headers(creds: MihoyoCredentials, *, ds: str | None = None) -> dict[str, str]:
    creds = _ensure_device_id(_normalize_creds(creds))
    cookie = cookie_header(creds)
    if creds.stoken:
        try:
            cookie = stoken_cookie_header(creds)
        except MihoyoApiError:
            pass
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Cookie": cookie,
        "User-Agent": USER_AGENT,
        "Referer": "https://app.mihoyo.com",
        "Origin": "https://app.mihoyo.com",
        "DS": ds or generate_ds_sign(),
        "x-rpc-client_type": MYS_CLIENT_TYPE,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-device_id": creds.device_id,
        "x-rpc-device_name": "vivo s7",
        "x-rpc-device_model": "vivo-s7",
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "miyousheluodi",
    }


def _game_headers(
    creds: MihoyoCredentials,
    *,
    referer: str = "https://webstatic.mihoyo.com/",
    ds: str | None = None,
) -> dict[str, str]:
    """对齐 MihoyoBBSTools 游戏签到头：client_type=5 + web salt DS1。"""
    creds = _ensure_device_id(creds)
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Cookie": cookie_header(creds),
        "User-Agent": USER_AGENT,
        "Referer": referer,
        "Origin": "https://webstatic.mihoyo.com",
        "DS": ds or generate_ds_web(),
        "x-rpc-client_type": MYS_CLIENT_TYPE_WEB,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-device_id": creds.device_id,
        "x-rpc-device_name": "vivo s7",
        "x-rpc-device_model": "vivo-s7",
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "miyousheluodi",
        "X-Requested-With": "com.mihoyo.hyperion",
    }


def _assert_ok(payload: dict[str, Any]) -> dict[str, Any]:
    retcode = payload.get("retcode")
    if retcode is None:
        retcode = payload.get("code")
    message = str(payload.get("message") or payload.get("msg") or "")
    if retcode not in (0, "0", None):
        raise MihoyoApiError(
            friendly_error_message(message or "米游社请求失败"),
            code=retcode,
            data=payload,
        )
    data = payload.get("data")
    return data if isinstance(data, dict) else {"raw": data}


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        resp = client.request(method.upper(), url, headers=headers, params=params, json=json_body)
        try:
            payload = resp.json()
        except json.JSONDecodeError as exc:
            raise MihoyoApiError(
                f"上游返回非 JSON（HTTP {resp.status_code}）"
            ) from exc
    if not isinstance(payload, dict):
        raise MihoyoApiError("上游返回格式异常")
    return payload


def resolve_stoken(creds: MihoyoCredentials) -> MihoyoCredentials:
    creds = _normalize_creds(creds)
    if creds.stoken and creds.stuid:
        return creds
    ticket = creds.login_ticket
    if not ticket:
        raise MihoyoApiError("Cookie 缺少 login_ticket / stoken，请重新扫码或登录绑定")
    acc_url = (
        "https://webapi.account.mihoyo.com/Api/cookie_accountinfo_by_loginticket"
        f"?login_ticket={ticket}"
    )
    acc_payload = _http_json("GET", acc_url, headers={"User-Agent": USER_AGENT})
    acc_data = acc_payload.get("data") if isinstance(acc_payload.get("data"), dict) else {}
    cookie_info = acc_data.get("cookie_info") if isinstance(acc_data.get("cookie_info"), dict) else {}
    stuid = str(cookie_info.get("account_id") or creds.stuid or creds.account_id or "").strip()
    if not stuid:
        raise MihoyoApiError("无法从 Cookie 解析账号 ID，请重新绑定")
    token_url = (
        "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket"
        f"?login_ticket={ticket}&token_types=3&uid={stuid}"
    )
    token_payload = _http_json("GET", token_url, headers={"User-Agent": USER_AGENT})
    token_data = _assert_ok(token_payload)
    token_list = token_data.get("list") if isinstance(token_data.get("list"), list) else []
    stoken = ""
    for row in token_list:
        if isinstance(row, dict) and str(row.get("token_type")) == "3":
            stoken = str(row.get("token") or "").strip()
            break
    if not stoken and token_list and isinstance(token_list[0], dict):
        stoken = str(token_list[0].get("token") or "").strip()
    if not stoken:
        raise MihoyoApiError("无法获取 Stoken，请重新绑定")
    creds.stuid = stuid
    creds.stoken = stoken
    creds.account_id = creds.account_id or stuid
    creds.ltuid = creds.ltuid or stuid
    return creds


def stoken_cookie_header(creds: MihoyoCredentials) -> str:
    """MihoyoBBSTools get_stoken_cookie：v2 必须带 mid。"""
    creds = _normalize_creds(creds)
    stuid = creds.stuid or creds.account_id or creds.ltuid
    if not creds.stoken or not stuid:
        raise MihoyoApiError("缺少 stoken / uid")
    parts = [f"stuid={stuid}", f"stoken={creds.stoken}"]
    if creds.stoken.startswith("v2_"):
        if not creds.mid:
            raise MihoyoApiError("v2 stoken 缺少 mid，请重新扫码绑定")
        parts.append(f"mid={creds.mid}")
    return ";".join(parts)


def refresh_cookie_token(creds: MihoyoCredentials) -> MihoyoCredentials:
    """stoken(+mid) → cookie_token，供游戏角色 / 福利签到使用。"""
    creds = _normalize_creds(creds)
    parts = parse_cookie_string(creds.cookie)
    if parts.get("cookie_token") or parts.get("cookie_token_v2"):
        return creds
    # 对齐 MihoyoBBSTools：仅 Cookie 带 stoken(+mid)，不传 query / DS
    cookie = stoken_cookie_header(creds)
    url = f"{TAKUMI_API}/auth/api/getCookieAccountInfoBySToken"
    headers = {
        "User-Agent": USER_AGENT,
        "Cookie": cookie,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-client_type": MYS_CLIENT_TYPE_WEB,
        "x-rpc-device_id": creds.device_id or uuid.uuid4().hex,
    }
    payload = _http_json("GET", url, headers=headers)
    data = _assert_ok(payload)
    token = str(data.get("cookie_token") or "").strip()
    if not token:
        raise MihoyoApiError("无法用 stoken 换取 cookie_token，请重新绑定")
    parts["cookie_token"] = token
    parts["cookie_token_v2"] = token
    aid = creds.stuid or creds.account_id
    if aid:
        parts.setdefault("account_id", aid)
        parts.setdefault("account_id_v2", aid)
        parts.setdefault("ltuid", aid)
        parts.setdefault("ltuid_v2", aid)
    if creds.mid:
        parts.setdefault("mid", creds.mid)
        parts.setdefault("account_mid_v2", creds.mid)
        parts.setdefault("ltmid_v2", creds.mid)
    if creds.stoken:
        parts["stoken"] = creds.stoken
        parts["stuid"] = aid or parts.get("stuid", "")
    creds.cookie = "; ".join(f"{k}={v}" for k, v in parts.items() if v)
    return creds


def ensure_session(creds: MihoyoCredentials) -> MihoyoCredentials:
    working = _normalize_creds(creds)
    working = resolve_stoken(working)
    if working.stoken.startswith("v2_") and not working.mid:
        raise MihoyoApiError("v2 stoken 缺少 mid，请重新扫码绑定")
    try:
        working = refresh_cookie_token(working)
    except MihoyoApiError as exc:
        # cookie_token 失败时仍可先走 stoken 接口；记录警告
        logger.warning("mihoyo refresh_cookie_token skipped: %s", exc.message)
    try:
        enrich_user_info(working)
    except MihoyoApiError as exc:
        logger.warning("mihoyo enrich_user_info skipped: %s", exc.message)
    return working


def enrich_user_info(creds: MihoyoCredentials) -> MihoyoCredentials:
    creds = _normalize_creds(creds)
    uid = creds.stuid or creds.ltuid or creds.account_id
    if not uid:
        raise MihoyoApiError("缺少账号 UID")
    url = f"{BBS_API}/user/api/getUserFullInfo"
    payload = _http_json("GET", url, headers=_bbs_headers(creds), params={"uid": uid})
    data = _assert_ok(payload)
    user = data.get("user_info") if isinstance(data.get("user_info"), dict) else data
    nickname = str(user.get("nickname") or user.get("nick_name") or "").strip()
    if nickname:
        creds.nickname = nickname
    return creds


def list_bbs_business_ids(creds: MihoyoCredentials) -> list[str]:
    creds = _normalize_creds(creds)
    uid = creds.stuid or creds.ltuid
    url = f"{BBS_API}/user/api/getUserBusinesses"
    payload = _http_json("GET", url, headers=_bbs_headers(creds), params={"uid": uid})
    data = _assert_ok(payload)
    rows = data.get("businesses") if isinstance(data.get("businesses"), list) else []
    out: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            gid = str(row.get("id") or row.get("gid") or "").strip()
            if gid:
                out.append(gid)
    return out


def list_game_roles(creds: MihoyoCredentials) -> list[GameRole]:
    """优先 stoken+DS1；失败再回退 cookie_token。"""
    creds = _normalize_creds(creds)
    rows: list[Any] = []
    last_err: MihoyoApiError | None = None

    if creds.stoken:
        try:
            # UIGF: client_type=2 + K2 salt + DS1 + SToken Cookie
            url = f"{TAKUMI_MIYOUSHE}/binding/api/getUserGameRolesByStoken"
            headers = {
                **_bbs_headers(creds, ds=generate_ds_sign()),
                "Cookie": stoken_cookie_header(creds),
            }
            payload = _http_json("GET", url, headers=headers)
            data = _assert_ok(payload)
            rows = data.get("list") if isinstance(data.get("list"), list) else []
        except MihoyoApiError as exc:
            last_err = exc
            logger.warning(
                "mihoyo getUserGameRolesByStoken failed: %s", exc.message
            )

    if not rows:
        try:
            creds = refresh_cookie_token(creds)
        except MihoyoApiError as exc:
            last_err = last_err or exc
            logger.warning("mihoyo refresh_cookie_token for roles failed: %s", exc.message)
        try:
            url = f"{TAKUMI_API}/binding/api/getUserGameRolesByCookie"
            payload = _http_json("GET", url, headers=_game_headers(creds))
            data = _assert_ok(payload)
            rows = data.get("list") if isinstance(data.get("list"), list) else []
        except MihoyoApiError as exc:
            last_err = exc
            logger.warning(
                "mihoyo getUserGameRolesByCookie failed: %s", exc.message
            )

    if not rows and last_err is not None:
        # 社区账号仍可加入；游戏角色拉取失败时向上抛出会阻断角色树
        # 改为返回空列表，由 preview_roles 至少带上社区节点
        logger.warning(
            "mihoyo list_game_roles empty after fallbacks: %s", last_err.message
        )

    out: list[GameRole] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        biz = str(row.get("game_biz") or "").strip()
        meta = GAME_BIZ_META.get(biz)
        if meta is None:
            continue
        uid = str(row.get("game_uid") or row.get("uid") or "").strip()
        if not uid:
            continue
        region = str(row.get("region") or "").strip()
        nickname = str(row.get("nickname") or row.get("nick_name") or uid).strip()
        out.append(
            GameRole(
                game_biz=biz,
                game_code=meta["game_code"],
                game_name=meta["game_name"],
                role_uid=uid,
                role_name=nickname,
                region=region,
                channel_name=REGION_LABELS.get(region, region or "未知"),
            )
        )
    return out


def bind_with_cookie(raw_cookie: str) -> MihoyoCredentials:
    kv = parse_cookie_string(raw_cookie)
    cookie = "; ".join(f"{k}={v}" for k, v in kv.items())
    creds = MihoyoCredentials(cookie=cookie)
    creds = _normalize_creds(creds)
    working = ensure_session(creds)
    list_game_roles(working)
    return working


def get_points_balance(creds: MihoyoCredentials) -> int:
    creds = _normalize_creds(creds)
    url = f"{BBS_API}/user/wapi/getUserMcoinBalance"
    payload = _http_json("GET", url, headers=_bbs_headers(creds))
    data = _assert_ok(payload)
    try:
        return int(data.get("mcoin_balance") or data.get("points") or 0)
    except (TypeError, ValueError):
        return 0


def list_exchange_goods(creds: MihoyoCredentials, *, app_id: int = 1) -> list[ExchangeItem]:
    creds = _normalize_creds(creds)
    url = f"{MALL_API}/mall/v1/web/goods/list"
    payload = _http_json(
        "GET",
        url,
        headers=_game_headers(creds, referer="https://www.miyoushe.com/"),
        params={"app_id": app_id, "page_size": 50, "page": 1},
    )
    data = _assert_ok(payload)
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    out: list[ExchangeItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        gid = str(row.get("goods_id") or row.get("id") or "").strip()
        if not gid:
            continue
        name = str(row.get("goods_name") or row.get("name") or "商品").strip()
        try:
            price = int(row.get("price") or row.get("goods_price") or 0)
        except (TypeError, ValueError):
            price = 0
        try:
            limit = int(row.get("exchange_limit") or row.get("buy_limit") or 0)
        except (TypeError, ValueError):
            limit = 0
        try:
            exchanged = int(row.get("exchanged_count") or row.get("buy_num") or 0)
        except (TypeError, ValueError):
            exchanged = 0
        try:
            num = int(row.get("goods_num") or row.get("num") or 1)
        except (TypeError, ValueError):
            num = 1
        biz = str(row.get("game_biz") or "").strip()
        meta = GAME_BIZ_META.get(biz, {})
        out.append(
            ExchangeItem(
                goods_id=gid,
                goods_name=name,
                goods_num=num,
                goods_img=str(row.get("goods_img") or row.get("icon") or "").strip(),
                price=price,
                exchange_limit=limit,
                exchanged_count=exchanged,
                next_exchange_time=str(row.get("next_exchange_time") or "") or None,
                game_biz=biz,
                game_name=str(meta.get("game_name") or biz),
            )
        )
    return out


def exchange_goods(
    creds: MihoyoCredentials,
    *,
    goods_id: str,
    game_biz: str = "",
    region: str = "",
    role_uid: str = "",
    exchange_num: int = 1,
) -> dict[str, Any]:
    creds = _normalize_creds(creds)
    uid = creds.stuid or creds.ltuid or creds.account_id
    body = {
        "app_id": 1,
        "point_sn": "myb",
        "goods_id": str(goods_id),
        "exchange_num": int(exchange_num),
        "uid": uid,
        "region": region or "",
        "game_biz": game_biz or "",
    }
    if role_uid:
        body["game_uid"] = role_uid
    url = f"{MALL_API}/mall/v1/web/goods/exchange"
    payload = _http_json(
        "POST",
        url,
        headers=_game_headers(creds, referer="https://www.miyoushe.com/"),
        json_body=body,
    )
    _assert_ok(payload)
    return payload


def list_points_logs(
    creds: MihoyoCredentials,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    creds = _normalize_creds(creds)
    url = f"{BBS_API}/user/wapi/getCoinLog"
    payload = _http_json(
        "GET",
        url,
        headers=_bbs_headers(creds),
        params={"page": page, "page_size": page_size},
    )
    data = _assert_ok(payload)
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    total = data.get("total")
    try:
        total_i = int(total) if total is not None else len(rows)
    except (TypeError, ValueError):
        total_i = len(rows)
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out_rows.append(
            {
                "points": int(row.get("coin_num") or row.get("points") or 0),
                "reason": str(row.get("reason") or row.get("title") or ""),
                "log_time": str(row.get("log_time") or row.get("created_at") or ""),
            }
        )
    return {"list": out_rows, "total": total_i, "page": page, "page_size": page_size}
