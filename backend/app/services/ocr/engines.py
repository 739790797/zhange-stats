"""共享 OCR 引擎：熊猫 OCR（RapidOCR / Paddle）+ EasyOCR。

权重由任务配置「文字识别模型」落到 var/data/{rapidocr,easyocr}。
识别路径不现场下载。非主引擎失败返回空行，不拖垮整次识别。
Paddle 档位由系统配置决定；同族 v5/v6 不能当两票。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from typing import Any

from PIL import Image

from app.services.ocr.boxes import box_to_xywh
from app.services.ocr.catalog import ENGINE_LABELS, normalize_paddle_profile, paddle_rapidocr_enums
from app.services.ocr.models import (
    MODELS_NOT_READY_MSG,
    easyocr_model_dir,
    easyocr_models_ready,
    paddle_models_ready,
    rapidocr_model_dir,
)
from app.services.ocr.types import NamedEngine, OcrError, OcrLine

logger = logging.getLogger("zhange.ocr")

NamedRecognizer = NamedEngine

_RAPID_LOCK = threading.Lock()
_EASY_LOCK = threading.Lock()
_RAPID: Any | None = None
_RAPID_PROFILE: str | None = None
_EASY: Any | None = None


def rapidocr_available() -> bool:
    try:
        import rapidocr  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


def easyocr_available() -> bool:
    try:
        import easyocr  # noqa: F401
        import numpy  # noqa: F401
    except ImportError:
        return False
    return True


def ocr_available() -> bool:
    return rapidocr_available() or easyocr_available()


def model_dir():
    return rapidocr_model_dir()


def reset_runtime() -> None:
    global _RAPID, _RAPID_PROFILE, _EASY
    with _RAPID_LOCK:
        _RAPID = None
        _RAPID_PROFILE = None
    with _EASY_LOCK:
        _EASY = None


def build_named_engines(
    engine_ids: Sequence[str],
    profile: str | None = None,
) -> list[NamedEngine]:
    chosen = normalize_paddle_profile(profile)
    pack: list[NamedEngine] = []
    for engine in engine_ids:
        if engine == "paddle":
            if rapidocr_available() and paddle_models_ready(profile=chosen):
                pack.append(NamedEngine(name="paddle", engine=RapidOcrEngine(chosen)))
        elif engine == "easyocr":
            if easyocr_available() and easyocr_models_ready():
                pack.append(NamedEngine(name="easyocr", engine=EasyOcrEngine()))
    return pack


def default_named_recognizers() -> list[NamedEngine]:
    from app.services.ocr.runtime import named_engines_for

    return named_engines_for("tarkov_keys")


def _lines_from_result(result: Any) -> list[OcrLine]:
    if result is None:
        return []
    txts = getattr(result, "txts", None) or ()
    boxes = getattr(result, "boxes", None)
    out: list[OcrLine] = []
    for index, raw in enumerate(txts):
        text = str(raw).strip()
        if not text:
            continue
        xywh = None
        if boxes is not None:
            try:
                xywh = box_to_xywh(boxes[index])
            except (IndexError, TypeError, ValueError):
                xywh = None
        if xywh:
            out.append(OcrLine(text=text, x=xywh[0], y=xywh[1], w=xywh[2], h=xywh[3]))
        else:
            out.append(OcrLine(text=text))
    return out


def _lines_from_easyocr(rows: Any) -> list[OcrLine]:
    out: list[OcrLine] = []
    for row in rows or []:
        box = None
        text = ""
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            box = row[0]
            text = str(row[1] or "").strip()
        else:
            continue
        if not text:
            continue
        xywh = box_to_xywh(box)
        if xywh:
            out.append(OcrLine(text=text, x=xywh[0], y=xywh[1], w=xywh[2], h=xywh[3]))
        else:
            out.append(OcrLine(text=text))
    return out


def _easyocr_gpu() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _rapidocr_params(folder, profile: str) -> dict[str, Any]:
    enums = paddle_rapidocr_enums(profile)
    return {
        "Global.log_level": "error",
        "Global.model_root_dir": str(folder),
        "Global.use_cls": False,
        "Det.ocr_version": enums["ocr_version"],
        "Det.model_type": enums["model_type"],
        "Det.lang_type": enums["det_lang"],
        "Rec.ocr_version": enums["ocr_version"],
        "Rec.model_type": enums["model_type"],
        "Rec.lang_type": enums["rec_lang"],
    }


def _build_rapid(profile: str) -> Any:
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise OcrError("服务器未安装识别引擎（rapidocr）", 503) from exc
    if not paddle_models_ready(profile=profile):
        raise OcrError(MODELS_NOT_READY_MSG, 503)
    folder = rapidocr_model_dir()
    folder.mkdir(parents=True, exist_ok=True)
    try:
        return RapidOCR(params=_rapidocr_params(folder, profile))
    except Exception as exc:  # noqa: BLE001
        logger.exception("rapidocr init failed")
        raise OcrError("识别引擎加载失败，请稍后重试", 503) from exc


def get_rapid_engine(profile: str | None = None) -> Any:
    global _RAPID, _RAPID_PROFILE
    chosen = normalize_paddle_profile(profile)
    if _RAPID is not None and _RAPID_PROFILE == chosen:
        return _RAPID
    with _RAPID_LOCK:
        if _RAPID is None or _RAPID_PROFILE != chosen:
            _RAPID = _build_rapid(chosen)
            _RAPID_PROFILE = chosen
        return _RAPID


def get_engine() -> Any:
    return get_rapid_engine()


def _build_easyocr() -> Any:
    try:
        import easyocr
    except ImportError as exc:
        raise OcrError("服务器未安装识别引擎（easyocr）", 503) from exc
    folder = easyocr_model_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "user_network").mkdir(parents=True, exist_ok=True)
    try:
        kwargs = {
            "gpu": _easyocr_gpu(),
            "model_storage_directory": str(folder),
            "user_network_directory": str(folder / "user_network"),
            "download_enabled": False,
            "verbose": False,
            "quantize": False,
        }
        try:
            return easyocr.Reader(["ch_sim", "en"], **kwargs)
        except TypeError:
            kwargs.pop("quantize", None)
            kwargs.pop("verbose", None)
            return easyocr.Reader(["ch_sim", "en"], **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("easyocr init failed")
        raise OcrError("EasyOCR 加载失败，请稍后重试", 503) from exc


def get_easyocr_engine() -> Any:
    global _EASY
    if _EASY is not None:
        return _EASY
    if not easyocr_models_ready():
        raise OcrError(MODELS_NOT_READY_MSG, 503)
    with _EASY_LOCK:
        if _EASY is None:
            _EASY = _build_easyocr()
        return _EASY


class RapidOcrEngine:
    """Paddle RapidOCR。档位由系统配置决定（默认 PP-OCRv5 server）。"""

    def __init__(self, profile: str | None = None) -> None:
        self.profile = normalize_paddle_profile(profile)

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        try:
            import numpy as np
        except ImportError as exc:
            raise OcrError("服务器未安装识别引擎（numpy）", 503) from exc
        engine = get_rapid_engine(self.profile)
        arr = np.asarray(image.convert("RGB"))
        with _RAPID_LOCK:
            try:
                result = engine(arr, use_cls=False)
            except Exception as exc:  # noqa: BLE001
                logger.exception("rapidocr recognize failed")
                raise OcrError("识别失败，请换一张更清晰的图") from exc
        return _lines_from_result(result)


class EasyOcrEngine:
    """CRAFT + CRNN，中英混合；低频场景关掉量化、用 beam search。"""

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        try:
            import numpy as np
        except ImportError:
            logger.exception("easyocr numpy missing")
            return []
        try:
            reader = get_easyocr_engine()
        except OcrError:
            if not rapidocr_available():
                raise
            logger.exception("easyocr unavailable")
            return []
        arr = np.asarray(image.convert("RGB"))
        with _EASY_LOCK:
            try:
                rows = reader.readtext(
                    arr,
                    detail=1,
                    paragraph=False,
                    decoder="beamsearch",
                    beamWidth=5,
                )
            except TypeError:
                try:
                    rows = reader.readtext(arr, detail=1, paragraph=False)
                except Exception:
                    logger.exception("easyocr recognize failed")
                    return []
            except Exception:
                logger.exception("easyocr recognize failed")
                return []
        return _lines_from_easyocr(rows)


def engine_status_rows(profile: str | None = None) -> list[dict[str, Any]]:
    chosen = normalize_paddle_profile(profile)
    return [
        {
            "id": "paddle",
            "label": ENGINE_LABELS["paddle"],
            "installed": rapidocr_available(),
            "models_ready": paddle_models_ready(profile=chosen),
        },
        {
            "id": "easyocr",
            "label": ENGINE_LABELS["easyocr"],
            "installed": easyocr_available(),
            "models_ready": easyocr_models_ready(),
        },
    ]
