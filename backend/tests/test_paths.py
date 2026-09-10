"""Runtime paths resolve against install root, not process cwd."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core.paths import (
    DEFAULT_DATA_DIR,
    DEFAULT_UPLOAD_DIR,
    hydrate_legacy_runtime,
    migrate_runtime_layout,
    resolve_runtime_path,
)
from app.core.runtime_cache import (
    migrate_spilled_library_caches,
    path_in_install,
    pin_library_cache_env,
)
from app.core.secret import ensure_secret_key


def test_relative_data_dir_uses_install_root_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (install / "backend").mkdir()
    cwd = tmp_path / "backend-cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    got = resolve_runtime_path("data/runtime", configured_install=str(install))
    assert got == (install / "data" / "runtime").resolve()
    assert "backend-cwd" not in str(got)
    legacy = resolve_runtime_path("var/data", configured_install=str(install))
    assert legacy == (install / "var" / "data").resolve()


def test_absolute_data_dir_unchanged(tmp_path: Path) -> None:
    absolute = tmp_path / "elsewhere" / "data"
    got = resolve_runtime_path(str(absolute), configured_install=str(tmp_path / "ignored"))
    assert got == absolute.resolve()


def test_ensure_secret_migrates_from_backend_data(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (install / "backend").mkdir()
    legacy = install / "backend" / "data"
    legacy.mkdir()
    (legacy / ".secret_key").write_text("legacy-secret-value\n", encoding="utf-8")

    got = ensure_secret_key(
        "",
        data_dir="data/runtime",
        upload_dir="data/uploads",
        install_dir=str(install),
    )
    dest = install / "data" / "runtime" / ".secret_key"
    assert got == "legacy-secret-value"
    assert dest.read_text(encoding="utf-8").strip() == "legacy-secret-value"
    assert not (legacy / ".secret_key").is_file()


def test_hydrate_copies_logs_once(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    dest = install / "data" / "runtime"
    legacy_logs = install / "backend" / "data" / "logs"
    legacy_logs.mkdir(parents=True)
    (legacy_logs / "app.jsonl").write_text("{}\n", encoding="utf-8")

    hydrate_legacy_runtime(dest_data=dest, install=install)
    assert (dest / "logs" / "app.jsonl").is_file()
    hydrate_legacy_runtime(dest_data=dest, install=install)
    assert (dest / "logs" / "app.jsonl").read_text(encoding="utf-8") == "{}\n"


def test_hydrate_skips_outside_install_tree(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    (install / "backend" / "data" / "logs").mkdir(parents=True)
    (install / "backend" / "data" / "logs" / "app.jsonl").write_text("x\n", encoding="utf-8")
    dest = tmp_path / "pytest-tmp" / "data"
    hydrate_legacy_runtime(dest_data=dest, install=install)
    assert not (dest / "logs").exists()


def test_migrate_var_layout_to_data(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    var = install / "var"
    (var / "data" / "logs").mkdir(parents=True)
    (var / "data" / ".secret_key").write_text("k\n", encoding="utf-8")
    (var / "data" / "rapidocr").mkdir()
    (var / "data" / "rapidocr" / "det.onnx").write_bytes(b"x")
    (var / "data" / "ocr_REVISION").write_text("rev\n", encoding="utf-8")
    (var / "uploads" / "avatars").mkdir(parents=True)
    (var / "dev" / "backend.pid").parent.mkdir(parents=True)
    (var / "dev" / "backend.pid").write_text("1\n", encoding="utf-8")
    (var / "cache" / "vite").mkdir(parents=True)
    (install / "config").mkdir()
    (install / "config" / "app.json").write_text(
        json.dumps({"DATA_DIR": "var/data", "UPLOAD_DIR": "var/uploads"}),
        encoding="utf-8",
    )
    (install / "config" / "database.json").write_text(
        json.dumps({"engine": "sqlite", "path": "var/data/zhange.sqlite"}),
        encoding="utf-8",
    )

    migrate_runtime_layout(install)

    assert (install / "data" / "runtime" / ".secret_key").is_file()
    assert (install / "data" / "models" / "rapidocr" / "det.onnx").is_file()
    assert (install / "data" / "models" / "ocr_REVISION").read_text(encoding="utf-8") == "rev\n"
    assert (install / "data" / "uploads" / "avatars").is_dir()
    assert (install / "data" / "run" / "backend.pid").is_file()
    assert (install / "data" / "cache" / "vite").is_dir()
    assert not (install / "var").exists()
    app = json.loads((install / "config" / "app.json").read_text(encoding="utf-8"))
    assert app["DATA_DIR"] == DEFAULT_DATA_DIR
    assert app["UPLOAD_DIR"] == DEFAULT_UPLOAD_DIR
    db = json.loads((install / "config" / "database.json").read_text(encoding="utf-8"))
    assert db["path"] == "data/runtime/zhange.sqlite"


def test_migrate_old_flat_data_dir(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    flat = install / "data"
    flat.mkdir()
    (flat / ".secret_key").write_text("k\n", encoding="utf-8")
    (flat / "logs").mkdir()
    (flat / "texteller").mkdir()
    (flat / "texteller" / "encoder_model.onnx").write_bytes(b"x")
    (install / "config").mkdir()
    (install / "config" / "app.json").write_text(
        json.dumps({"DATA_DIR": str(flat)}),
        encoding="utf-8",
    )

    migrate_runtime_layout(install)

    assert (install / "data" / "runtime" / ".secret_key").is_file()
    assert (install / "data" / "runtime" / "logs").is_dir()
    assert (install / "data" / "models" / "texteller" / "encoder_model.onnx").is_file()
    app = json.loads((install / "config" / "app.json").read_text(encoding="utf-8"))
    assert app["DATA_DIR"] == DEFAULT_DATA_DIR


def test_migrate_merges_into_existing_runtime(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    runtime = install / "data" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "placeholder.txt").write_text("keep\n", encoding="utf-8")
    (runtime / ".secret_key").write_text("stub-key\n", encoding="utf-8")
    (install / "var" / "data").mkdir(parents=True)
    (install / "var" / "data" / ".secret_key").write_text("old-key\n", encoding="utf-8")
    (install / "var" / "data" / "logs").mkdir()
    (install / "var" / "data" / "logs" / "app.jsonl").write_text("{}\n", encoding="utf-8")

    migrate_runtime_layout(install)

    assert (runtime / "placeholder.txt").read_text(encoding="utf-8") == "keep\n"
    assert (runtime / ".secret_key").read_text(encoding="utf-8") == "old-key\n"
    assert (runtime / "logs" / "app.jsonl").is_file()
    assert not (install / "var" / "data").exists()


def test_pin_library_cache_env_overrides_home_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    leak = Path.home() / ".cache" / "huggingface"
    monkeypatch.setenv("HF_HOME", str(leak))
    monkeypatch.setenv("TORCH_HOME", str(Path.home() / ".cache" / "torch"))
    monkeypatch.setenv("EASYOCR_MODULE_PATH", str(Path.home() / ".EasyOCR"))
    monkeypatch.delenv("TMPDIR", raising=False)

    applied = pin_library_cache_env(install=install)
    hf = Path(applied["HF_HOME"])
    assert hf == (install / "data" / "cache" / "huggingface").resolve()
    assert os.environ["HF_HOME"] == str(hf)
    assert path_in_install(Path(applied["TORCH_HOME"]), install)
    assert path_in_install(Path(applied["EASYOCR_MODULE_PATH"]), install)
    assert path_in_install(Path(applied["TMPDIR"]), install)
    assert Path(applied["HF_HUB_CACHE"]) == hf / "hub"


def test_pin_library_cache_env_keeps_path_inside_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    custom = install / "data" / "cache" / "custom-hf"
    custom.mkdir(parents=True)
    monkeypatch.setenv("HF_HOME", str(custom))

    applied = pin_library_cache_env(install=install)
    assert Path(applied["HF_HOME"]).resolve() == custom.resolve()
    assert Path(applied["HF_HUB_CACHE"]).resolve() == (custom / "hub").resolve()


def test_migrate_spilled_copies_owned_weights_and_leaves_shared_hf(
    tmp_path: Path,
) -> None:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    home = tmp_path / "home"
    snap = (
        home
        / ".cache"
        / "huggingface"
        / "hub"
        / "models--OleehyO--TexTeller"
        / "snapshots"
        / "abc"
    )
    snap.mkdir(parents=True)
    (snap / "encoder_model.onnx").write_bytes(b"enc")
    (snap / "config.json").write_text("{}\n", encoding="utf-8")
    shared = home / ".cache" / "huggingface" / ".agent_harnesses.json"
    shared.write_text("{}\n", encoding="utf-8")
    easy = home / ".EasyOCR" / "model"
    easy.mkdir(parents=True)
    (easy / "craft_mlt_25k.pth").write_bytes(b"craft")
    (home / ".EasyOCR" / "other.bin").write_bytes(b"nope")

    copied = migrate_spilled_library_caches(install=install, home=home)
    models = install / "data" / "models"
    assert (models / "texteller" / "encoder_model.onnx").read_bytes() == b"enc"
    assert (models / "easyocr" / "craft_mlt_25k.pth").read_bytes() == b"craft"
    assert not (install / "data" / "cache" / "huggingface" / ".agent_harnesses.json").exists()
    assert shared.is_file()
    assert (easy / "craft_mlt_25k.pth").is_file()
    assert any("encoder_model.onnx" in item.replace("\\", "/") for item in copied)

    (models / "texteller" / "encoder_model.onnx").write_bytes(b"keep")
    migrate_spilled_library_caches(install=install, home=home)
    assert (models / "texteller" / "encoder_model.onnx").read_bytes() == b"keep"
