"""Runtime paths resolve against install root, not process cwd."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.paths import hydrate_legacy_runtime, resolve_runtime_path
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

    got = resolve_runtime_path("var/data", configured_install=str(install))
    assert got == (install / "var" / "data").resolve()
    assert "backend-cwd" not in str(got)


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
        data_dir="var/data",
        upload_dir="var/uploads",
        install_dir=str(install),
    )
    dest = install / "var" / "data" / ".secret_key"
    assert got == "legacy-secret-value"
    assert dest.read_text(encoding="utf-8").strip() == "legacy-secret-value"
    assert not (legacy / ".secret_key").is_file()


def test_hydrate_copies_logs_once(tmp_path: Path) -> None:
    install = tmp_path / "zhange-stats"
    dest = install / "var" / "data"
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
