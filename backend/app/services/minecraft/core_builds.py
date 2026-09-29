"""非整合包核心的可下载版本。Arclight 按服上的 Minecraft 版本和加载器去列构建。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.http_client import HttpRequestError, http_request

_FILES = "https://files.hypertention.cn/v1/files"
_NAME_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,80}$")
_LOADERS = {"neoforge", "forge", "fabric"}
_CHANNELS = ("stable", "snapshot")
_CHANNEL_LABELS = {"stable": "稳定版", "snapshot": "快照"}
_SNAPSHOT_LIMIT = 30


class CoreBuildError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def supports_remote_builds(core_id: str) -> bool:
    return core_id == "arclight"


def is_build_name(name: str) -> bool:
    return _valid_name(name)


def arclight_jar_name(loader: str, mc_version: str, build: str) -> str:
    return f"arclight-{loader}-{mc_version}-{build}.jar"


def _valid_name(name: str) -> bool:
    return bool(_NAME_RE.fullmatch(name or ""))


def builds_from_listing(files: list[dict[str, Any]], *, limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") not in {"object", "directory", "link"}:
            continue
        name = str(item.get("name") or "").strip()
        if not _valid_name(name) or name.startswith("latest-"):
            continue
        link = str(item.get("link") or item.get("permlink") or "").strip()
        rows.append({"name": name, "url": link})
        if len(rows) >= limit:
            break
    return rows


def arclight_download_url(mc_version: str, loader: str, channel: str, build: str) -> str:
    if loader not in _LOADERS or channel not in _CHANNELS or not _valid_name(build):
        raise CoreBuildError("版本无效", status_code=400)
    if not re.fullmatch(r"\d+(?:\.\d+){1,2}", mc_version or ""):
        raise CoreBuildError("认不出 Minecraft 版本", status_code=400)
    return (
        f"{_FILES}/arclight/minecraft/{mc_version}/loaders/{loader}"
        f"/versions-{channel}/{build}"
    )


def _get_json(url: str) -> dict[str, Any]:
    try:
        response = http_request(
            "GET",
            url,
            headers={"Accept": "application/json", "User-Agent": "zhange-stats"},
            timeout=20,
            follow_redirects=True,
        )
    except HttpRequestError as exc:
        raise CoreBuildError("无法获取 Arclight 版本") from exc
    if response.status_code >= 400:
        raise CoreBuildError(f"Arclight 版本列表返回 {response.status_code}")
    try:
        data = json.loads(response.text or "{}")
    except json.JSONDecodeError as exc:
        raise CoreBuildError("Arclight 版本列表不是 JSON") from exc
    if not isinstance(data, dict):
        raise CoreBuildError("Arclight 版本列表无效")
    return data


def list_arclight_builds(loader: str, mc_version: str) -> list[dict[str, Any]]:
    if loader not in _LOADERS:
        raise CoreBuildError(f"Arclight 没有 {loader or '这个'} 加载器的构建", status_code=400)
    options: list[dict[str, Any]] = []
    for channel in _CHANNELS:
        url = (
            f"{_FILES}/arclight/minecraft/{mc_version}/loaders/{loader}"
            f"/versions-{channel}"
        )
        listing = _get_json(url)
        files = listing.get("files")
        limit = 20 if channel == "stable" else _SNAPSHOT_LIMIT
        builds = builds_from_listing(files if isinstance(files, list) else [], limit=limit)
        if not builds:
            continue
        options.append(
            {
                "value": channel,
                "label": _CHANNEL_LABELS[channel],
                "children": [
                    {
                        "value": row["name"],
                        "label": row["name"],
                        "filename": arclight_jar_name(loader, mc_version, row["name"]),
                    }
                    for row in builds
                ],
            }
        )
    if not options:
        raise CoreBuildError(f"没有找到 Minecraft {mc_version} 的 Arclight 构建")
    return options
