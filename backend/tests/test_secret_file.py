"""SECRET_KEY 文件：0600 原子写、失败不留半截、首启生成不覆盖并发写入者。"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from app.core import secret
from app.core.secret import ensure_secret_key


def _install(tmp_path: Path) -> Path:
    install = tmp_path / "zhange-stats"
    install.mkdir()
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (install / "backend").mkdir()
    return install


def _ensure(install: Path) -> str:
    return ensure_secret_key(
        "",
        data_dir="data/runtime",
        upload_dir="data/uploads",
        install_dir=str(install),
    )


def test_generated_secret_is_private_and_leaves_no_temp(tmp_path: Path) -> None:
    install = _install(tmp_path)
    got = _ensure(install)
    dest = install / "data" / "runtime" / ".secret_key"
    assert dest.read_text(encoding="utf-8") == got + "\n"
    assert [p.name for p in dest.parent.iterdir()] == [".secret_key"]
    if sys.platform != "win32":
        assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert _ensure(install) == got


def test_failed_write_keeps_previous_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "data" / ".secret_key"
    dest.parent.mkdir()
    dest.write_text("old-key\n", encoding="utf-8")

    def boom(_fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(secret.os, "fsync", boom)
    with pytest.raises(OSError):
        secret._write_secret_file(dest, "new-key")
    assert dest.read_text(encoding="utf-8") == "old-key\n"
    assert [p.name for p in dest.parent.iterdir()] == [".secret_key"]


def test_generate_does_not_clobber_concurrent_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install = _install(tmp_path)
    dest = (install / "data" / "runtime" / ".secret_key").resolve()
    real_read = secret._read_secret_file
    raced = {"done": False}

    def racing_read(path: Path) -> str | None:
        if path.resolve() == dest and not raced["done"]:
            raced["done"] = True
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("winner-key\n", encoding="utf-8")
            return None
        return real_read(path)

    monkeypatch.setattr(secret, "_read_secret_file", racing_read)
    assert _ensure(install) == "winner-key"
    assert dest.read_text(encoding="utf-8") == "winner-key\n"


def test_empty_secret_file_is_regenerated(tmp_path: Path) -> None:
    install = _install(tmp_path)
    dest = install / "data" / "runtime" / ".secret_key"
    dest.parent.mkdir(parents=True)
    dest.write_text("", encoding="utf-8")
    got = _ensure(install)
    assert got
    assert dest.read_text(encoding="utf-8").strip() == got


@pytest.mark.skipif(not hasattr(os, "link"), reason="no hard links")
def test_exclusive_falls_back_when_hard_links_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_link(_src: object, _dst: object) -> None:
        raise PermissionError("hard links unsupported")

    monkeypatch.setattr(secret.os, "link", no_link)
    dest = tmp_path / "data" / ".secret_key"
    secret._write_secret_file(dest, "k1", exclusive=True)
    assert dest.read_text(encoding="utf-8") == "k1\n"
    with pytest.raises(FileExistsError):
        secret._write_secret_file(dest, "k2", exclusive=True)
    assert dest.read_text(encoding="utf-8") == "k1\n"
    assert [p.name for p in dest.parent.iterdir()] == [".secret_key"]
