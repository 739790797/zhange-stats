"""将用户输入的多种 Steam 标识解析为 SteamID64。"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

STEAMID64_BASE = 76561197960265728
# s.team/p/ 短邀请码字符表（与 Valve 编码一致）
_INVITE_ALPHABET = "bcdfghjkmnpqrtvwxyz23456789"
_INVITE_LOOKUP = {c: i for i, c in enumerate(_INVITE_ALPHABET)}


def account_id_to_steamid64(account_id: int) -> str:
    if account_id < 1 or account_id > 0xFFFFFFFF:
        raise ValueError("好友码/账号 ID 无效")
    return str(STEAMID64_BASE + account_id)


def decode_invite_code(code: str) -> str:
    """解码 s.team/p/{code} 中的短码为 SteamID64。"""
    cleaned = re.sub(r"[^0-9a-z]", "", code.lower())
    if not cleaned:
        raise ValueError("邀请码无效")
    value = 0
    for ch in cleaned:
        if ch not in _INVITE_LOOKUP:
            raise ValueError("邀请码包含非法字符")
        value = value * len(_INVITE_ALPHABET) + _INVITE_LOOKUP[ch]
    return account_id_to_steamid64(value)


def resolve_vanity(api_key: str, vanity: str) -> str:
    if not api_key:
        raise RuntimeError("STEAM_API_KEY 未配置，无法解析自定义主页名")
    params = urllib.parse.urlencode(
        {"key": api_key, "vanityurl": vanity, "url_type": 1}
    )
    url = f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "zhange-stats/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Steam 解析失败 HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Steam 网络错误: {exc}") from exc

    response = (payload or {}).get("response") or {}
    if int(response.get("success") or 0) != 1 or not response.get("steamid"):
        raise ValueError("未找到该 Steam 自定义主页名")
    return str(response["steamid"])


def resolve_steam_input(raw: str, api_key: str = "") -> str:
    """
    支持：
    - SteamID64
    - 好友码（AccountID 数字）
    - steamcommunity.com/profiles/...
    - steamcommunity.com/id/... 或纯 vanity
    - s.team/p/... 邀请链接/短码
    - STEAM_0:Y:Z / [U:1:accountid]
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("请输入 Steam 标识")

    # 完整 URL 或带协议的链接
    lower = text.lower()
    if "s.team/p/" in lower:
        m = re.search(r"s\.team/p/([a-z0-9\-]+)", lower)
        if not m:
            raise ValueError("无法解析邀请链接")
        return decode_invite_code(m.group(1))

    if "steamcommunity.com/profiles/" in lower:
        m = re.search(r"profiles/(\d{15,20})", lower)
        if not m:
            raise ValueError("无法从资料链接解析 SteamID")
        return m.group(1)

    if "steamcommunity.com/id/" in lower:
        m = re.search(r"id/([^/?#]+)", lower)
        if not m:
            raise ValueError("无法从自定义主页链接解析名称")
        return resolve_vanity(api_key, urllib.parse.unquote(m.group(1)))

    if "steamcommunity.com/user/" in lower:
        m = re.search(r"user/([a-z0-9\-]+)", lower)
        if m:
            return decode_invite_code(m.group(1))

    # STEAM_0:Y:Z
    m = re.fullmatch(r"STEAM_[0-5]:([01]):(\d+)", text, flags=re.IGNORECASE)
    if m:
        y, z = int(m.group(1)), int(m.group(2))
        return account_id_to_steamid64(z * 2 + y)

    # [U:1:accountid]
    m = re.fullmatch(r"\[?U:1:(\d+)\]?", text, flags=re.IGNORECASE)
    if m:
        return account_id_to_steamid64(int(m.group(1)))

    # 纯数字：SteamID64 或好友码(AccountID)
    if re.fullmatch(r"\d+", text):
        if text.startswith("7656119") and len(text) >= 15:
            return text
        return account_id_to_steamid64(int(text))

    # 短邀请码 abcd-efgh
    if re.fullmatch(r"[a-z0-9]{4,5}(-[a-z0-9]{4,5}){1,3}", text, flags=re.IGNORECASE):
        return decode_invite_code(text)

    # 当作 vanity 名称
    if re.fullmatch(r"[A-Za-z0-9_\-]{2,64}", text):
        return resolve_vanity(api_key, text)

    raise ValueError("无法识别的 Steam 标识，请粘贴资料链接或好友码")
