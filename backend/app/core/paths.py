"""Install root and runtime directory resolution.

Application runtime (secrets, logs, uploads, update lock, local scratch)
lives under the install root ``var/`` by default — never under ``backend/``
or ``frontend/``. Relative ``DATA_DIR`` / ``UPLOAD_DIR`` resolve against the
install root, not the process cwd (uvicorn usually starts in ``backend/``).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

DEFAULT_DATA_DIR = "var/data"
DEFAULT_UPLOAD_DIR = "var/uploads"

_LEGACY_DATA_RELATIVE = ("data", "backend/data", "frontend/data")
_LEGACY_UPLOAD_RELATIVE = ("uploads", "backend/uploads", "frontend/uploads")
_HYDRATE_SUBDIRS = ("logs", "maa")


def resolve_install_dir(*, configured: str = "") -> Path:
    raw = (configured or os.environ.get("APP_INSTALL_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[3],
        Path.cwd().parent if Path.cwd().name == "backend" else Path.cwd(),
        Path.cwd(),
    ):
        if (candidate / "VERSION").is_file() and (candidate / "backend").is_dir():
            return candidate.resolve()
    return Path.cwd().resolve()


def resolve_runtime_path(path_str: str, *, configured_install: str = "") -> Path:
    path = Path(path_str).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (resolve_install_dir(configured=configured_install) / path).resolve()


def iter_legacy_data_dirs(install: Path) -> list[Path]:
    return [(install / rel).resolve() for rel in _LEGACY_DATA_RELATIVE]


def iter_legacy_upload_dirs(install: Path) -> list[Path]:
    return [(install / rel).resolve() for rel in _LEGACY_UPLOAD_RELATIVE]


def hydrate_legacy_runtime(*, dest_data: Path, install: Path) -> None:
    """Copy leftover logs/maa from old locations into dest once.

    Skipped when dest is outside the install tree (pytest tmp paths).
    """

    try:
        dest_data.resolve().relative_to(install.resolve())
    except ValueError:
        return
    dest_data.mkdir(parents=True, exist_ok=True)
    for name in _HYDRATE_SUBDIRS:
        dest = dest_data / name
        if dest.exists():
            continue
        for src_root in iter_legacy_data_dirs(install):
            src = src_root / name
            if src.is_dir() and src.resolve() != dest.resolve():
                shutil.copytree(src, dest)
                break
