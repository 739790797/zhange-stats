"""OCR 引擎、Paddle 档位、业务场景。新增场景只加这里，不要复制引擎。"""

from __future__ import annotations

from typing import Any

from app.services.ocr.paddle_profiles import (
    DEFAULT_PADDLE_PROFILE,
    list_paddle_profiles,
    normalize_paddle_profile,
    paddle_rapidocr_enums,
)

ENGINE_IDS = ("paddle", "easyocr")
USE_CASE_IDS = ("tarkov_keys", "tarkov_raid_prep", "general")

ENGINE_LABELS = {
    "paddle": "熊猫 OCR",
    "easyocr": "EasyOCR",
}

ENGINE_HINTS = {
    "paddle": "RapidOCR / Paddle ONNX。v5 与 v6 同族，交叉验证不能当两票。",
    "easyocr": "CRAFT + CRNN，中英。CPU 常驻大约 1–2GB。",
}

EASYOCR_PROFILES = (
    {"id": "ch_sim_en", "label": "ch_sim+en"},
)

USE_CASES: dict[str, dict[str, Any]] = {
    "tarkov_keys": {
        "label": "塔科夫钥匙箱",
        "hint": "游戏 UI 短名。切块与闭集匹配仍在塔科夫业务里。",
        "engines": ["paddle", "easyocr"],
        "cross_check": True,
    },
    "tarkov_raid_prep": {
        "label": "塔科夫局前任务",
        "hint": "任务页截图。列表裁切与闭集匹配仍在塔科夫业务里。默认只开熊猫 OCR。",
        "engines": ["paddle"],
        "cross_check": False,
    },
    "general": {
        "label": "通用识别",
        "hint": "给尚未单独配置的业务用。",
        "engines": ["paddle"],
        "cross_check": False,
    },
}


def engine_has_profiles(engine_id: str) -> bool:
    return engine_id == "paddle"


def normalize_engine_id(value: str) -> str:
    raw = (value or "").strip().lower()
    if raw in ENGINE_IDS:
        return raw
    return ""


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
        if engine and engine not in seen:
            seen.add(engine)
            out.append(engine)
    return out or list(fallback)


__all__ = [
    "DEFAULT_PADDLE_PROFILE",
    "EASYOCR_PROFILES",
    "ENGINE_HINTS",
    "ENGINE_IDS",
    "ENGINE_LABELS",
    "USE_CASES",
    "USE_CASE_IDS",
    "engine_has_profiles",
    "list_paddle_profiles",
    "normalize_engine_id",
    "normalize_engine_list",
    "normalize_paddle_profile",
    "normalize_use_case",
    "paddle_rapidocr_enums",
]
