"""TexTeller 版本判断、LaTeX 清洗、缺模型/缺包。"""

from pathlib import Path

import pytest

from app.services.articles.errors import ArticleError
from app.services.articles import texteller as texteller_svc


def test_parse_texteller_latex_strips_delimiters() -> None:
    assert texteller_svc.parse_texteller_latex(" $$ E=mc^2 $$ ") == "E=mc^2"
    assert texteller_svc.parse_texteller_latex(r"\[1+1=2\]") == "1+1=2"
    assert texteller_svc.parse_texteller_latex("$a+b$") == "a+b"
    assert texteller_svc.parse_texteller_latex("   ") == ""


def test_should_refresh() -> None:
    assert texteller_svc.should_refresh("aaa", "bbb") is True
    assert texteller_svc.should_refresh("aaa", "aaa") is False
    assert texteller_svc.should_refresh("", "bbb") is True
    assert texteller_svc.should_refresh("aaa", "") is False


def test_sync_downloads_when_revision_changes(tmp_path: Path) -> None:
    dest = tmp_path / "texteller"
    dest.mkdir()
    (dest / "REVISION").write_text("old", encoding="utf-8")
    (dest / "config.json").write_text("{}", encoding="utf-8")
    (dest / "encoder_model.onnx").write_bytes(b"x")

    pulled: list[str] = []

    def fetch() -> str:
        return "newsha"

    def download(revision: str, folder: Path) -> None:
        pulled.append(revision)
        (folder / "config.json").write_text("{}", encoding="utf-8")
        (folder / "encoder_model.onnx").write_bytes(b"y")

    out = texteller_svc.sync_texteller_models(
        dest=dest,
        fetch_remote=fetch,
        download=download,
    )
    assert out["updated"] is True
    assert out["revision"] == "newsha"
    assert pulled == ["newsha"]
    assert texteller_svc.read_local_revision(dest) == "newsha"


def test_sync_skips_when_current(tmp_path: Path) -> None:
    dest = tmp_path / "texteller"
    dest.mkdir()
    (dest / "REVISION").write_text("same", encoding="utf-8")
    (dest / "config.json").write_text("{}", encoding="utf-8")
    (dest / "encoder_model.onnx").write_bytes(b"x")

    def fetch() -> str:
        return "same"

    def download(revision: str, folder: Path) -> None:
        raise AssertionError("should not download")

    out = texteller_svc.sync_texteller_models(
        dest=dest,
        fetch_remote=fetch,
        download=download,
    )
    assert out == {"updated": False, "revision": "same"}


def test_recognize_requires_ready_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(texteller_svc, "models_ready", lambda: False)
    with pytest.raises(ArticleError) as exc:
        texteller_svc.recognize_image_bytes(b"\x89PNG")
    assert exc.value.status_code == 503
    assert "模型尚未就绪" in exc.value.message


def test_recognize_rejects_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(texteller_svc, "models_ready", lambda: True)
    with pytest.raises(ArticleError) as exc:
        texteller_svc.recognize_image_bytes(b"")
    assert exc.value.status_code == 400


def test_recognize_rejects_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(texteller_svc, "models_ready", lambda: True)
    with pytest.raises(ArticleError) as exc:
        texteller_svc.recognize_image_bytes(b"x" * (2 * 1024 * 1024 + 1))
    assert exc.value.status_code == 400
    assert "2MB" in exc.value.message


def test_ensure_skips_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(texteller_svc, "models_ready", lambda: True)

    def boom(**kwargs):
        raise AssertionError("should not sync")

    monkeypatch.setattr(texteller_svc, "sync_texteller_models", boom)
    texteller_svc.ensure_texteller_models()


def test_hf_endpoint_defaults_to_mirror() -> None:
    assert texteller_svc.resolve_hf_endpoint("") == "https://hf-mirror.com"
    assert texteller_svc.resolve_hf_endpoint("  ") == "https://hf-mirror.com"
    assert (
        texteller_svc.resolve_hf_endpoint("https://huggingface.co/")
        == "https://huggingface.co"
    )
    assert texteller_svc.hf_model_api_url("https://hf-mirror.com") == (
        "https://hf-mirror.com/api/models/OleehyO/TexTeller"
    )
    assert texteller_svc.hf_file_url(
        "https://hf-mirror.com",
        "abc",
        "encoder_model.onnx",
    ) == "https://hf-mirror.com/OleehyO/TexTeller/resolve/abc/encoder_model.onnx"


def test_fetch_remote_revision_uses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(texteller_svc, "apply_hf_endpoint", lambda: "https://hf-mirror.com")
    monkeypatch.setattr(
        texteller_svc,
        "hf_get_json",
        lambda url: {"sha": "abc123", "siblings": []},
    )
    assert texteller_svc.fetch_remote_revision() == "abc123"


def test_fetch_remote_revision_keeps_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(texteller_svc, "apply_hf_endpoint", lambda: "https://hf-mirror.com")

    def boom(url: str) -> dict:
        raise RuntimeError("certificate verify failed")

    monkeypatch.setattr(texteller_svc, "hf_get_json", boom)
    with pytest.raises(ArticleError) as exc:
        texteller_svc.fetch_remote_revision()
    assert exc.value.status_code == 502
    assert "hf-mirror.com" in exc.value.message
    assert "certificate verify failed" in exc.value.message


def test_progress_helpers() -> None:
    assert texteller_svc.parse_tqdm_filename("Downloading encoder_model.onnx") == (
        "encoder_model.onnx"
    )
    assert texteller_svc.parse_tqdm_filename("foo/bar.onnx: 12%") == "bar.onnx"
    assert (
        texteller_svc.compute_download_percent(
            done_bytes=50,
            current_bytes=50,
            total_bytes=200,
            files_done=1,
            files_total=2,
        )
        == 50
    )
    assert (
        texteller_svc.compute_download_percent(
            done_bytes=0,
            current_bytes=0,
            total_bytes=0,
            files_done=1,
            files_total=4,
        )
        == 25
    )
    assert texteller_svc.format_sync_message("check") == "正在读取 Hugging Face 版本…"
    assert (
        texteller_svc.format_sync_message(
            "download",
            file="encoder_model.onnx",
            index=2,
            total=8,
        )
        == "正在下载 encoder_model.onnx（2/8）"
    )
    assert texteller_svc.allowed_weight_files(
        [
            {"rfilename": "README.md", "size": 10},
            {"rfilename": "encoder_model.onnx", "size": 30},
            {"rfilename": "decoder_model_merged.onnx", "size": 800},
            {"rfilename": "decoder_with_past_model.onnx", "size": 790},
            {"rfilename": "config.json", "size": 2},
        ]
    ) == [("config.json", 2), ("encoder_model.onnx", 30)]


def test_sync_emits_skip_progress(tmp_path: Path) -> None:
    dest = tmp_path / "texteller"
    dest.mkdir()
    (dest / "REVISION").write_text("same", encoding="utf-8")
    (dest / "config.json").write_text("{}", encoding="utf-8")
    (dest / "encoder_model.onnx").write_bytes(b"x")
    notes: list[str] = []

    def progress(message: str, stats: dict) -> None:
        notes.append(str(stats.get("phase")))
        assert message

    out = texteller_svc.sync_texteller_models(
        dest=dest,
        fetch_remote=lambda: "same",
        download=lambda *_a: (_ for _ in ()).throw(AssertionError("no")),
        progress=progress,
    )
    assert out["updated"] is False
    assert "check" in notes
    assert "skip" in notes


def test_onnx_preprocess_shape() -> None:
    import numpy as np
    from PIL import Image

    from app.services.articles.texteller_onnx import (
        FIXED_IMG_SIZE,
        preprocess_image,
        trim_white_border,
    )

    rgb = Image.new("RGB", (80, 40), "white")
    for x in range(20, 40):
        rgb.putpixel((x, 20), (0, 0, 0))
    pixels = preprocess_image(rgb)
    assert pixels.shape == (1, 1, FIXED_IMG_SIZE, FIXED_IMG_SIZE)
    assert pixels.dtype == np.float32
    trimmed = trim_white_border(np.asarray(rgb))
    assert trimmed.shape[0] < 40
    assert trimmed.shape[1] < 80


def test_models_ready_needs_revision_and_weights(tmp_path: Path) -> None:
    dest = tmp_path / "texteller"
    dest.mkdir()
    assert texteller_svc.models_ready(dest) is False
    (dest / "REVISION").write_text("sha", encoding="utf-8")
    (dest / "config.json").write_text("{}", encoding="utf-8")
    assert texteller_svc.models_ready(dest) is False
    (dest / "encoder_model.onnx").write_bytes(b"x")
    assert texteller_svc.models_ready(dest) is True


def test_hf_get_json_maps_http_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 502

        def json(self):
            return {}

    monkeypatch.setattr(
        texteller_svc, "http_request", lambda *_a, **_k: _Resp()
    )
    with pytest.raises(ArticleError) as exc:
        texteller_svc.hf_get_json("https://example.test/api")
    assert exc.value.status_code == 502
    assert "HTTP 502" in exc.value.message
