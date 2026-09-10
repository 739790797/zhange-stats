"""Runtime paths resolve against install root, not process cwd."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core.paths import (
    DEFAULT_DATA_DIR,
    DEFAULT_UPLOAD_DIR,
    LEFTOVER_TEXTTELLER_FILES,
    cleanup_legacy_install_tree,
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


def test_migrate_rewrites_env_var_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = tmp_path / "zhange-stats"
    var_data = install / "var" / "data"
    var_data.mkdir(parents=True)
    (var_data / ".secret_key").write_text("k\n", encoding="utf-8")
    (install / "var" / "uploads").mkdir(parents=True)
    sqlite = (var_data / "zhange.sqlite").resolve().as_posix()
    monkeypatch.setenv("DATA_DIR", str(var_data))
    monkeypatch.setenv("UPLOAD_DIR", str(install / "var" / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{sqlite}")

    migrate_runtime_layout(install)

    assert os.environ["DATA_DIR"] == DEFAULT_DATA_DIR
    assert os.environ["UPLOAD_DIR"] == DEFAULT_UPLOAD_DIR
    assert os.environ["DATABASE_URL"].replace("\\", "/").endswith(
        "data/runtime/zhange.sqlite"
    )


def test_migrate_merges_backend_uploads(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    dest = install / "data" / "uploads" / "avatars"
    dest.mkdir(parents=True)
    (dest / "keep.jpg").write_bytes(b"a")
    leftover = install / "backend" / "uploads" / "articles"
    leftover.mkdir(parents=True)
    (leftover / "pic.png").write_bytes(b"b")

    migrate_runtime_layout(install)

    assert (install / "data" / "uploads" / "avatars" / "keep.jpg").is_file()
    assert (install / "data" / "uploads" / "articles" / "pic.png").is_file()
    assert not (install / "backend" / "uploads").exists()


def test_cleanup_legacy_install_tree_skips_env_and_secret(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    (install / "scripts" / "config.example").mkdir(parents=True)
    (install / "scripts" / "linux").mkdir(parents=True)
    (install / "scripts" / "config.example" / "app.json").write_text("{}\n", encoding="utf-8")
    (install / "scripts" / "linux" / "zhange-stats.service").write_text("u\n", encoding="utf-8")
    (install / "config.example").mkdir()
    (install / "config.example" / "app.json").write_text("old\n", encoding="utf-8")
    (install / "deploy" / "systemd").mkdir(parents=True)
    (install / "backend" / "uploads").mkdir(parents=True)
    (install / "backend" / "data" / "logs").mkdir(parents=True)
    (install / "backend" / "data" / ".secret_key").write_text("other\n", encoding="utf-8")
    (install / ".env").write_text("X=1\n", encoding="utf-8")
    models = install / "data" / "models" / "texteller"
    models.mkdir(parents=True)
    (models / "encoder_model.onnx").write_bytes(b"keep")
    (models / "decoder_model.onnx").write_bytes(b"keep")
    for name in LEFTOVER_TEXTTELLER_FILES:
        (models / name).write_bytes(b"drop")
    (install / "data" / "runtime" / "maa").mkdir(parents=True)

    removed = cleanup_legacy_install_tree(install)
    assert "config.example/" in removed
    assert "deploy/" in removed
    assert any(item.endswith("decoder_model_merged.onnx") for item in removed)
    assert not (install / "config.example").exists()
    assert not (install / "deploy").exists()
    assert not (install / "backend" / "uploads").exists()
    assert not (install / "data" / "runtime" / "maa").exists()
    assert (install / ".env").is_file()
    assert (install / "backend" / "data" / ".secret_key").read_text(encoding="utf-8") == "other\n"
    assert (models / "encoder_model.onnx").is_file()
    assert (models / "decoder_model.onnx").is_file()
    for name in LEFTOVER_TEXTTELLER_FILES:
        assert not (models / name).exists()
