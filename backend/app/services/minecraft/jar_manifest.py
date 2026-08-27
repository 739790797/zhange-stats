"""从 Minecraft jar 读模组/插件身份（不把文件名当身份）。"""

from __future__ import annotations

import json
import re
import tomllib
import zipfile
from io import BytesIO
from typing import Any

_PLACEHOLDER_VER = re.compile(r"^\$\{.+\}$")
_MANIFEST_KEYS = ("Implementation-Version", "Specification-Version")


class JarManifestError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _clean_version(raw: str) -> str:
    text = (raw or "").strip()
    if not text or _PLACEHOLDER_VER.match(text):
        return ""
    return text


def _clean_id(raw: str) -> str:
    return (raw or "").strip()


def _read_zip_text(zf: zipfile.ZipFile, name: str) -> str:
    try:
        data = zf.read(name)
    except KeyError:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _names_lower(zf: zipfile.ZipFile) -> dict[str, str]:
    out: dict[str, str] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        out[name.lower()] = name
    return out


def _parse_fabric(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    mod_id = _clean_id(str(data.get("id") or ""))
    name = str(data.get("name") or "").strip() or mod_id
    version = _clean_version(str(data.get("version") or ""))
    if not mod_id:
        return None
    return {"mod_ids": [mod_id], "mod_names": [name] if name else [mod_id], "mod_version": version}


def _parse_mods_toml(text: str) -> dict[str, Any] | None:
    parsed: Any = None
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        parsed = None
    ids: list[str] = []
    names: list[str] = []
    version = ""
    if isinstance(parsed, dict):
        mods = parsed.get("mods")
        rows = mods if isinstance(mods, list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mod_id = _clean_id(str(row.get("modId") or row.get("mod_id") or ""))
            if not mod_id:
                continue
            ids.append(mod_id)
            display = str(row.get("displayName") or row.get("display_name") or "").strip()
            names.append(display or mod_id)
            if not version:
                version = _clean_version(str(row.get("version") or ""))
    if not ids:
        ids = [_clean_id(m) for m in re.findall(r'modId\s*=\s*"([^"]+)"', text)]
        ids = [row for row in ids if row]
        display = re.search(r'displayName\s*=\s*"([^"]+)"', text)
        names = [display.group(1).strip()] if display else list(ids)
        ver = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
        version = _clean_version(ver.group(1) if ver else "")
    if not ids:
        return None
    if not names:
        names = list(ids)
    return {"mod_ids": ids, "mod_names": names, "mod_version": version}


def _yaml_scalar(text: str, key: str) -> str:
    pattern = re.compile(rf"(?im)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$")
    match = pattern.search(text)
    if not match:
        return ""
    value = match.group(1).strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value.strip()


def _parse_plugin_yml(text: str) -> dict[str, Any] | None:
    name = _yaml_scalar(text, "name")
    version = _clean_version(_yaml_scalar(text, "version"))
    plugin_id = _clean_id(_yaml_scalar(text, "id") or name)
    if not plugin_id and not name:
        return None
    display = name or plugin_id
    ident = plugin_id or name
    return {"mod_ids": [ident], "mod_names": [display], "mod_version": version}


def _parse_velocity(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    mod_id = _clean_id(str(data.get("id") or ""))
    name = str(data.get("name") or "").strip() or mod_id
    version = _clean_version(str(data.get("version") or ""))
    if not mod_id:
        return None
    return {"mod_ids": [mod_id], "mod_names": [name], "mod_version": version}


def _parse_manifest(text: str) -> str:
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() in _MANIFEST_KEYS:
            version = _clean_version(value.strip())
            if version:
                return version
    return ""


def parse_jar_bytes(data: bytes) -> dict[str, Any]:
    """拆包读身份。缺元数据时返回空 ids（仍算读过包）。损坏 zip 抛 `JarManifestError`。"""
    if not data:
        raise JarManifestError("空文件")
    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise JarManifestError("不是有效的 jar") from exc
    with zf:
        names = _names_lower(zf)
        parsed: dict[str, Any] | None = None
        for candidate, reader in (
            ("fabric.mod.json", _parse_fabric),
            ("quilt.mod.json", _parse_fabric),
            ("velocity-plugin.json", _parse_velocity),
            ("plugin.yml", _parse_plugin_yml),
            ("paper-plugin.yml", _parse_plugin_yml),
            ("bungee.yml", _parse_plugin_yml),
            ("meta-inf/mods.toml", _parse_mods_toml),
            ("meta-inf/neoforge.mods.toml", _parse_mods_toml),
        ):
            real = names.get(candidate)
            if not real:
                continue
            parsed = reader(_read_zip_text(zf, real))
            if parsed:
                break
        manifest_ver = ""
        manifest_name = names.get("meta-inf/manifest.mf")
        if manifest_name:
            manifest_ver = _parse_manifest(_read_zip_text(zf, manifest_name))
    if not parsed:
        return {
            "mod_ids": [],
            "mod_names": [],
            "mod_version": manifest_ver,
        }
    if not parsed.get("mod_version") and manifest_ver:
        parsed["mod_version"] = manifest_ver
    return parsed
