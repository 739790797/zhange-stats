"""钥匙 OCR 权重同步：版本判断、缺模型、不打真实下载。"""

from pathlib import Path

import pytest

from app.services.ocr import engines as engine_svc
from app.services.ocr import models as models_svc
from app.services.ocr.models import WeightSpec
from app.services.ocr.types import OcrError


def test_should_refresh() -> None:
    assert models_svc.should_refresh("aaa", "bbb") is True
    assert models_svc.should_refresh("aaa", "aaa") is False
    assert models_svc.should_refresh("", "bbb") is True
    assert models_svc.should_refresh("aaa", "") is False


def test_format_sync_message() -> None:
    assert models_svc.format_sync_message("check") == "正在核对识别模型版本…"
    assert models_svc.format_sync_message("skip") == "本地识别模型已是最新，无需下载"
    assert models_svc.format_sync_message(
        "download", file="ch_PP-OCRv5_det_server.onnx", index=1, total=2
    ) == "正在下载 ch_PP-OCRv5_det_server.onnx（1/2）"


def test_compute_download_percent() -> None:
    assert models_svc.compute_download_percent(
        done_bytes=50,
        current_bytes=50,
        total_bytes=200,
        files_done=0,
        files_total=2,
    ) == 50


def _spec(name: str, folder: str = "rapidocr") -> WeightSpec:
    return WeightSpec(name=name, url=f"https://example.test/{name}", folder=folder)


def test_sync_downloads_when_revision_changes(tmp_path: Path) -> None:
    specs = [_spec("det.onnx"), _spec("rec.onnx")]
    pulled: list[str] = []

    def fetch() -> str:
        return "newsha"

    def download(spec: WeightSpec, folder: Path) -> None:
        pulled.append(spec.name)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / spec.name).write_bytes(b"x")

    (tmp_path / models_svc.REVISION_NAME).write_text("old", encoding="utf-8")
    out = models_svc.sync_key_ocr_models(
        dest=tmp_path,
        fetch_remote=fetch,
        download=download,
        specs=specs,
    )
    assert out["updated"] is True
    assert out["revision"] == "newsha"
    assert pulled == ["det.onnx", "rec.onnx"]
    assert models_svc.read_local_revision(tmp_path) == "newsha"


def test_read_legacy_revision(tmp_path: Path) -> None:
    (tmp_path / models_svc.LEGACY_REVISION_NAME).write_text("oldrev", encoding="utf-8")
    assert models_svc.read_local_revision(tmp_path) == "oldrev"


def test_sync_skips_when_current(tmp_path: Path) -> None:
    specs = [_spec("det.onnx")]
    folder = tmp_path / "rapidocr"
    folder.mkdir()
    (folder / "det.onnx").write_bytes(b"x")
    (tmp_path / models_svc.REVISION_NAME).write_text("same", encoding="utf-8")

    def fetch() -> str:
        return "same"

    def download(spec: WeightSpec, folder: Path) -> None:
        raise AssertionError("should not download")

    out = models_svc.sync_key_ocr_models(
        dest=tmp_path,
        fetch_remote=fetch,
        download=download,
        specs=specs,
    )
    assert out == {"updated": False, "revision": "same"}


def test_default_recognizers_require_ready_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_svc, "rapidocr_available", lambda: True)
    monkeypatch.setattr(engine_svc, "easyocr_available", lambda: True)
    monkeypatch.setattr(engine_svc, "paddle_models_ready", lambda *a, **k: False)
    monkeypatch.setattr(engine_svc, "easyocr_models_ready", lambda *a, **k: False)
    with pytest.raises(OcrError) as exc:
        engine_svc.default_named_recognizers()
    assert exc.value.status_code == 503
    assert "文字识别模型" in exc.value.message


def test_default_recognizers_require_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine_svc, "rapidocr_available", lambda: False)
    monkeypatch.setattr(engine_svc, "easyocr_available", lambda: False)
    monkeypatch.setattr(engine_svc, "paddle_models_ready", lambda *a, **k: False)
    monkeypatch.setattr(engine_svc, "easyocr_models_ready", lambda *a, **k: False)
    with pytest.raises(OcrError) as exc:
        engine_svc.default_named_recognizers()
    assert exc.value.status_code == 503
    assert "未安装" in exc.value.message


def test_paddle_profile_is_v5_server() -> None:
    specs = models_svc.paddle_weight_specs()
    names = {item.name for item in specs}
    assert "ch_PP-OCRv5_det_server.onnx" in names
    assert "ch_PP-OCRv5_rec_server.onnx" in names


def test_easyocr_weights_cover_chinese_and_english() -> None:
    specs = models_svc.easyocr_weight_specs()
    names = {item.name for item in specs}
    assert "craft_mlt_25k.pth" in names
    assert "zh_sim_g2.pth" in names
    assert "english_g2.pth" in names


def test_job_id_is_wired() -> None:
    from app.api.jobs.catalog import JOB_CATALOG
    from app.services.platform_features import JOB_FEATURE_IDS
    from app.services.scheduler_config import JOB_IDS
    from app.services.scheduler_runtime import SYSTEM_CRON_HANDLERS

    assert models_svc.JOB_ID == "ocr_model_sync"
    assert models_svc.JOB_ID in JOB_IDS
    assert any(item["id"] == models_svc.JOB_ID for item in JOB_CATALOG)
    assert JOB_FEATURE_IDS[models_svc.JOB_ID] == "zhange.ocr_model"
    assert models_svc.JOB_ID in SYSTEM_CRON_HANDLERS
    assert set(JOB_IDS) == {str(item["id"]) for item in JOB_CATALOG}


def test_sync_allows_one_family_to_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [_spec("det.onnx"), _spec("craft.pth", folder="easyocr")]
    (tmp_path / "rapidocr").mkdir()
    (tmp_path / "rapidocr" / "det.onnx").write_bytes(b"x")

    def boom(spec: WeightSpec, dest: Path, **_kwargs) -> None:
        if spec.folder == "easyocr":
            raise OcrError("github blocked", 502)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / spec.name).write_bytes(b"x")

    monkeypatch.setattr(models_svc, "download_weight", boom)
    out = models_svc.sync_key_ocr_models(
        dest=tmp_path,
        fetch_remote=lambda: "rev",
        specs=specs,
    )
    assert out["updated"] is True
    assert (tmp_path / "rapidocr" / "det.onnx").is_file()
    assert models_svc.read_local_revision(tmp_path) == ""


def test_sync_redownloads_when_checksum_fails(tmp_path: Path) -> None:
    spec = WeightSpec(
        name="det.onnx",
        url="https://example.test/det.onnx",
        folder="rapidocr",
        sha256="aa" * 32,
    )
    folder = tmp_path / "rapidocr"
    folder.mkdir()
    (folder / "det.onnx").write_bytes(b"corrupt")
    (tmp_path / models_svc.REVISION_NAME).write_text("same", encoding="utf-8")
    pulled: list[str] = []

    def download(item: WeightSpec, dest: Path) -> None:
        pulled.append(item.name)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / item.name).write_bytes(b"ok")

    out = models_svc.sync_key_ocr_models(
        dest=tmp_path,
        fetch_remote=lambda: "same",
        download=download,
        specs=[spec],
    )
    assert pulled == ["det.onnx"]
    assert out["updated"] is True


def test_safe_zip_rejects_parent_paths() -> None:
    with pytest.raises(OcrError):
        models_svc._safe_zip_member(["../craft_mlt_25k.pth"], "craft_mlt_25k.pth")


def test_safe_zip_picks_filename() -> None:
    assert (
        models_svc._safe_zip_member(["weights/craft_mlt_25k.pth"], "craft_mlt_25k.pth")
        == "weights/craft_mlt_25k.pth"
    )


def test_download_weight_streams_via_http_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    class _Resp:
        status_code = 200

        def iter_bytes(self, chunk_size=None):  # noqa: ANN001
            yield b"he"
            yield b"llo"

    @contextmanager
    def fake_stream(*_a, **_k):
        yield _Resp()

    monkeypatch.setattr(models_svc, "http_stream", fake_stream)
    spec = WeightSpec(
        name="det.onnx",
        url="https://example.test/det.onnx",
        folder="rapidocr",
    )
    models_svc.download_weight(spec, tmp_path)
    assert (tmp_path / "det.onnx").read_bytes() == b"hello"
