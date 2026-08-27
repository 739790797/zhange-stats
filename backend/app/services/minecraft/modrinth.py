"""Modrinth 检索 / 钉版本（只收录服务端可用模组）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.core.http_client import HttpRequestError, http_request

USER_AGENT = "zhange-stats-minecraft/1.0 (github.com/739790797/zhange-stats)"
MODRINTH_API = "https://api.modrinth.com/v2"


class ModrinthError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _get_json(url: str, *, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ModrinthError(f"Modrinth HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ModrinthError(f"无法连接 Modrinth：{exc.reason}") from exc


def _env_server(file_obj: dict[str, Any] | None, version_obj: dict[str, Any]) -> str:
    env = {}
    if isinstance(file_obj, dict) and isinstance(file_obj.get("env"), dict):
        env = file_obj["env"]
    elif isinstance(version_obj.get("env"), dict):
        env = version_obj["env"]
    raw = str(env.get("server") or "required").strip().lower()
    if raw not in {"required", "optional", "unsupported"}:
        return "required"
    return raw


def _primary_file(version: dict[str, Any]) -> dict[str, Any] | None:
    files = version.get("files") if isinstance(version.get("files"), list) else []
    for row in files:
        if isinstance(row, dict) and row.get("primary"):
            return row
    for row in files:
        if isinstance(row, dict):
            return row
    return None


def pin_from_version(
    version: dict[str, Any],
    *,
    project_id: str,
    project_title: str = "",
    slug: str = "",
) -> dict[str, Any] | None:
    file_obj = _primary_file(version)
    if not file_obj:
        return None
    env = _env_server(file_obj, version)
    if env == "unsupported":
        return None
    hashes = file_obj.get("hashes") if isinstance(file_obj.get("hashes"), dict) else {}
    sha512 = str(hashes.get("sha512") or "")
    url = str(file_obj.get("url") or "")
    filename = str(file_obj.get("filename") or "")
    if not sha512 or not url or not filename:
        return None
    return {
        "project_id": project_id,
        "project_title": project_title or str(version.get("name") or project_id),
        "slug": slug,
        "version_id": str(version.get("id") or ""),
        "version_number": str(version.get("version_number") or ""),
        "filename": filename,
        "download_url": url,
        "sha512": sha512,
        "sha1": str(hashes.get("sha1") or ""),
        "file_size": int(file_obj.get("size") or 0),
        "env_server": env,
    }


def list_versions(
    project_id: str,
    *,
    loader: str,
    mc_version: str,
) -> list[dict[str, Any]]:
    pid = (project_id or "").strip()
    if not pid:
        return []
    params: dict[str, str] = {}
    if loader:
        params["loaders"] = json.dumps([loader])
    if mc_version:
        params["game_versions"] = json.dumps([mc_version])
    qs = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{MODRINTH_API}/project/{urllib.parse.quote(pid)}/version{qs}"
    data = _get_json(url)
    if not isinstance(data, list):
        return []
    project_title = ""
    slug = ""
    try:
        proj = _get_json(f"{MODRINTH_API}/project/{urllib.parse.quote(pid)}")
        if isinstance(proj, dict):
            project_title = str(proj.get("title") or "")
            slug = str(proj.get("slug") or "")
    except ModrinthError:
        project_title = ""
    out: list[dict[str, Any]] = []
    for version in data:
        if not isinstance(version, dict):
            continue
        pin = pin_from_version(
            version, project_id=pid, project_title=project_title, slug=slug
        )
        if pin:
            out.append(pin)
    return out


def latest_pin(
    project_id: str,
    *,
    loader: str,
    mc_version: str,
) -> dict[str, Any] | None:
    versions = list_versions(project_id, loader=loader, mc_version=mc_version)
    return versions[0] if versions else None


def versions_from_hashes(hashes: list[str], *, algorithm: str = "sha512") -> dict[str, dict[str, Any]]:
    """用文件哈希批量认 Modrinth 版本；对不上返回空。"""
    wanted = [item.strip() for item in hashes if item and item.strip()]
    if not wanted:
        return {}
    url = f"{MODRINTH_API}/version_files"
    try:
        resp = http_request(
            "POST",
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"hashes": wanted, "algorithm": algorithm},
            timeout=20,
        )
    except HttpRequestError as exc:
        raise ModrinthError(f"无法连接 Modrinth：{exc}") from exc
    if resp.status_code == 404:
        return {}
    if resp.status_code >= 400:
        raise ModrinthError(f"Modrinth HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise ModrinthError("Modrinth 返回无法解析") from exc
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out[str(key)] = value
    return out


def project_icon_url(project_id: str) -> str:
    pid = (project_id or "").strip()
    if not pid:
        return ""
    url = f"{MODRINTH_API}/project/{urllib.parse.quote(pid)}"
    try:
        resp = http_request(
            "GET",
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=20,
        )
    except HttpRequestError:
        return ""
    if resp.status_code >= 400:
        return ""
    try:
        data = resp.json()
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("icon_url") or "")
