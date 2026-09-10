"""OCR 系统配置：归一化、读写、场景选引擎。"""

import pytest

from app.core.file_config import write_json
from app.services.ocr import config as ocr_cfg
from app.services.ocr.catalog import normalize_paddle_profile


def test_normalize_paddle_profile_aliases() -> None:
    assert normalize_paddle_profile("v5") == "v5_server"
    assert normalize_paddle_profile("v6medium") == "v6_medium"
    assert normalize_paddle_profile("nope") == "v5_server"


def test_load_defaults_when_missing() -> None:
    cfg = ocr_cfg.load_ocr_config()
    assert cfg["paddle_profile"] == "v5_server"
    assert cfg["engines"]["paddle"] is True
    assert "tess" not in cfg["engines"]
    assert cfg["use_cases"]["tarkov_keys"] == {
        "engines": ["paddle", "easyocr"],
        "cross_check": True,
    }
    assert cfg["use_cases"]["tarkov_raid_prep"] == {
        "engines": ["paddle"],
        "cross_check": False,
    }
    assert cfg["use_cases"]["general"] == {
        "engines": ["paddle"],
        "cross_check": False,
    }


def test_load_legacy_list_and_drop_unknown_engines() -> None:
    write_json(
        "ocr",
        {
            "paddle_profile": "v6_small",
            "engines": {"paddle": False, "ghost": True, "tess": True},
            "use_cases": {"tarkov_keys": ["easyocr", "ghost", "tess", "easyocr"]},
        },
    )
    cfg = ocr_cfg.load_ocr_config()
    assert cfg["paddle_profile"] == "v6_small"
    assert cfg["engines"]["paddle"] is False
    assert cfg["engines"]["easyocr"] is True
    assert "tess" not in cfg["engines"]
    assert cfg["use_cases"]["tarkov_keys"]["engines"] == ["easyocr"]
    assert cfg["use_cases"]["tarkov_keys"]["cross_check"] is True


def test_engines_for_use_case_respects_global_switch() -> None:
    cfg = {
        "paddle_profile": "v5_server",
        "engines": {"paddle": False, "easyocr": True},
        "use_cases": {
            "tarkov_keys": {"engines": ["paddle", "easyocr"], "cross_check": True}
        },
    }
    assert ocr_cfg.engines_for_use_case(cfg, "tarkov_keys") == ["easyocr"]
    assert ocr_cfg.engines_for_use_case(cfg, "general") == []


def test_save_rejects_cross_check_without_two_families() -> None:
    with pytest.raises(ocr_cfg.OcrConfigError, match="多端校验"):
        ocr_cfg.save_ocr_config(
            None,
            {
                "paddle_profile": "v5_server",
                "engines": {"paddle": True, "easyocr": False},
                "use_cases": {
                    "tarkov_keys": {
                        "engines": ["paddle", "easyocr"],
                        "cross_check": True,
                    },
                    "general": {"engines": ["paddle"], "cross_check": False},
                },
            },
        )


def test_save_roundtrip() -> None:
    saved = ocr_cfg.save_ocr_config(
        None,
        {
            "paddle_profile": "v6_medium",
            "engines": {"paddle": True, "easyocr": False},
            "use_cases": {
                "tarkov_keys": {
                    "engines": ["paddle"],
                    "cross_check": False,
                },
                "general": {"engines": ["paddle"], "cross_check": False},
            },
        },
    )
    loaded = ocr_cfg.load_ocr_config()
    assert saved == loaded
    assert loaded["paddle_profile"] == "v6_medium"
    assert loaded["engines"]["easyocr"] is False
    assert loaded["use_cases"]["tarkov_keys"]["cross_check"] is False
    assert loaded["use_cases"]["tarkov_raid_prep"] == {
        "engines": ["paddle"],
        "cross_check": False,
    }
    assert loaded["use_cases"]["general"]["engines"] == ["paddle"]


def test_scheduler_maps_legacy_key_ocr_job() -> None:
    from app.services.scheduler_config import load_scheduler_config

    write_json(
        "jobs",
        {"tarkov_key_ocr_sync": {"enabled": False, "hour": 7, "minute": 22}},
    )
    cfg = load_scheduler_config()
    assert cfg["ocr_model_sync"]["enabled"] is False
    assert cfg["ocr_model_sync"]["hour"] == 7
    assert cfg["ocr_model_sync"]["minute"] == 22


def test_ocr_settings_openapi_exists() -> None:
    from app.main import app

    schema = app.openapi()
    path = (schema.get("paths") or {}).get("/api/settings/ocr") or {}
    assert path.get("get") is not None
    assert path.get("put") is not None
    components = (schema.get("components") or {}).get("schemas") or {}
    assert "OcrUseCaseSettings" in components
    assert "OcrEngineMetaOut" in components


def test_public_shape_includes_catalog() -> None:
    out = ocr_cfg.public_ocr_config(ocr_cfg.default_ocr_config(), engine_status=[])
    assert out["paddle_profile"] == "v5_server"
    ids = {row["id"] for row in out["paddle_profiles"]}
    assert "v5_server" in ids
    assert "v6_small" in ids
    assert "v6_medium" in ids
    assert all(row.get("label") for row in out["paddle_profiles"])
    cases = {row["id"] for row in out["use_case_meta"]}
    assert cases == {"tarkov_keys", "tarkov_raid_prep", "general"}
    assert "paddle" in out["engine_labels"]
    assert "tess" not in out["engine_labels"]
    meta_ids = [row["id"] for row in out["engine_meta"]]
    assert meta_ids == ["paddle", "easyocr"]
    assert out["easyocr_profiles"][0]["id"] == "ch_sim_en"
    assert out["use_cases"]["tarkov_keys"]["cross_check"] is True
