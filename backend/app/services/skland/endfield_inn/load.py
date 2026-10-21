"""把 EndfieldData 的 TableCfg 读成求解用的内存结构。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.upstream_repos import REPO_ENDFIELD, RepoError, ensure_repo, repo_dir

_REQUIRED = (
    "InnTopicTable.json",
    "InnRequirementTable.json",
    "InnDescribeTable.json",
    "InnDishTable.json",
    "InnDrinkTable.json",
    "InnAffixTable.json",
    "InnDishCategoryTable.json",
    "InnCharSkillTable.json",
    "InnSkillTable.json",
    "InnLevelTable.json",
    "InnExpansionTable.json",
    "InnManagementConst.json",
    "InnCharTable.json",
)
_OPTIONAL = (
    "I18nTextTable_CN.json",
    "ItemTable.json",
    "CharacterTable.json",
    "GachaCharInfoTable.json",
    "NpcTable.json",
)

AFFIX_CN = {
    "umami": "鲜",
    "salty": "咸",
    "spicy": "辣",
    "sweet": "甜",
    "sour": "酸",
    "meat": "荤",
    "vegetarian": "素",
    "seafood": "海鲜",
    "nourishing": "滋补",
    "aesthetic": "美观",
    "precious": "珍贵",
    "teaScent": "茶香",
    "wineScent": "酒香",
    "milkyScent": "奶香",
    "fruityScent": "果香",
    "rare": "稀有",
}
CATEGORY_CN = {
    "staple": "主食",
    "cuisine": "菜肴",
    "pastry": "甜品",
    "soup": "汤羹",
    "drink": "饮料",
}

_cache_sig: tuple | None = None
_cache_data: dict[str, Any] | None = None


class InnDataError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InnDataUnavailable(InnDataError):
    """本地上游资源尚不可用，例如首次浅克隆失败。"""


class InnInvalidInput(InnDataError):
    """主题、等级或扩建组合无效。"""


class InnTopicNotFound(InnDataError):
    """所选主题不存在。"""


def _read_json(root: Path, name: str, *, required: bool) -> Any:
    path = root / "TableCfg" / name
    if not path.is_file():
        if required:
            raise InnDataUnavailable(f"缺少 {name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InnDataUnavailable(f"{name} 无法解析") from exc
    if not isinstance(payload, dict):
        raise InnDataUnavailable(f"{name} 不是对象")
    return payload


def _pick_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        direct = value.get("text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        rows = value.get("list")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    text = row.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
    return ""


def _index_i18n(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in payload.items():
        text = _pick_text(value)
        if text:
            out[str(key)] = text
    return out


def resolve_text(node: Any, i18n: dict[str, str]) -> str:
    if isinstance(node, str):
        return node.strip()
    if not isinstance(node, dict):
        return ""
    direct = node.get("text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    ident = node.get("id")
    if ident in (None, 0, "0"):
        return ""
    return i18n.get(str(ident), "")


def _index_char_names(table: dict[str, Any], i18n: dict[str, str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for key, row in table.items():
        if not isinstance(row, dict):
            continue
        char_id = ""
        for field in ("charId", "id", "char_id"):
            value = row.get(field)
            if isinstance(value, str) and value.startswith("chr_"):
                char_id = value
                break
        if not char_id and str(key).startswith("chr_"):
            char_id = str(key)
        if not char_id:
            continue
        label = resolve_text(row.get("name"), i18n) or resolve_text(row.get("engName"), i18n)
        if label:
            names[char_id] = label
    return names


def _item_names(table: dict[str, Any], i18n: dict[str, str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for key, row in table.items():
        if isinstance(row, dict):
            label = resolve_text(row.get("name"), i18n)
            if label:
                names[str(key)] = label
    return names


def _signature(root: Path) -> tuple:
    parts: list[tuple[str, int]] = []
    folder = root / "TableCfg"
    for name in (*_REQUIRED, *_OPTIONAL):
        path = folder / name
        parts.append((name, path.stat().st_mtime_ns if path.is_file() else 0))
    return tuple(parts)


def _build(root: Path) -> dict[str, Any]:
    tables = {name: _read_json(root, name, required=True) for name in _REQUIRED}
    optional = {name: _read_json(root, name, required=False) for name in _OPTIONAL}
    i18n = _index_i18n(optional["I18nTextTable_CN.json"])
    char_names = {}
    char_names.update(_index_char_names(optional["GachaCharInfoTable.json"], i18n))
    char_names.update(_index_char_names(optional["NpcTable.json"], i18n))
    char_names.update(_index_char_names(optional["CharacterTable.json"], i18n))
    return {
        "topics": tables["InnTopicTable.json"],
        "requirements": tables["InnRequirementTable.json"],
        "describes": tables["InnDescribeTable.json"],
        "dishes": tables["InnDishTable.json"],
        "drinks": tables["InnDrinkTable.json"],
        "affixes": tables["InnAffixTable.json"],
        "categories": tables["InnDishCategoryTable.json"],
        "char_skills": tables["InnCharSkillTable.json"],
        "skills": tables["InnSkillTable.json"],
        "levels": tables["InnLevelTable.json"],
        "expansions": tables["InnExpansionTable.json"],
        "const": tables["InnManagementConst.json"],
        "inn_chars": tables["InnCharTable.json"],
        "i18n": i18n,
        "item_names": _item_names(optional["ItemTable.json"], i18n),
        "char_names": char_names,
    }


def load_tables(*, root: Path | None = None) -> dict[str, Any]:
    global _cache_sig, _cache_data
    if root is not None:
        return _build(root)
    try:
        ensure_repo(REPO_ENDFIELD)
    except RepoError as exc:
        raise InnDataUnavailable(exc.message) from exc
    live = repo_dir(REPO_ENDFIELD)
    sig = _signature(live)
    if _cache_sig == sig and _cache_data is not None:
        return _cache_data
    data = _build(live)
    _cache_sig = sig
    _cache_data = data
    return data
