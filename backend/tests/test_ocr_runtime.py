"""OCR runtime：按配置挑引擎，未安装 / 未就绪文案分开。"""

import pytest

from app.services.ocr import engines as engine_svc
from app.services.ocr.runtime import named_engines_for
from app.services.ocr.types import OcrError


def test_named_engines_skip_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_svc, "rapidocr_available", lambda: True)
    monkeypatch.setattr(engine_svc, "easyocr_available", lambda: True)
    monkeypatch.setattr(engine_svc, "paddle_models_ready", lambda *a, **k: True)
    monkeypatch.setattr(engine_svc, "easyocr_models_ready", lambda *a, **k: True)
    pack = named_engines_for(
        "tarkov_keys",
        cfg={
            "paddle_profile": "v5_server",
            "engines": {"paddle": True, "easyocr": False},
            "use_cases": {
                "tarkov_keys": {
                    "engines": ["paddle", "easyocr"],
                    "cross_check": False,
                }
            },
        },
    )
    assert [item.name for item in pack] == ["paddle"]


def test_named_engines_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_svc, "rapidocr_available", lambda: False)
    monkeypatch.setattr(engine_svc, "easyocr_available", lambda: False)
    monkeypatch.setattr(engine_svc, "paddle_models_ready", lambda *a, **k: False)
    monkeypatch.setattr(engine_svc, "easyocr_models_ready", lambda *a, **k: False)
    with pytest.raises(OcrError) as exc:
        named_engines_for("tarkov_keys")
    assert exc.value.status_code == 503
    assert "未安装" in exc.value.message
    assert "tesseract" not in exc.value.message


def test_named_engines_models_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_svc, "rapidocr_available", lambda: True)
    monkeypatch.setattr(engine_svc, "easyocr_available", lambda: True)
    monkeypatch.setattr(engine_svc, "paddle_models_ready", lambda *a, **k: False)
    monkeypatch.setattr(engine_svc, "easyocr_models_ready", lambda *a, **k: False)
    with pytest.raises(OcrError) as exc:
        named_engines_for("tarkov_keys")
    assert exc.value.status_code == 503
    assert "文字识别模型" in exc.value.message
    assert "文字识别" in exc.value.message


def test_named_engines_empty_use_case() -> None:
    with pytest.raises(OcrError) as exc:
        named_engines_for(
            "general",
            cfg={
                "paddle_profile": "v5_server",
                "engines": {"paddle": False, "easyocr": False},
                "use_cases": {
                    "general": {"engines": ["paddle"], "cross_check": False}
                },
            },
        )
    assert exc.value.status_code == 503
    assert "文字识别" in exc.value.message
