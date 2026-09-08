"""OCR 系统配置：system_configs.key = ocr。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.services.ocr.catalog import (
    DEFAULT_PADDLE_PROFILE,
    ENGINE_IDS,
    ENGINE_LABELS,
    PADDLE_PROFILES,
    USE_CASES,
    normalize_engine_list,
    normalize_paddle_profile,
    normalize_use_case,
)

OCR_CONFIG_KEY = "ocr"


def default_ocr_config() -> dict[str, Any]:
    return {
        "paddle_profile": DEFAULT_PADDLE_PROFILE,
        "engines": {engine: True for engine in ENGINE_IDS},
        "use_cases": {
            key: list(meta["engines"]) for key, meta in USE_CASES.items()
        },
    }


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
                use_cases[key] = normalize_engine_list(
                    use_cases_in.get(key),
                    fallback=list(meta["engines"]),
                )
    return {
        "paddle_profile": normalize_paddle_profile(data.get("paddle_profile")),
        "engines": engines,
        "use_cases": use_cases,
    }


def load_ocr_config(db: Session | None) -> dict[str, Any]:
    if db is None:
        return default_ocr_config()
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == OCR_CONFIG_KEY)
        .first()
    )
    if not row:
        return default_ocr_config()
    try:
        stored = json.loads(row.value or "{}")
    except json.JSONDecodeError:
        return default_ocr_config()
    if not isinstance(stored, dict):
        return default_ocr_config()
    return _normalize(stored)


def save_ocr_config(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    data = _normalize(payload)
    raw = json.dumps(data, ensure_ascii=False)
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == OCR_CONFIG_KEY)
        .first()
    )
    if row:
        row.value = raw
    else:
        db.add(SystemConfig(key=OCR_CONFIG_KEY, value=raw))
    db.commit()
    from app.services.ocr.engines import reset_runtime

    reset_runtime()
    return data


def engines_for_use_case(cfg: dict[str, Any], use_case: str) -> list[str]:
    data = _normalize(cfg)
    key = normalize_use_case(use_case)
    wanted = list(data["use_cases"].get(key) or USE_CASES[key]["engines"])
    enabled = data["engines"]
    return [engine for engine in wanted if enabled.get(engine, True)]


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
            {"id": key, "label": meta["label"], "hint": ""}
            for key, meta in PADDLE_PROFILES.items()
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
