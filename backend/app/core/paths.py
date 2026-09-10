"""Install root and runtime directory resolution.

Application runtime lives under the install root ``data/`` — never under
``backend/`` or ``frontend/``. Relative ``DATA_DIR`` / ``UPLOAD_DIR`` resolve
against the install root, not the process cwd (uvicorn usually starts in
``backend/``).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable

DEFAULT_DATA_DIR = "data/runtime"
DEFAULT_UPLOAD_DIR = "data/uploads"
DEFAULT_MODELS_DIR = "data/models"

_RUNTIME_ROOT = "data"
_MODEL_FOLDERS = ("rapidocr", "easyocr", "texteller")
_VAR_LAYOUT = (
    ("data", "runtime"),
    ("uploads", "uploads"),
    ("cache", "cache"),
    ("dev", "run"),
    ("backups", "backups"),
    ("mariadb", "mariadb"),
    ("tmp", "tmp"),
)
_LEGACY_DATA_RELATIVE = ("backend/data", "frontend/data")
_LEGACY_UPLOAD_RELATIVE = ("uploads", "backend/uploads", "frontend/uploads")
_HYDRATE_SUBDIRS = ("logs", "maa")
_EMPTY_LEFTOVER_DIRS = (
    "backend/uploads",
    "backend/var",
    "frontend/uploads",
    "frontend/data",
    "frontend/var",
    "uploads",
)
_EMPTY_MAA_DIRS = (
    "data/runtime/maa",
    "data/maa",
    "backend/data/maa",
    "var/data/maa",
)
# 推理不用；ALLOW_PATTERNS 已不再下载。启动时删存量，不删 .env / 旧 .secret_key。
LEFTOVER_TEXTTELLER_FILES = (
    "decoder_model_merged.onnx",
    "decoder_with_past_model.onnx",
)

logger = logging.getLogger("zhange.startup")


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


def runtime_root(install: Path | None = None) -> Path:
    base = install if install is not None else resolve_install_dir()
    return (base / _RUNTIME_ROOT).resolve()


def iter_legacy_data_dirs(install: Path) -> list[Path]:
    return [(install / rel).resolve() for rel in _LEGACY_DATA_RELATIVE]


def iter_legacy_upload_dirs(install: Path) -> list[Path]:
    return [(install / rel).resolve() for rel in _LEGACY_UPLOAD_RELATIVE]


def _relocate(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    try:
        if src.resolve() == dest.resolve():
            return
    except OSError:
        return
    if dest.exists():
        if src.is_dir() and dest.is_dir():
            for child in list(src.iterdir()):
                _relocate(child, dest / child.name)
            try:
                src.rmdir()
            except OSError:
                pass
            return
        if src.is_file():
            try:
                dest.unlink()
            except OSError:
                pass
        else:
            return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src.rename(dest)
        return
    except OSError:
        pass
    if src.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for child in list(src.iterdir()):
            _relocate(child, dest / child.name)
        try:
            src.rmdir()
        except OSError:
            pass
        return
    try:
        shutil.copy2(src, dest)
        src.unlink()
    except OSError:
        pass


def _is_old_flat_data_dir(root: Path) -> bool:
    if not root.is_dir():
        return False
    if (root / "runtime").exists() or (root / "uploads").exists() or (root / "models").exists():
        return False
    return (root / ".secret_key").is_file() or (root / "logs").is_dir() or (root / "rapidocr").is_dir()


def _split_models(root: Path) -> None:
    runtime = root / "runtime"
    models = root / "models"
    for name in _MODEL_FOLDERS:
        _relocate(runtime / name, models / name)
    for stamp in ("ocr_REVISION", "key_ocr_REVISION"):
        _relocate(runtime / stamp, models / stamp)
    _relocate(runtime / "tarkov_pw_profile", root / "cache" / "tarkov_pw_profile")


def _rewrite_path_value(raw: str, install: Path) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    key = text.replace("\\", "/").strip("/")
    rel_map = {
        "var/data": DEFAULT_DATA_DIR,
        "var/uploads": DEFAULT_UPLOAD_DIR,
        "var/data/zhange.sqlite": f"{DEFAULT_DATA_DIR}/zhange.sqlite",
        "data": DEFAULT_DATA_DIR,
        "data/zhange.sqlite": f"{DEFAULT_DATA_DIR}/zhange.sqlite",
        "uploads": DEFAULT_UPLOAD_DIR,
    }
    if key in rel_map:
        return rel_map[key]
    if (
        key == DEFAULT_DATA_DIR
        or key.startswith(f"{DEFAULT_DATA_DIR}/")
        or key == DEFAULT_UPLOAD_DIR
        or key.startswith(f"{DEFAULT_UPLOAD_DIR}/")
        or key == DEFAULT_MODELS_DIR
        or key.startswith(f"{DEFAULT_MODELS_DIR}/")
    ):
        return None
    try:
        resolved = Path(text).expanduser()
        if not resolved.is_absolute():
            return None
        resolved = resolved.resolve()
    except OSError:
        return None
    ordered = (
        ((install / "var" / "data").resolve(), DEFAULT_DATA_DIR),
        ((install / "var" / "uploads").resolve(), DEFAULT_UPLOAD_DIR),
        ((install / "data" / "runtime").resolve(), DEFAULT_DATA_DIR),
        ((install / "data" / "uploads").resolve(), DEFAULT_UPLOAD_DIR),
        ((install / "data").resolve(), DEFAULT_DATA_DIR),
        ((install / "uploads").resolve(), DEFAULT_UPLOAD_DIR),
    )
    for old, new in ordered:
        if resolved == old:
            return new
        try:
            rest = resolved.relative_to(old).as_posix()
        except ValueError:
            continue
        return f"{new}/{rest}"
    return None


def _patch_json(path: Path, mutator: Callable[[dict[str, Any]], bool]) -> None:
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    if not mutator(payload):
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rewrite_site_config_paths(install: Path) -> None:
    config = install / "config"

    def patch_app(data: dict[str, Any]) -> bool:
        changed = False
        for key in ("DATA_DIR", "UPLOAD_DIR"):
            nxt = _rewrite_path_value(str(data.get(key) or ""), install)
            if nxt is not None and nxt != data.get(key):
                data[key] = nxt
                changed = True
        return changed

    def patch_database(data: dict[str, Any]) -> bool:
        nxt = _rewrite_path_value(str(data.get("path") or ""), install)
        if nxt is None or nxt == data.get("path"):
            return False
        data["path"] = nxt
        return True

    _patch_json(config / "app.json", patch_app)
    _patch_json(config / "database.json", patch_database)


def _rewrite_sqlite_database_url(raw: str, install: Path) -> str | None:
    text = (raw or "").strip()
    if not text.lower().startswith("sqlite"):
        return None
    marker = ":///"
    idx = text.find(marker)
    if idx < 0:
        return None
    rest = text[idx + len(marker) :].replace("\\", "/")
    nxt = _rewrite_path_value(rest, install)
    if nxt is None:
        return None
    dest = Path(nxt)
    if not dest.is_absolute():
        dest = (install / dest).resolve()
    else:
        dest = dest.resolve()
    return "sqlite:///" + dest.as_posix()


def rewrite_legacy_runtime_env(install: Path | None = None) -> dict[str, str]:
    """If process env still points at ``var/data``, rewrite to the new layout.

    systemd ``EnvironmentFile=.env`` and leftover ``DATA_DIR`` win over
    ``config/app.json``; after 0.5.1 that can recreate an empty ``var/data``.
    """

    base = (install or resolve_install_dir()).resolve()
    changed: dict[str, str] = {}
    for key in ("DATA_DIR", "UPLOAD_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        nxt = _rewrite_path_value(raw, base)
        if nxt is None or nxt == raw:
            continue
        os.environ[key] = nxt
        changed[key] = nxt
    raw_db = (os.environ.get("DATABASE_URL") or "").strip()
    if raw_db:
        nxt_db = _rewrite_sqlite_database_url(raw_db, base)
        if nxt_db is not None and nxt_db != raw_db:
            os.environ["DATABASE_URL"] = nxt_db
            changed["DATABASE_URL"] = nxt_db
    return changed


def _rel_of(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix().replace("\\", "/")


def _rmdir_empty_tree(path: Path) -> bool:
    if path.is_symlink() or not path.is_dir():
        return False
    try:
        children = list(path.iterdir())
    except OSError:
        return False
    for child in children:
        if child.is_dir() and not child.is_symlink():
            _rmdir_empty_tree(child)
    try:
        path.rmdir()
        return True
    except OSError:
        return False


def _unlink_if_file(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def cleanup_legacy_install_tree(install: Path | None = None) -> list[str]:
    """Delete leftovers that 0.5.1 moved away from but did not remove.

    Does **not** delete root ``.env`` or leftover ``.secret_key`` files
    (may differ from the live key).
    """

    base = (install or resolve_install_dir()).resolve()
    removed: list[str] = []

    unit = base / "scripts" / "linux" / "zhange-stats.service"
    leftover_deploy = base / "deploy"
    if unit.is_file() and leftover_deploy.exists():
        try:
            if leftover_deploy.is_dir():
                shutil.rmtree(leftover_deploy)
            else:
                leftover_deploy.unlink()
            removed.append("deploy/")
        except OSError:
            pass

    nested_example = base / "scripts" / "config.example"
    leftover_example = base / "config.example"
    if nested_example.is_dir() and leftover_example.exists():
        try:
            if leftover_example.is_dir():
                shutil.rmtree(leftover_example)
            else:
                leftover_example.unlink()
            removed.append("config.example/")
        except OSError:
            pass

    models = base / DEFAULT_MODELS_DIR / "texteller"
    runtime_texteller = base / DEFAULT_DATA_DIR / "texteller"
    for folder in (models, runtime_texteller):
        for name in LEFTOVER_TEXTTELLER_FILES:
            path = folder / name
            if _unlink_if_file(path):
                removed.append(_rel_of(base, path))

    for rel in _EMPTY_MAA_DIRS:
        path = base / rel
        if _rmdir_empty_tree(path):
            removed.append(rel.rstrip("/") + "/")

    for rel in _EMPTY_LEFTOVER_DIRS:
        path = base / rel
        if _rmdir_empty_tree(path):
            removed.append(rel.rstrip("/") + "/")

    leftover_backend_data = base / "backend" / "data"
    if leftover_backend_data.is_dir():
        logs = leftover_backend_data / "logs"
        if logs.is_dir():
            _rmdir_empty_tree(logs)
        if _rmdir_empty_tree(leftover_backend_data):
            removed.append("backend/data/")

    var = base / "var"
    if var.is_dir() and _rmdir_empty_tree(var):
        removed.append("var/")

    return removed


def migrate_runtime_layout(install: Path | None = None) -> None:
    """Move ``var/`` and old flat ``data/`` into ``data/{runtime,uploads,models,…}``."""

    base = (install or resolve_install_dir()).resolve()
    root = base / _RUNTIME_ROOT
    var = base / "var"

    if _is_old_flat_data_dir(root):
        staging = base / ".zhange-data-migrate"
        if staging.exists():
            shutil.rmtree(staging)
        root.rename(staging)
        root.mkdir(parents=True)
        runtime = root / "runtime"
        runtime.mkdir()
        for child in list(staging.iterdir()):
            _relocate(child, runtime / child.name)
        try:
            staging.rmdir()
        except OSError:
            pass

    if var.is_dir():
        root.mkdir(parents=True, exist_ok=True)
        for old_name, new_name in _VAR_LAYOUT:
            _relocate(var / old_name, root / new_name)
        readme = var / "README.md"
        dest_readme = root / "README.md"
        if readme.is_file() and not dest_readme.exists():
            _relocate(readme, dest_readme)
        try:
            next(var.iterdir())
        except StopIteration:
            var.rmdir()
        except OSError:
            pass

    dest_uploads = root / "uploads"
    for src in iter_legacy_upload_dirs(base):
        _relocate(src, dest_uploads)

    leftover_secret = root / ".secret_key"
    dest_secret = root / "runtime" / ".secret_key"
    if leftover_secret.is_file() and not dest_secret.exists():
        _relocate(leftover_secret, dest_secret)

    _split_models(root)
    _rewrite_site_config_paths(base)
    rewritten = rewrite_legacy_runtime_env(base)
    leftover = cleanup_legacy_install_tree(base)
    if rewritten or leftover:
        logger.info(
            "runtime layout migrated env=%s leftover=%s",
            ",".join(f"{k}={v}" for k, v in rewritten.items()) or "-",
            ",".join(leftover) or "-",
        )


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
