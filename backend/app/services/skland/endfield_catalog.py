"""终末地可操作干员图鉴：从本地 EndfieldData 表读取。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.upstream_repos import REPO_ENDFIELD, RepoError, ensure_repo, repo_dir

_PLAYABLE_EXTRA_IDS = {"chr_0002_endminm", "chr_0003_endminf"}
_cache_signature: tuple[tuple[str, int], ...] | None = None
_cache_catalog: list[dict[str, Any]] | None = None


class EndfieldCatalogError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _read_table(root: Path, name: str, *, required: bool = True) -> dict[str, Any]:
    path = root / "TableCfg" / name
    if not path.is_file():
        if required:
            raise EndfieldCatalogError(f"缺少 {name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EndfieldCatalogError(f"{name} 无法解析") from exc
    if not isinstance(payload, dict):
        raise EndfieldCatalogError(f"{name} 格式无效")
    return payload


def _i18n_index(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, str) and value.strip():
            out[str(key)] = value.strip()
        elif isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str) and text.strip():
                out[str(key)] = text.strip()
    return out


def _localized(value: Any, i18n: dict[str, str]) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    direct = value.get("text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    ident = value.get("id")
    return i18n.get(str(ident), "") if ident not in (None, 0, "0") else ""


def parse_character_tables(
    characters: dict[str, Any],
    gacha_characters: dict[str, Any],
    professions: dict[str, Any],
    i18n_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """投影可招募角色与主角性别版本，排除剧情/NPC character rows。"""
    i18n = _i18n_index(i18n_payload)
    profession_names: dict[str, str] = {}
    for key, value in professions.items():
        if isinstance(value, dict):
            label = _localized(value.get("name"), i18n)
            if label:
                profession_names[str(value.get("profession", key))] = label

    playable_ids = set(gacha_characters) | _PLAYABLE_EXTRA_IDS
    rows: list[dict[str, Any]] = []
    for char_id, raw in characters.items():
        char_id = str(char_id)
        if char_id not in playable_ids or not isinstance(raw, dict):
            continue
        name = _localized(raw.get("name"), i18n) or str(raw.get("engName") or char_id)
        try:
            rarity = int(raw.get("rarity", 0))
            sort_order = int(raw.get("sortOrder", 0))
            profession_id = str(int(raw.get("profession", 0)))
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "char_id": char_id,
                "name": name[:64],
                "rarity": max(1, min(6, rarity)),
                "profession": profession_id,
                "profession_label": profession_names.get(profession_id, "未知"),
                "sort_order": sort_order,
            }
        )
    rows.sort(key=lambda row: (row["sort_order"], row["char_id"]))
    if not rows:
        raise EndfieldCatalogError("未解析到终末地可操作干员")
    return rows


def list_operators(*, root: Path | None = None) -> list[dict[str, Any]]:
    """读取本地上游克隆；提供 root 仅用于无网络的临时目录测试。"""
    global _cache_signature, _cache_catalog
    if root is None:
        try:
            ensure_repo(REPO_ENDFIELD)
        except RepoError:
            raise
        root = repo_dir(REPO_ENDFIELD)
        names = (
            "CharacterTable.json",
            "GachaCharInfoTable.json",
            "CharProfessionTable.json",
            "I18nTextTable_CN.json",
        )
        signature = tuple(
            (
                name,
                (root / "TableCfg" / name).stat().st_mtime_ns
                if (root / "TableCfg" / name).is_file()
                else 0,
            )
            for name in names
        )
        if signature == _cache_signature and _cache_catalog is not None:
            return _cache_catalog
    else:
        signature = None
        names = (
            "CharacterTable.json",
            "GachaCharInfoTable.json",
            "CharProfessionTable.json",
            "I18nTextTable_CN.json",
        )

    tables = {name: _read_table(root, name) for name in names}
    result = parse_character_tables(
        tables["CharacterTable.json"],
        tables["GachaCharInfoTable.json"],
        tables["CharProfessionTable.json"],
        tables["I18nTextTable_CN.json"],
    )
    if signature is not None:
        _cache_signature, _cache_catalog = signature, result
    return result
