"""兼容旧导入。实现见 app.services.ocr.models。"""

from app.services.ocr.models import (  # noqa: F401
    JOB_ID,
    LEGACY_REVISION_NAME,
    MODELS_NOT_READY_MSG,
    REVISION_NAME,
    WeightSpec,
    all_weight_specs,
    compute_download_percent,
    download_weight,
    easyocr_model_dir,
    easyocr_models_ready,
    easyocr_weight_specs,
    expected_revision,
    format_sync_message,
    model_sync_job,
    models_ready,
    paddle_models_ready,
    paddle_weight_specs,
    rapidocr_model_dir,
    read_local_revision,
    revision_path,
    should_refresh,
    sync_key_ocr_models,
    sync_ocr_models,
)
from app.services.ocr.models import _safe_zip_member  # noqa: F401
