"""生成 mrpack / boot 脚本 / server.properties 合并。"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

LOADERS = ("fabric", "quilt", "forge", "neoforge")

LOADER_DEP_KEY = {
    "fabric": "fabric-loader",
    "quilt": "quilt-loader",
    "forge": "forge",
    "neoforge": "neoforge",
}

BOOT_SH = """#!/usr/bin/env bash
set -euo pipefail
ROOT="${PWD}"
ZHANGE="${ROOT}/zhange"
PACK="${ZHANGE}/pack.mrpack"
BIN="${ZHANGE}/mrpack-install"
mkdir -p "${ZHANGE}" "${ROOT}/mods" "${ROOT}/config"

if [ ! -x "${BIN}" ]; then
  echo "[zhange] mrpack-install 不存在，跳过包安装（请用战鸽「应用」拉取二进制）"
else
  if [ -f "${PACK}" ]; then
    echo "[zhange] 按档案对齐加载器与模组…"
    "${BIN}" "${PACK}" --server-dir "${ROOT}" || echo "[zhange] mrpack-install 失败，继续启动"
  fi
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "[zhange] 启动命令为空。请把 Egg 启动改成：bash zhange/boot.sh <原来的 java 命令>"
exit 1
"""

MRPACK_INSTALL_URL = (
    "https://github.com/nothub/mrpack-install/releases/latest/download/"
    "mrpack-install-linux"
)

COMMON_PROPERTY_KEYS = (
    "motd",
    "max-players",
    "difficulty",
    "gamemode",
    "white-list",
    "enforce-whitelist",
    "view-distance",
    "simulation-distance",
    "pvp",
    "online-mode",
    "spawn-protection",
    "enable-command-block",
)

SECRET_PROPERTY_KEYS = frozenset({"rcon.password"})
RCON_DEFAULT_PORT = 25575


def redact_properties(props: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in (props or {}).items()
        if key not in SECRET_PROPERTY_KEYS
    }


def merge_rcon_properties(
    text: str,
    *,
    enabled: bool,
    port: int,
    password: str,
) -> str:
    listen = port if 1 <= int(port or 0) <= 65535 else RCON_DEFAULT_PORT
    updates = {
        "enable-rcon": "true" if enabled else "false",
        "rcon.port": str(listen),
        "broadcast-rcon-to-ops": "false",
    }
    secret = (password or "").strip()
    if secret:
        updates["rcon.password"] = secret
    elif not enabled:
        updates["rcon.password"] = ""
    return merge_properties(text, updates)


def parse_properties(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            out[key] = value
    return out


def merge_properties(text: str, updates: dict[str, str]) -> str:
    """按原文件顺序改值；新键追加在末尾。"""
    updates_clean = {
        str(k).strip(): str(v)
        for k, v in (updates or {}).items()
        if str(k).strip()
    }
    if not text and not updates_clean:
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in updates_clean:
                lines.append(f"{key}={updates_clean[key]}")
                seen.add(key)
                continue
        lines.append(raw_line)
    for key, value in updates_clean.items():
        if key not in seen:
            lines.append(f"{key}={value}")
            seen.add(key)
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def normalize_loader(value: str) -> str:
    loader = (value or "").strip().lower()
    if loader not in LOADERS:
        raise ValueError("加载器须为 fabric / quilt / forge / neoforge")
    return loader


def normalize_override_path(path: str) -> str:
    rel = (path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise ValueError(f"非法覆盖路径：{path}")
    return rel


def build_overrides_map(
    properties: dict[str, str],
    extra: list[dict[str, str]],
    *,
    existing_properties_text: str = "",
) -> dict[str, str]:
    out: dict[str, str] = {}
    props_text = merge_properties(existing_properties_text, properties)
    if props_text.strip():
        out["server.properties"] = props_text
    for row in extra:
        path = normalize_override_path(str(row.get("path") or ""))
        if path == "server.properties":
            continue
        out[path] = str(row.get("content") or "")
    return out


def loader_dep_key(loader: str) -> str:
    return LOADER_DEP_KEY[normalize_loader(loader)]


def build_mrpack_bytes(
    *,
    mc_version: str,
    loader: str,
    loader_version: str,
    mods: list[dict[str, Any]],
    overrides: dict[str, str],
) -> bytes:
    loader = normalize_loader(loader)
    files: list[dict[str, Any]] = []
    for mod in mods:
        if not isinstance(mod, dict):
            continue
        if str(mod.get("env_server") or "") == "unsupported":
            continue
        filename = str(mod.get("filename") or "").strip()
        url = str(mod.get("download_url") or "").strip()
        sha512 = str(mod.get("sha512") or "").strip()
        if not filename or not url or not sha512:
            continue
        hashes: dict[str, str] = {"sha512": sha512}
        sha1 = str(mod.get("sha1") or "").strip()
        if sha1:
            hashes["sha1"] = sha1
        env_server = str(mod.get("env_server") or "required")
        files.append(
            {
                "path": f"mods/{filename}",
                "hashes": hashes,
                "downloads": [url],
                "fileSize": int(mod.get("file_size") or 0),
                "env": {"client": "optional", "server": env_server},
            }
        )
    deps: dict[str, str] = {"minecraft": mc_version}
    if loader_version:
        deps[loader_dep_key(loader)] = loader_version
    index = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": "zhange",
        "name": "Zhange Minecraft",
        "summary": "Desired state from Zhange Stats",
        "files": files,
        "dependencies": deps,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modrinth.index.json", json.dumps(index, ensure_ascii=False, indent=2))
        for rel, content in (overrides or {}).items():
            path = normalize_override_path(rel)
            zf.writestr(f"server-overrides/{path}", content or "")
    return buf.getvalue()


def desired_json(
    *,
    mc_version: str,
    loader: str,
    loader_version: str,
    mods: list[dict[str, Any]],
) -> str:
    body = {
        "mc_version": mc_version,
        "loader": normalize_loader(loader),
        "loader_version": loader_version,
        "mods": [
            {
                "filename": m.get("filename"),
                "sha512": m.get("sha512"),
                "download_url": m.get("download_url"),
            }
            for m in mods
            if isinstance(m, dict) and m.get("filename")
        ],
    }
    return json.dumps(body, ensure_ascii=False, indent=2) + "\n"
