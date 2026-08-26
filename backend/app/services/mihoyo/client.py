"""米游社（MiHoYo BBS）HTTP 客户端。

上游 salt / 活动 ID / 签到请求头对齐 Womsxd/MihoyoBBSTools。
米游币商城对齐 Ljzd-PRO/nonebot-plugin-mystool（列表/余额走 api-takumi.mihoyo.com）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import string
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, TypeVar
from urllib.parse import unquote

from app.core.http_client import HttpRequestError, http_request
from app.core.timeutil import BEIJING
from app.services.mihoyo_bbs import setting as bbs_setting

logger = logging.getLogger(__name__)

BBS_API = bbs_setting.bbs_api
TAKUMI_API = bbs_setting.web_api
TAKUMI_MIYOUSHE = "https://api-takumi.miyoushe.com"

SALT_APP = bbs_setting.mihoyobbs_salt
SALT_WEB = bbs_setting.mihoyobbs_salt_web
SALT_X4 = bbs_setting.mihoyobbs_salt_x4
SALT_X6 = bbs_setting.mihoyobbs_salt_x6
MYS_VERSION = bbs_setting.mihoyobbs_version
MYS_CLIENT_TYPE = bbs_setting.mihoyobbs_Client_type
MYS_CLIENT_TYPE_WEB = bbs_setting.mihoyobbs_Client_type_web
BBS_VERIFY_KEY = bbs_setting.mihoyobbs_verify_key
BBS_OKHTTP_UA = bbs_setting.BBS_OKHTTP_UA

REQUEST_TIMEOUT = 25

USER_AGENT = str(bbs_setting.headers["User-Agent"])

BBS_FORUMS: list[dict[str, str]] = [
    {"gid": row["id"], "forum_id": row["forumId"], "name": row["name"]}
    for _, row in sorted(bbs_setting.mihoyobbs_List.items())
]


def _bh_referer(act_id: str, path: str) -> str:
    return (
        f"https://webstatic.mihoyo.com/bbs/event/signin/{path}/index.html"
        f"?bbs_auth_required=true&act_id={act_id}&bbs_presentation_style=fullscreen"
        "&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
    )


# 活动 ID / luna URL / signgame 头：对齐 MihoyoBBSTools gamecheckin.py
GAME_BIZ_META: dict[str, dict[str, str]] = {
    "hk4e_cn": {
        "game_code": "genshin",
        "game_name": "原神",
        "act_id": bbs_setting.genshin_act_id,
        "sign_kind": "luna",
        "signgame": "hk4e",
        "origin": "https://act.mihoyo.com",
        "referer": "https://act.mihoyo.com/",
    },
    "bh3_cn": {
        "game_code": "bh3",
        "game_name": "崩坏3",
        "act_id": bbs_setting.honkai3rd_act_id,
        "sign_kind": "luna",
        "referer": _bh_referer(bbs_setting.honkai3rd_act_id, "bh3"),
    },
    "bh2_cn": {
        "game_code": "bh2",
        "game_name": "崩坏2",
        "act_id": bbs_setting.honkai2_act_id,
        "sign_kind": "luna",
        "referer": _bh_referer(bbs_setting.honkai2_act_id, "bh2"),
    },
    "hkrpg_cn": {
        "game_code": "starrail",
        "game_name": "崩坏：星穹铁道",
        "act_id": bbs_setting.honkai_sr_act_id,
        "sign_kind": "luna",
        "origin": "https://act.mihoyo.com",
        "referer": "https://act.mihoyo.com/",
    },
    "nap_cn": {
        "game_code": "zzz",
        "game_name": "绝区零",
        "act_id": bbs_setting.zzz_act_id,
        "sign_kind": "luna_zzz",
        "signgame": "zzz",
        "origin": "https://act.mihoyo.com",
        "referer": "https://act.mihoyo.com/",
    },
}

REGION_LABELS: dict[str, str] = {
    # 原神
    "cn_gf01": "官服",
    "cn_qd01": "B服",
    "os_usa": "美服",
    "os_euro": "欧服",
    "os_asia": "亚服",
    "os_cht": "港澳台",
    # 星铁 / 绝区零
    "prod_gf_cn": "官服",
    "prod_qd_cn": "B服",
    "prod_official_usa": "美服",
    "prod_official_euro": "欧服",
    "prod_official_asia": "亚服",
    "prod_official_cht": "港澳台",
    "prod_gf_us": "美服",
    "prod_gf_jp": "日服",
    "prod_gf_sg": "亚服",
    # 崩坏3 / 崩坏2
    "android01": "官服",
    "ios01": "官服",
    "pc01": "官服",
    "bb01": "B服",
}


def region_label(region: str | None, region_name: str | None = None) -> str:
    """区服内部 ID → 渠道展示名（官服 / B服 / …）。

    上游 `region` 是技术代码（原神 cn_gf01、星铁/绝区零 prod_gf_cn）。
    未收录时按命名启发式；仍无法识别则用中文 region_name，避免把代码直接展示。
    """
    key = (region or "").strip()
    if key in REGION_LABELS:
        return REGION_LABELS[key]
    low = key.lower()
    if low:
        if "qd" in low or low.startswith("bb") or "bilibili" in low:
            return "B服"
        if "cht" in low or "tw" in low or "hk" in low:
            return "港澳台"
        if "usa" in low or low.endswith("_us") or "america" in low:
            return "美服"
        if "euro" in low or "europe" in low:
            return "欧服"
        if "jp" in low or "japan" in low:
            return "日服"
        if "asia" in low or low.endswith("_sg"):
            return "亚服"
        if "gf" in low or "official" in low:
            return "官服"
    name = (region_name or "").strip()
    if name and name != key and any("\u4e00" <= ch <= "\u9fff" for ch in name):
        return name
    return "未知"


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


# 米游币商城分区 game= → (game_code, 展示名)；对齐 mystool Good.game
MALL_GAME_META: dict[str, tuple[str, str]] = {
    "hk4e": ("genshin", "原神"),
    "hkrpg": ("starrail", "崩坏：星穹铁道"),
    "nap": ("zzz", "绝区零"),
    "bh3": ("bh3", "崩坏3"),
    "bh2": ("bh2", "崩坏2"),
    "nxx": ("nxx", "未定事件簿"),
    "bbs": ("", "米游社"),
}


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
    game_code: str = ""
    game_name: str = ""
    goods_type: int = 0

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
            "game_code": self.game_code,
            "game_name": self.game_name,
            "goods_type": self.goods_type,
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


_AUTH_RETCODES = {-100, -101, -10001, 10001}
_AUTH_HINTS = (
    "登录失效",
    "登录已失效",
    "登陆失效",
    "未登录",
    "尚未登录",
    "cookie 无效",
    "stoken 无效",
    "凭证已损坏",
    "凭证格式无效",
    "请重新绑定",
    "unauthorized",
    "login expired",
    "not login",
)


def is_auth_failure(*, code: Any = None, message: str | None = None) -> bool:
    """登录态 / Cookie / Stoken 失效：应上注为 token_ok=false，不能当成未签。"""
    try:
        if code is not None and str(code).strip() != "":
            if int(code) in _AUTH_RETCODES:
                return True
    except (TypeError, ValueError):
        pass
    text = (message or "").strip()
    if not text:
        return False
    low = text.lower()
    return any(hint.lower() in low for hint in _AUTH_HINTS)


T = TypeVar("T")


def call_with_cookie_refresh(
    creds: MihoyoCredentials, fn: Callable[[MihoyoCredentials], T]
) -> T:
    """对齐 MihoyoBBSTools login.update_cookie_token：-100 时用 stoken 刷新 cookie_token 再试一次。"""
    try:
        return fn(creds)
    except MihoyoApiError as exc:
        if not is_auth_failure(code=exc.code, message=exc.message) or not creds.stoken:
            raise
        logger.info("mihoyo cookie_token refresh after auth failure: %s", exc.message)
        refresh_cookie_token(creds, force=True)
        return fn(creds)


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


def compact_json_body(body: dict[str, Any]) -> str:
    """DS2 必须与 POST body 字节完全一致；httpx json= 会带空格导致验签失败。"""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def _bbs_headers(creds: MihoyoCredentials, *, ds: str | None = None) -> dict[str, str]:
    """对齐 MihoyoBBSTools mihoyobbs.py：stoken Cookie + okhttp。"""
    creds = _ensure_device_id(_normalize_creds(creds))
    cookie = cookie_header(creds)
    if creds.stoken:
        try:
            cookie = stoken_cookie_header(creds)
        except MihoyoApiError:
            pass
    return {
        "DS": ds or generate_ds_sign(),
        "Cookie": cookie,
        "x-rpc-client_type": MYS_CLIENT_TYPE,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-sys_version": "12",
        "x-rpc-channel": "miyousheluodi",
        "x-rpc-device_id": creds.device_id,
        "x-rpc-device_name": "vivo s7",
        "x-rpc-device_model": "vivo-s7",
        "x-rpc-h265_supported": "1",
        "Referer": "https://app.mihoyo.com",
        "x-rpc-verify_key": BBS_VERIFY_KEY,
        "x-rpc-csm_source": "discussion",
        "Content-Type": "application/json; charset=UTF-8",
        "Accept-Encoding": "gzip",
        "User-Agent": BBS_OKHTTP_UA,
    }


def _mission_headers(creds: MihoyoCredentials) -> dict[str, str]:
    """米游币任务列表：web Cookie（MihoyoBBSTools task_header）。"""
    creds = _ensure_device_id(_normalize_creds(creds))
    return {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://webstatic.mihoyo.com",
        "User-Agent": USER_AGENT,
        "Referer": "https://webstatic.mihoyo.com",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,en-US;q=0.8",
        "X-Requested-With": "com.mihoyo.hyperion",
        "Cookie": cookie_header(creds),
    }


def _game_headers(
    creds: MihoyoCredentials,
    *,
    referer: str = "https://act.mihoyo.com/",
    origin: str | None = None,
    signgame: str | None = None,
    ds: str | None = None,
) -> dict[str, str]:
    """对齐 MihoyoBBSTools gamecheckin.set_headers：client_type=5 + web salt DS1。"""
    creds = _ensure_device_id(creds)
    headers = dict(bbs_setting.headers)
    headers["DS"] = ds or generate_ds_web()
    headers["Referer"] = referer
    headers["Origin"] = origin or str(headers.get("Origin") or "https://webstatic.mihoyo.com")
    headers["Cookie"] = cookie_header(creds)
    headers["x-rpc-device_id"] = creds.device_id
    headers["User-Agent"] = USER_AGENT
    if signgame:
        headers["x-rpc-signgame"] = signgame
        headers["X-Rpc-Signgame"] = signgame
    return headers


def _game_headers_for_meta(
    creds: MihoyoCredentials, meta: dict[str, str], *, ds: str | None = None
) -> dict[str, str]:
    return _game_headers(
        creds,
        referer=meta.get("referer") or "https://act.mihoyo.com/",
        origin=meta.get("origin") or None,
        signgame=meta.get("signgame") or None,
        ds=ds,
    )


def _mall_list_headers(creds: MihoyoCredentials) -> dict[str, str]:
    """对齐 mystool HEADERS_GOOD_LIST。"""
    creds = _ensure_device_id(_normalize_creds(creds))
    return {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://user.mihoyo.com",
        "x-rpc-device_id": creds.device_id,
        "x-rpc-client_type": MYS_CLIENT_TYPE_WEB,
        "User-Agent": USER_AGENT,
        "Referer": "https://user.mihoyo.com/",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Cookie": cookie_header(creds),
    }


def _mall_points_headers(creds: MihoyoCredentials) -> dict[str, str]:
    """对齐 mystool HEADERS_MYB。"""
    creds = _normalize_creds(creds)
    return {
        "Origin": "https://webstatic.mihoyo.com",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": USER_AGENT,
        "Referer": "https://webstatic.mihoyo.com/",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Cookie": cookie_header(creds),
    }


def _mall_exchange_headers(creds: MihoyoCredentials) -> dict[str, str]:
    """对齐 mystool HEADERS_EXCHANGE。"""
    creds = _ensure_device_id(_normalize_creds(creds))
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://webstatic.miyoushe.com",
        "Referer": "https://webstatic.miyoushe.com/",
        "User-Agent": USER_AGENT,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-channel": "appstore",
        "x-rpc-client_type": "1",
        "x-rpc-verify_key": BBS_VERIFY_KEY,
        "x-rpc-device_id": creds.device_id,
        "x-rpc-device_model": "iPhone14,2",
        "x-rpc-device_name": "iPhone",
        "x-rpc-sys_version": "16.6",
        "Cookie": cookie_header(creds),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mall_next_time(raw: Any) -> str | None:
    ts = _safe_int(raw, 0)
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, BEIJING).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _mall_item_meta(row: dict[str, Any], *, game_key: str = "") -> tuple[str, str, str]:
    biz = str(row.get("game_biz") or "").strip()
    key = str(row.get("game") or game_key or "").strip()
    if key.endswith("_cn"):
        key = key[: -len("_cn")]
    biz_meta = GAME_BIZ_META.get(biz, {})
    mall_meta = MALL_GAME_META.get(key, ("", ""))
    game_code = str(biz_meta.get("game_code") or mall_meta[0] or "")
    game_name = str(
        biz_meta.get("game_name")
        or mall_meta[1]
        or row.get("game_name")
        or biz
        or "米游社"
    )
    return biz, game_code, game_name


def _parse_exchange_item(row: dict[str, Any], *, game_key: str = "") -> ExchangeItem | None:
    gid = str(row.get("goods_id") or row.get("id") or "").strip()
    if not gid:
        return None
    unlimit = bool(row.get("unlimit"))
    limit = 0 if unlimit else _safe_int(
        row.get("account_cycle_limit") or row.get("exchange_limit") or row.get("buy_limit")
    )
    biz, game_code, game_name = _mall_item_meta(row, game_key=game_key)
    return ExchangeItem(
        goods_id=gid,
        goods_name=str(row.get("goods_name") or row.get("name") or "商品").strip(),
        goods_num=max(_safe_int(row.get("goods_num") or row.get("num"), 1), 1),
        goods_img=str(row.get("icon") or row.get("goods_img") or "").strip(),
        price=_safe_int(row.get("price") or row.get("goods_price")),
        exchange_limit=limit,
        exchanged_count=_safe_int(
            row.get("account_exchange_count")
            or row.get("exchanged_count")
            or row.get("buy_num")
        ),
        next_exchange_time=_mall_next_time(row.get("next_time") or row.get("next_exchange_time")),
        game_biz=biz,
        game_code=game_code,
        game_name=game_name,
        goods_type=_safe_int(row.get("type")),
    )


def _fetch_mall_page(
    creds: MihoyoCredentials, *, game: str, page: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = _http_json(
        "GET",
        bbs_setting.url_good_list,
        headers=_mall_list_headers(creds),
        params={
            "app_id": bbs_setting.mall_app_id,
            "point_sn": bbs_setting.mall_point_sn,
            "page_size": bbs_setting.mall_page_size,
            "page": page,
            "game": game,
        },
    )
    data = _assert_ok(payload)
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    games = data.get("games") if isinstance(data.get("games"), list) else []
    return (
        [row for row in rows if isinstance(row, dict)],
        [row for row in games if isinstance(row, dict)],
    )


def _mall_partition_keys(creds: MihoyoCredentials) -> list[str]:
    _, games = _fetch_mall_page(creds, game="", page=1)
    keys = [str(row.get("key") or "").strip() for row in games]
    keys = [key for key in keys if key]
    if keys:
        return keys
    return list(bbs_setting.mall_game_keys)


def _list_goods_for_game(creds: MihoyoCredentials, game: str) -> list[ExchangeItem]:
    out: list[ExchangeItem] = []
    page_size = bbs_setting.mall_page_size
    for page in range(1, 21):
        rows, _ = _fetch_mall_page(creds, game=game, page=page)
        if not rows:
            break
        for row in rows:
            item = _parse_exchange_item(row, game_key=game)
            if item:
                out.append(item)
        if len(rows) < page_size:
            break
    return out


def _default_address_id(creds: MihoyoCredentials) -> str:
    payload = _http_json(
        "GET",
        bbs_setting.url_address,
        headers=_mall_list_headers(creds),
        params={"t": int(time.time() * 1000)},
    )
    data = _assert_ok(payload)
    rows = data.get("list") if isinstance(data.get("list"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        aid = str(row.get("id") or row.get("address_id") or "").strip()
        if aid:
            return aid
    return ""


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
    raw_body: str | None = None,
) -> dict[str, Any]:
    req_headers = dict(headers)
    content: bytes | None = None
    json_payload: dict[str, Any] | None = None
    if raw_body is not None:
        content = raw_body.encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json; charset=UTF-8")
    elif json_body is not None:
        json_payload = json_body
    request_kw: dict[str, Any] = {
        "headers": req_headers,
        "params": params,
    }
    if content is not None:
        request_kw["content"] = content
    elif json_payload is not None:
        request_kw["json"] = json_payload
    try:
        resp = http_request(
            method.upper(),
            url,
            timeout=REQUEST_TIMEOUT,
            **request_kw,
        )
        payload = resp.json()
    except HttpRequestError as exc:
        raise MihoyoApiError(f"网络错误：{exc}") from exc
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


def refresh_cookie_token(
    creds: MihoyoCredentials, *, force: bool = False
) -> MihoyoCredentials:
    """stoken(+mid) → cookie_token。force 时覆盖已有 token（对齐 update_cookie_token）。"""
    creds = _normalize_creds(creds)
    parts = parse_cookie_string(creds.cookie)
    if not force and (parts.get("cookie_token") or parts.get("cookie_token_v2")):
        return creds
    cookie = stoken_cookie_header(creds)
    url = bbs_setting.bbs_get_cookie_token_by_stoken
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,en-US;q=0.8",
        "User-Agent": USER_AGENT,
        "x-rpc-app_version": MYS_VERSION,
        "x-rpc-client_type": MYS_CLIENT_TYPE_WEB,
        "x-rpc-channel": "miyousheluodi",
        "X-Requested-With": "com.mihoyo.hyperion",
        "Cookie": cookie,
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
    url = bbs_setting.bbs_user_full_info
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
    url = bbs_setting.bbs_user_businesses
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
    """getUserGameRolesByCookie；-100 时刷新 cookie_token（MihoyoBBSTools account.py）。"""
    creds = _normalize_creds(creds)
    parts = parse_cookie_string(creds.cookie)
    if not parts.get("cookie_token") and not parts.get("cookie_token_v2"):
        try:
            creds = refresh_cookie_token(creds, force=True)
        except MihoyoApiError as exc:
            logger.warning("mihoyo refresh_cookie_token for roles failed: %s", exc.message)

    def _fetch(working: MihoyoCredentials) -> list[Any]:
        url = bbs_setting.account_Info_url
        payload = _http_json(
            "GET",
            url,
            headers=_game_headers(working, referer="https://act.mihoyo.com/"),
        )
        data = _assert_ok(payload)
        return data.get("list") if isinstance(data.get("list"), list) else []

    rows: list[Any] = []
    try:
        rows = call_with_cookie_refresh(creds, _fetch)
    except MihoyoApiError as exc:
        logger.warning("mihoyo getUserGameRolesByCookie failed: %s", exc.message)

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
        region_name = str(row.get("region_name") or "").strip()
        out.append(
            GameRole(
                game_biz=biz,
                game_code=meta["game_code"],
                game_name=meta["game_name"],
                role_uid=uid,
                role_name=nickname,
                region=region,
                channel_name=region_label(region, region_name),
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

    def _run(working: MihoyoCredentials) -> int:
        payload = _http_json(
            "GET",
            bbs_setting.url_myb_points,
            headers=_mall_points_headers(working),
            params={
                "app_id": bbs_setting.mall_app_id,
                "point_sn": bbs_setting.mall_point_sn,
            },
        )
        data = _assert_ok(payload)
        return _safe_int(data.get("points") or data.get("mcoin_balance"))

    return call_with_cookie_refresh(creds, _run)


def list_exchange_goods(creds: MihoyoCredentials, *, app_id: int = 1) -> list[ExchangeItem]:
    del app_id  # 固定 mystool app_id=1 / point_sn=myb
    creds = _normalize_creds(creds)

    def _run(working: MihoyoCredentials) -> list[ExchangeItem]:
        seen: set[str] = set()
        out: list[ExchangeItem] = []
        for game in _mall_partition_keys(working):
            for item in _list_goods_for_game(working, game):
                if item.goods_id in seen:
                    continue
                seen.add(item.goods_id)
                out.append(item)
        return out

    return call_with_cookie_refresh(creds, _run)


def exchange_goods(
    creds: MihoyoCredentials,
    *,
    goods_id: str,
    game_biz: str = "",
    region: str = "",
    role_uid: str = "",
    exchange_num: int = 1,
    goods_type: int = 0,
) -> dict[str, Any]:
    creds = _normalize_creds(creds)

    def _run(working: MihoyoCredentials) -> dict[str, Any]:
        uid = str(role_uid or working.stuid or working.ltuid or working.account_id).strip()
        body: dict[str, Any] = {
            "app_id": bbs_setting.mall_app_id,
            "point_sn": bbs_setting.mall_point_sn,
            "goods_id": str(goods_id),
            "exchange_num": int(exchange_num),
            "uid": uid,
        }
        if region:
            body["region"] = region
        if game_biz:
            body["game_biz"] = game_biz
        if goods_type == 2:
            address_id = _default_address_id(working)
            if not address_id:
                raise MihoyoApiError("该商品需要收货地址，请先在米游社填写后再兑换")
            body["address_id"] = address_id
        payload = _http_json(
            "POST",
            bbs_setting.url_exchange,
            headers=_mall_exchange_headers(working),
            json_body=body,
        )
        _assert_ok(payload)
        return payload

    return call_with_cookie_refresh(creds, _run)


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
