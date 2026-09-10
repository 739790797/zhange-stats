"""任务配置功能树：战鸽数据合并文字/公式模型，兼容旧 tavern / ocr 开关。"""

from __future__ import annotations

import pytest

from app.core.file_config import write_json
from app.services import platform_features as pf


def _store(features: dict[str, bool]) -> None:
    write_json("jobs", {"features": features})
    pf.invalidate_feature_cache()


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    pf.invalidate_feature_cache()
    yield
    pf.invalidate_feature_cache()


def test_zhange_groups_ocr_and_texteller_jobs() -> None:
    roots = {str(node["id"]): node for node in pf.FEATURE_TREE}
    assert "tavern" not in roots
    assert "ocr" not in roots
    zhange = roots["zhange"]
    assert zhange["name"] == "战鸽数据"
    children = zhange["children"]
    assert [c["id"] for c in children] == [
        "zhange.ocr_model",
        "zhange.texteller_model",
    ]
    assert [c["name"] for c in children] == ["文字识别模型", "公式识别模型"]
    assert pf.JOB_FEATURE_IDS["ocr_model_sync"] == "zhange.ocr_model"
    assert pf.JOB_FEATURE_IDS["texteller_model_sync"] == "zhange.texteller_model"


def test_tavern_alias_follows_zhange() -> None:
    flags = pf.default_features()
    assert pf.is_feature_enabled_from_flags(flags, "tavern") is True
    flags["zhange"] = False
    assert pf.is_feature_enabled_from_flags(flags, "tavern") is False
    assert pf.is_feature_enabled_from_flags(flags, "zhange.ocr_model") is False


def test_legacy_tavern_and_ocr_flags_migrate() -> None:
    _store(
        {
            "tavern": False,
            "tavern.texteller_sync": True,
            "ocr": True,
            "ocr.model_sync": False,
        }
    )
    loaded = pf.load_feature_flags()
    assert loaded["zhange"] is False
    assert loaded["zhange.texteller_model"] is True
    assert loaded["zhange.ocr_model"] is False
    assert pf.effective_features(None)["tavern"] is False  # type: ignore[arg-type]


def test_new_zhange_keys_win_over_legacy() -> None:
    _store(
        {
            "tavern": False,
            "zhange": True,
            "ocr.model_sync": False,
            "zhange.ocr_model": True,
        }
    )
    loaded = pf.load_feature_flags()
    assert loaded["zhange"] is True
    assert loaded["zhange.ocr_model"] is True
