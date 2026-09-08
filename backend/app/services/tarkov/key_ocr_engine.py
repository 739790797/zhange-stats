"""兼容旧导入。实现见 app.services.ocr.engines。"""

from app.services.ocr.engines import (  # noqa: F401
    EasyOcrEngine,
    NamedRecognizer,
    RapidOcrEngine,
    TessOcrEngine,
    _lines_from_easyocr,
    _lines_from_result,
    build_named_engines,
    default_named_recognizers,
    easyocr_available,
    easyocr_model_dir,
    easyocr_models_ready,
    engine_status_rows,
    get_easyocr_engine,
    get_engine,
    get_rapid_engine,
    model_dir,
    ocr_available,
    paddle_models_ready,
    rapidocr_available,
    rapidocr_model_dir,
    reset_runtime,
    tesseract_available,
)
from app.services.ocr.models import MODELS_NOT_READY_MSG  # noqa: F401
