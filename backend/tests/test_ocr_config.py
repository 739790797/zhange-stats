"""OCR 系统配置：归一化、读写、场景选引擎。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.system_config import SystemConfig
from app.services.ocr import config as ocr_cfg
from app.services.ocr.catalog import normalize_paddle_profile
from tests.integrations_fakes import db_with_stored


def _sqlite() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[SystemConfig.__table__])
    return sessionmaker(bind=engine)()


def test_normalize_paddle_profile_aliases() -> None:
    assert normalize_paddle_profile("v5") == "v5_server"
    assert normalize_paddle_profile("v6medium") == "v6_medium"
    assert normalize_paddle_profile("nope") == "v5_server"


def test_load_defaults_when_missing() -> None:
    cfg = ocr_cfg.load_ocr_config(db_with_stored(None))
    assert cfg["paddle_profile"] == "v5_server"
    assert cfg["engines"]["paddle"] is True
    assert cfg["use_cases"]["tarkov_keys"] == ["paddle", "easyocr", "tess"]
    assert cfg["use_cases"]["general"] == ["paddle"]


def test_load_stored_and_drop_unknown_engines() -> None:
    cfg = ocr_cfg.load_ocr_config(
        db_with_stored(
            {
                "paddle_profile": "v6_small",
                "engines": {"paddle": False, "ghost": True},
                "use_cases": {"tarkov_keys": ["easyocr", "ghost", "easyocr"]},
            }
        )
    )
    assert cfg["paddle_profile"] == "v6_small"
    assert cfg["engines"]["paddle"] is False
    assert cfg["engines"]["easyocr"] is True
    assert cfg["use_cases"]["tarkov_keys"] == ["easyocr"]


def test_engines_for_use_case_respects_global_switch() -> None:
    cfg = {
        "paddle_profile": "v5_server",
        "engines": {"paddle": False, "easyocr": True, "tess": True},
        "use_cases": {"tarkov_keys": ["paddle", "easyocr", "tess"]},
    }
    assert ocr_cfg.engines_for_use_case(cfg, "tarkov_keys") == ["easyocr", "tess"]
    assert ocr_cfg.engines_for_use_case(cfg, "general") == []


def test_save_roundtrip() -> None:
    db = _sqlite()
    try:
        saved = ocr_cfg.save_ocr_config(
            db,
            {
                "paddle_profile": "v6_medium",
                "engines": {"paddle": True, "easyocr": False, "tess": True},
                "use_cases": {"general": ["tess", "paddle"]},
            },
        )
        loaded = ocr_cfg.load_ocr_config(db)
        assert saved == loaded
        assert loaded["paddle_profile"] == "v6_medium"
        assert loaded["engines"]["easyocr"] is False
        assert loaded["use_cases"]["general"] == ["tess", "paddle"]
    finally:
        db.close()


def test_scheduler_maps_legacy_key_ocr_job() -> None:
    from app.services.scheduler_config import load_scheduler_config

    db = db_with_stored(
        {"tarkov_key_ocr_sync": {"enabled": False, "hour": 7, "minute": 22}}
    )
    cfg = load_scheduler_config(db)
    assert cfg["ocr_model_sync"]["enabled"] is False
    assert cfg["ocr_model_sync"]["hour"] == 7
    assert cfg["ocr_model_sync"]["minute"] == 22


def test_ocr_settings_openapi_exists() -> None:
    from app.main import app

    schema = app.openapi()
    path = (schema.get("paths") or {}).get("/api/settings/ocr") or {}
    assert path.get("get") is not None
    assert path.get("put") is not None


def test_public_shape_includes_catalog() -> None:
    out = ocr_cfg.public_ocr_config(ocr_cfg.default_ocr_config(), engine_status=[])
    assert out["paddle_profile"] == "v5_server"
    ids = {row["id"] for row in out["paddle_profiles"]}
    assert ids == {"v5_server", "v6_small", "v6_medium"}
    cases = {row["id"] for row in out["use_case_meta"]}
    assert cases == {"tarkov_keys", "general"}
    assert "paddle" in out["engine_labels"]
