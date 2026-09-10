"""OCR 系统配置：config/ocr.json。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.file_config import read_json, write_json
from app.services.ocr.catalog import (
    EASYOCR_PROFILES,
    ENGINE_HINTS,
    ENGINE_IDS,
    ENGINE_LABELS,
    USE_CASES,
    engine_has_profiles,
    normalize_engine_list,
    normalize_use_case,
)
from app.services.ocr.paddle_profiles import (
    DEFAULT_PADDLE_PROFILE,
    list_paddle_profiles,
    normalize_paddle_profile,
)

OCR_CONFIG_KEY = "ocr"


class OcrConfigError(ValueError):
    """保存文字识别配置时的用户可见错误。"""


def default_ocr_config() -> dict[str, Any]:
    return {
        "paddle_profile": DEFAULT_PADDLE_PROFILE,
        "engines": {engine: True for engine in ENGINE_IDS},
        "use_cases": {
            key: {
                "engines": list(meta["engines"]),
                "cross_check": bool(meta["cross_check"]),
            }
            for key, meta in USE_CASES.items()
        },
    }


def _normalize_use_case_row(raw: Any, meta: dict[str, Any]) -> dict[str, Any]:
    fallback = list(meta["engines"])
    default_cc = bool(meta["cross_check"])
    if isinstance(raw, (list, tuple)):
        return {
            "engines": normalize_engine_list(raw, fallback=fallback),
            "cross_check": default_cc,
        }
    if isinstance(raw, dict):
        engines_raw = raw.get("engines")
        if engines_raw is None and isinstance(raw.get("engine"), (list, tuple)):
            engines_raw = raw.get("engine")
        cc = raw.get("cross_check")
        return {
            "engines": normalize_engine_list(engines_raw, fallback=fallback),
            "cross_check": default_cc if cc is None else bool(cc),
        }
    return {"engines": fallback, "cross_check": default_cc}


def _normalize(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_ocr_config()
    data = raw if isinstance(raw, dict) else {}
    engines_in = data.get("engines")
    engines = dict(base["engines"])
    if isinstance(engines_in, dict):
        for engine in ENGINE_IDS:
            if engine in engines_in:
                engines[engine] = bool(engines_in.get(engine))
    use_cases_in = data.get("use_cases")
    use_cases = dict(base["use_cases"])
    if isinstance(use_cases_in, dict):
        for key, meta in USE_CASES.items():
            if key in use_cases_in:
                use_cases[key] = _normalize_use_case_row(use_cases_in.get(key), meta)
    return {
        "paddle_profile": normalize_paddle_profile(data.get("paddle_profile")),
        "engines": engines,
        "use_cases": use_cases,
    }


def validate_ocr_config(data: dict[str, Any]) -> None:
    normalized = _normalize(data)
    enabled = normalized["engines"]
    for key, meta in USE_CASES.items():
        row = normalized["use_cases"][key]
        if not row["cross_check"]:
            continue
        active = [engine for engine in row["engines"] if enabled.get(engine, True)]
        if len(active) < 2:
            raise OcrConfigError(
                f"{meta['label']} 开启了多端校验，请至少勾选两个不同模型族"
            )


def load_ocr_config(_db: Session | None = None) -> dict[str, Any]:
    stored = read_json("ocr")
    if not stored:
        return default_ocr_config()
    return _normalize(stored)


def save_ocr_config(_db: Session | None, payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize(payload)
    validate_ocr_config(data)
    write_json("ocr", data)
    from app.services.ocr.engines import reset_runtime

    reset_runtime()
    return data


def engines_for_use_case(cfg: dict[str, Any], use_case: str) -> list[str]:
    data = _normalize(cfg)
    key = normalize_use_case(use_case)
    row = data["use_cases"].get(key) or USE_CASES[key]
    wanted = list(row.get("engines") or USE_CASES[key]["engines"])
    enabled = data["engines"]
    return [engine for engine in wanted if enabled.get(engine, True)]


def use_case_cross_check(cfg: dict[str, Any] | None, use_case: str) -> bool:
    data = _normalize(cfg if isinstance(cfg, dict) else None)
    key = normalize_use_case(use_case)
    row = data["use_cases"].get(key) or {}
    if "cross_check" in row:
        return bool(row["cross_check"])
    return bool(USE_CASES[key]["cross_check"])


def public_ocr_config(
    cfg: dict[str, Any],
    *,
    engine_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = _normalize(cfg)
    return {
        "paddle_profile": data["paddle_profile"],
        "engines": data["engines"],
        "use_cases": data["use_cases"],
        "engine_status": engine_status or [],
        "paddle_profiles": [
            {"id": row.id, "label": row.label, "hint": row.group}
            for row in list_paddle_profiles()
        ],
        "easyocr_profiles": [dict(row) for row in EASYOCR_PROFILES],
        "engine_meta": [
            {
                "id": engine,
                "label": ENGINE_LABELS[engine],
                "hint": ENGINE_HINTS[engine],
                "has_profiles": engine_has_profiles(engine),
            }
            for engine in ENGINE_IDS
        ],
        "use_case_meta": [
            {
                "id": key,
                "label": meta["label"],
                "hint": meta["hint"],
            }
            for key, meta in USE_CASES.items()
        ],
        "engine_labels": dict(ENGINE_LABELS),
    }
