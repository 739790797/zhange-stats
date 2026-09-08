"""按系统配置挑出发给业务的 OCR 引擎。切块 / 闭集匹配仍在各业务里。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ocr import engines as ocr_engines
from app.services.ocr.config import engines_for_use_case, load_ocr_config
from app.services.ocr.models import MODELS_NOT_READY_MSG
from app.services.ocr.types import NamedEngine, OcrError


def _not_installed_message(wanted: list[str]) -> str:
    names: list[str] = []
    if "paddle" in wanted:
        names.append("rapidocr")
    if "easyocr" in wanted:
        names.append("easyocr")
    if "tess" in wanted:
        names.append("tesseract")
    if not names:
        return "服务器未安装识别引擎"
    return "服务器未安装识别引擎（" + " 或 ".join(names) + "）"


def _any_installed(wanted: list[str]) -> bool:
    for engine in wanted:
        if engine == "paddle" and ocr_engines.rapidocr_available():
            return True
        if engine == "easyocr" and ocr_engines.easyocr_available():
            return True
        if engine == "tess" and ocr_engines.tesseract_available():
            return True
    return False


def named_engines_for(
    use_case: str,
    *,
    db: Session | None = None,
    cfg: dict[str, Any] | None = None,
) -> list[NamedEngine]:
    data = cfg if isinstance(cfg, dict) else load_ocr_config(db)
    wanted = engines_for_use_case(data, use_case)
    if not wanted:
        raise OcrError("当前场景未启用任何识别引擎，请到系统管理「文字识别」勾选", 503)
    pack = ocr_engines.build_named_engines(wanted, profile=data.get("paddle_profile"))
    if pack:
        return pack
    if not _any_installed(wanted):
        raise OcrError(_not_installed_message(wanted), 503)
    raise OcrError(MODELS_NOT_READY_MSG, 503)


def engine_status(profile: str | None = None) -> list[dict[str, Any]]:
    return ocr_engines.engine_status_rows(profile)
