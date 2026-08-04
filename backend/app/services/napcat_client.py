"""NapCat OneBot HTTP 客户端。

支持两种接入方式：
1. OneBot HTTP 服务：POST {base}/{action}
2. NapCat WebUI 调试代理：POST {base}/api/Debug/call（Base URL 误填 WebUI 时自动回退）
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

_WEBUI_HINT = (
    "当前地址像是 NapCat WebUI，不是 OneBot HTTP 服务。"
    "请在 NapCat「网络配置」启用 HTTP 服务，把该地址填到 Base URL"
    "（例如 http://127.0.0.1:3000）；若仅内网可访问，请用反向代理对外暴露。"
    "也可继续使用 WebUI 地址，但 Token 须为 WebUI 登录后的 Bearer 令牌"
    "（浏览器本地存储中的 token），将走 /api/Debug/call。"
)


class NapCatError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_napcat_base_url(base_url: str) -> str:
    root = (base_url or "").strip().rstrip("/")
    if not root:
        return ""
    # 常见误填：带 /webui 的管理页地址
    while True:
        lower = root.lower()
        if lower.endswith("/webui"):
            root = root[: -len("/webui")].rstrip("/")
            continue
        if lower.endswith("/webui/debug/http"):
            root = root[: -len("/webui/debug/http")].rstrip("/")
            continue
        break
    return root


def _request_json(
    url: str,
    token: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> tuple[int, str, Any | None]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token.strip()}",
            "User-Agent": "zhange-stats/napcat",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            raw = ""
        return int(exc.code), raw, None
    except urllib.error.URLError as exc:
        raise NapCatError(f"无法连接 NapCat：{exc.reason}") from exc
    except TimeoutError as exc:
        raise NapCatError("NapCat 请求超时") from exc

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return status, raw, None
    return status, raw, parsed


def _looks_like_webui_miss(status: int, raw: str) -> bool:
    if status != 404:
        return False
    text = (raw or "").lower()
    return (
        "cannot post" in text
        or "<!doctype html" in text
        or "<html" in text
        or "express" in text
    )


def _looks_like_webui_json(data: Any) -> bool:
    return isinstance(data, dict) and "code" in data and "retcode" not in data


def _parse_onebot_payload(data: dict[str, Any]) -> Any:
    retcode = data.get("retcode", 0)
    try:
        retcode_int = int(retcode) if retcode is not None else 0
    except (TypeError, ValueError):
        retcode_int = -1
    status = str(data.get("status") or "").lower()
    if retcode_int != 0:
        raise NapCatError(
            str(
                data.get("message")
                or data.get("wording")
                or f"NapCat 错误 retcode={retcode}"
            )
        )
    if status in ("failed", "error"):
        raise NapCatError(
            str(data.get("message") or data.get("wording") or "NapCat 请求失败")
        )
    return data.get("data")


def _parse_webui_debug_payload(data: dict[str, Any]) -> Any:
    code = data.get("code")
    try:
        code_int = int(code) if code is not None else -1
    except (TypeError, ValueError):
        code_int = -1
    if code_int != 0:
        msg = str(data.get("message") or "WebUI 调试调用失败")
        if "unauthorized" in msg.lower() or code_int in (-1, 401, 403):
            raise NapCatError(
                f"{msg}。{_WEBUI_HINT}",
                status_code=401,
            )
        raise NapCatError(msg)

    inner = data.get("data")
    # callApi 可能直接返回业务 data，也可能返回完整 OneBot 包
    if isinstance(inner, dict) and ("retcode" in inner or "status" in inner):
        return _parse_onebot_payload(inner)
    return inner


def _post_action(
    base_url: str,
    token: str,
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    root = normalize_napcat_base_url(base_url)
    if not root:
        raise NapCatError("未配置 NapCat Base URL")
    if not (token or "").strip():
        raise NapCatError("未配置 NapCat Token")

    params = payload or {}
    onebot_url = f"{root}/{action.lstrip('/')}"
    status, raw, parsed = _request_json(onebot_url, token, params, timeout=timeout)

    if status == 200 and isinstance(parsed, dict) and not _looks_like_webui_json(parsed):
        return _parse_onebot_payload(parsed)

    # WebUI 鉴权 JSON（误打到 /api/*）或 Express HTML 404 → 改走 Debug/call
    should_try_webui = _looks_like_webui_miss(status, raw) or (
        status in (200, 401) and _looks_like_webui_json(parsed)
    )
    if not should_try_webui and status >= 400:
        snippet = re.sub(r"\s+", " ", (raw or ""))[:120]
        if _looks_like_webui_miss(status, raw) or "cannot post" in (raw or "").lower():
            raise NapCatError(_WEBUI_HINT, status_code=status)
        raise NapCatError(
            f"NapCat HTTP {status}" + (f"：{snippet}" if snippet else ""),
            status_code=status,
        )

    if should_try_webui:
        debug_url = f"{root}/api/Debug/call"
        d_status, d_raw, d_parsed = _request_json(
            debug_url,
            token,
            {"action": action, "params": params},
            timeout=timeout,
        )
        if d_status == 200 and isinstance(d_parsed, dict):
            return _parse_webui_debug_payload(d_parsed)
        if d_status in (401, 403) or (
            isinstance(d_parsed, dict)
            and str(d_parsed.get("message") or "").lower().find("unauthorized") >= 0
        ):
            raise NapCatError(
                f"WebUI 鉴权失败。{_WEBUI_HINT}",
                status_code=d_status or 401,
            )
        snippet = re.sub(r"\s+", " ", (d_raw or ""))[:120]
        raise NapCatError(
            f"NapCat WebUI 调试调用失败 HTTP {d_status}"
            + (f"：{snippet}" if snippet else ""),
            status_code=d_status,
        )

    if parsed is None:
        raise NapCatError("NapCat 返回非 JSON")
    if not isinstance(parsed, dict):
        raise NapCatError("NapCat 返回格式异常")
    return _parse_onebot_payload(parsed)


def get_group_list(base_url: str, token: str, *, no_cache: bool = False) -> list[dict]:
    payload: dict[str, Any] = {}
    if no_cache:
        payload["no_cache"] = True
    data = _post_action(base_url, token, "get_group_list", payload)
    if data is None:
        return []
    if not isinstance(data, list):
        raise NapCatError("群列表格式异常")
    return [item for item in data if isinstance(item, dict)]


def get_group_member_list(
    base_url: str,
    token: str,
    group_id: str | int,
    *,
    no_cache: bool = False,
) -> list[dict]:
    payload: dict[str, Any] = {"group_id": group_id}
    if no_cache:
        payload["no_cache"] = True
    data = _post_action(base_url, token, "get_group_member_list", payload)
    if data is None:
        return []
    if not isinstance(data, list):
        raise NapCatError("群成员列表格式异常")
    return [item for item in data if isinstance(item, dict)]


def describe_base_url_kind(base_url: str) -> str:
    """供日志/诊断：粗略判断配置像不像 WebUI。"""
    root = normalize_napcat_base_url(base_url)
    try:
        host = urlparse(root).netloc
    except Exception:  # noqa: BLE001
        host = ""
    return host or root
