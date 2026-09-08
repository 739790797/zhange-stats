"""OCR 引擎、Paddle 档位、业务场景。新增场景只加这里，不要复制引擎。"""

from __future__ import annotations

from typing import Any

ENGINE_IDS = ("paddle", "easyocr", "tess")
DEFAULT_PADDLE_PROFILE = "v5_server"
PADDLE_PROFILE_IDS = ("v5_server", "v6_small", "v6_medium")
USE_CASE_IDS = ("tarkov_keys", "general")

ENGINE_LABELS = {
    "paddle": "熊猫 OCR",
    "easyocr": "EasyOCR",
    "tess": "Tesseract",
}

PADDLE_PROFILES: dict[str, dict[str, str]] = {
    "v5_server": {
        "label": "PP-OCRv5 server（中英准确，推荐）",
        "ocr_version": "PP-OCRv5",
        "model_type": "server",
    },
    "v6_small": {
        "label": "PP-OCRv6 small（体积小、更快）",
        "ocr_version": "PP-OCRv6",
        "model_type": "small",
    },
    "v6_medium": {
        "label": "PP-OCRv6 medium（多语更准、包更大）",
        "ocr_version": "PP-OCRv6",
        "model_type": "medium",
    },
}

USE_CASES: dict[str, dict[str, Any]] = {
    "tarkov_keys": {
        "label": "塔科夫钥匙箱",
        "hint": "游戏 UI 短名，多引擎交叉验证；切块与闭集匹配仍在塔科夫业务里。",
        "engines": ["paddle", "easyocr", "tess"],
    },
    "general": {
        "label": "通用识别",
        "hint": "给尚未单独配置的业务用。默认只开熊猫 OCR。",
        "engines": ["paddle"],
    },
}


def normalize_engine_id(value: str) -> str:
    raw = (value or "").strip().lower()
    if raw in ENGINE_IDS:
        return raw
    return ""


def normalize_paddle_profile(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_")
    aliases = {
        "v5": "v5_server",
        "ppocrv5": "v5_server",
        "pp-ocrv5-server": "v5_server",
        "v6": "v6_small",
        "v6small": "v6_small",
        "v6medium": "v6_medium",
    }
    raw = aliases.get(raw, raw)
    if raw in PADDLE_PROFILE_IDS:
        return raw
    return DEFAULT_PADDLE_PROFILE


def normalize_use_case(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in USE_CASE_IDS:
        return raw
    return "general"


def normalize_engine_list(values: Any, *, fallback: list[str]) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return list(fallback)
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        engine = normalize_engine_id(str(item))
        if not engine or engine in seen:
            continue
        seen.add(engine)
        out.append(engine)
    return out or list(fallback)


def paddle_rapidocr_enums(profile: str) -> dict[str, Any]:
    from rapidocr import LangDet, LangRec, ModelType, OCRVersion

    meta = PADDLE_PROFILES[normalize_paddle_profile(profile)]
    versions = {
        "PP-OCRv5": OCRVersion.PPOCRV5,
        "PP-OCRv6": OCRVersion.PPOCRV6,
    }
    types = {
        "server": ModelType.SERVER,
        "small": ModelType.SMALL,
        "medium": ModelType.MEDIUM,
    }
    return {
        "ocr_version": versions[meta["ocr_version"]],
        "model_type": types[meta["model_type"]],
        "det_lang": LangDet.CH,
        "rec_lang": LangRec.CH,
    }
