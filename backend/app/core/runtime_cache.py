"""Pin third-party library caches inside the install tree.

Hugging Face / Torch / EasyOCR / pip / Playwright default to the user home
directory. The app process (and host scripts) override those env vars so
writes stay under ``data/cache`` and ``data/tmp``.

On a real install, known 战鸽 artifacts already sitting in those home
defaults are copied into the install tree (copy-if-missing). Shared caches
such as Cursor's Hugging Face home are not moved wholesale.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.core.paths import DEFAULT_MODELS_DIR, resolve_install_dir, runtime_root

_CACHE_ENV: tuple[tuple[str, str], ...] = (
    ("HF_HOME", "huggingface"),
    ("TORCH_HOME", "torch"),
    ("EASYOCR_MODULE_PATH", "easyocr"),
    ("MPLCONFIGDIR", "matplotlib"),
    ("XDG_CACHE_HOME", "xdg"),
    ("PIP_CACHE_DIR", "pip"),
    ("PLAYWRIGHT_BROWSERS_PATH", "playwright"),
    ("PYTHONPYCACHEPREFIX", "pycache"),
)

TEXTTELLER_HUB_DIR = "models--OleehyO--TexTeller"
TEXTTELLER_FILES = (
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "merges.txt",
    "encoder_model.onnx",
    "decoder_model.onnx",
    "REVISION",
)
EASYOCR_WEIGHT_FILES = (
    "craft_mlt_25k.pth",
    "zh_sim_g2.pth",
    "english_g2.pth",
)
_OUTSIDE_ENV_KEYS = (
    "HF_HOME",
    "HF_HUB_CACHE",
    "HUGGINGFACE_HUB_CACHE",
    "TORCH_HOME",
    "EASYOCR_MODULE_PATH",
)


def path_in_install(path: Path, install: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
        root = install.resolve()
    except OSError:
        return False
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False


def runtime_cache_dir(install: Path | None = None) -> Path:
    return (runtime_root(install) / "cache").resolve()


def runtime_tmp_dir(install: Path | None = None) -> Path:
    path = (runtime_root(install) / "tmp").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _copy_file_if_missing(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    try:
        if dest.exists() or src.resolve() == dest.resolve():
            return False
    except OSError:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _copy_tree_missing(src: Path, dest: Path) -> list[str]:
    copied: list[str] = []
    if not src.exists():
        return copied
    try:
        if src.resolve() == dest.resolve():
            return copied
    except OSError:
        return copied
    if src.is_file():
        if _copy_file_if_missing(src, dest):
            copied.append(str(dest))
        return copied
    if not src.is_dir():
        return copied
    for dirpath, _dirnames, filenames in os.walk(src, followlinks=False):
        rel = Path(dirpath).relative_to(src)
        for name in filenames:
            source = Path(dirpath) / name
            if source.is_symlink():
                continue
            target = dest / rel / name
            if _copy_file_if_missing(source, target):
                copied.append(str(target))
    return copied


def _huggingface_roots(home: Path, extra_roots: tuple[Path, ...]) -> list[Path]:
    rows: list[Path] = [home / ".cache" / "huggingface"]
    for path in extra_roots:
        name = path.name.lower()
        if "huggingface" in name or name in {"hub", "hf"}:
            rows.append(path)
            continue
        nested = path / "huggingface"
        if nested.is_dir():
            rows.append(nested)
        if (path / "hub").is_dir():
            rows.append(path)
    out: list[Path] = []
    seen: set[str] = set()
    for path in rows:
        try:
            key = str(path.expanduser().resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _hydrate_texteller(hub_repo: Path, dest: Path) -> list[str]:
    copied: list[str] = []
    snapshots = hub_repo / "snapshots"
    candidates: list[Path] = []
    if snapshots.is_dir():
        ranked: list[tuple[int, Path]] = []
        for snap in snapshots.iterdir():
            if not snap.is_dir():
                continue
            score = sum(1 for name in TEXTTELLER_FILES if (snap / name).is_file())
            ranked.append((score, snap))
        ranked.sort(key=lambda item: -item[0])
        candidates.extend(snap for score, snap in ranked if score)
    candidates.append(hub_repo)
    seen: set[str] = set()
    for root in candidates:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        for name in TEXTTELLER_FILES:
            if _copy_file_if_missing(root / name, dest / name):
                copied.append(str(dest / name))
        if copied:
            break
    return copied


def migrate_spilled_library_caches(
    *,
    install: Path,
    home: Path | None = None,
    extra_roots: tuple[Path, ...] = (),
) -> list[str]:
    """Copy 战鸽-owned files from home-directory defaults into the install tree.

    Does not delete sources and does not move a mixed Hugging Face home (other
    tools such as Cursor may share it). Existing files in the install win.
    """

    base = install.resolve()
    cache = runtime_cache_dir(base)
    models = (base / DEFAULT_MODELS_DIR).resolve()
    home_root = (home or Path.home()).expanduser()
    copied: list[str] = []

    dest_hf = cache / "huggingface"
    dest_easy = cache / "easyocr"
    dest_paddle = cache / "paddleocr"

    for hf_root in _huggingface_roots(home_root, extra_roots):
        repo = hf_root / "hub" / TEXTTELLER_HUB_DIR
        if not repo.exists():
            repo = hf_root / TEXTTELLER_HUB_DIR
        copied.extend(_copy_tree_missing(repo, dest_hf / "hub" / TEXTTELLER_HUB_DIR))
        copied.extend(_hydrate_texteller(repo, models / "texteller"))

    easy_roots = [home_root / ".EasyOCR"]
    torch_roots = [home_root / ".cache" / "torch"]
    paddle_roots = [home_root / ".paddleocr"]
    for path in extra_roots:
        lowered = path.name.lower()
        if "easyocr" in lowered:
            easy_roots.append(path)
        elif "paddle" in lowered:
            paddle_roots.append(path)
        elif "torch" in lowered:
            torch_roots.append(path)

    for root in easy_roots + torch_roots:
        for name in EASYOCR_WEIGHT_FILES:
            for candidate in (root / name, root / "model" / name, root / "hub" / name):
                if _copy_file_if_missing(candidate, models / "easyocr" / name):
                    copied.append(str(models / "easyocr" / name))
        copied.extend(_copy_tree_missing(root / "user_network", dest_easy / "user_network"))

    for root in paddle_roots:
        copied.extend(_copy_tree_missing(root, dest_paddle))

    return copied


def _outside_env_dirs(install: Path) -> tuple[Path, ...]:
    rows: list[Path] = []
    for key in _OUTSIDE_ENV_KEYS:
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path_in_install(path, install):
            continue
        rows.append(path)
    return tuple(rows)


def _should_migrate_spilled(install: Path) -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return (install / "VERSION").is_file() and (install / "backend").is_dir()


def pin_library_cache_env(*, install: Path | None = None) -> dict[str, str]:
    """Point known cache env vars at ``data/cache`` (and tempfile at ``data/tmp``).

    Existing values already inside the install root are kept. Home-directory
    defaults and other outside paths are overwritten. Real installs then copy
    known 战鸽 artifacts from those old locations into the tree.
    """

    base = (install or resolve_install_dir()).resolve()
    extra_roots = _outside_env_dirs(base)
    cache = runtime_cache_dir(base)
    tmp = runtime_tmp_dir(base)
    applied: dict[str, str] = {}

    def assign(key: str, dest: Path) -> None:
        dest = dest.resolve()
        current = (os.environ.get(key) or "").strip()
        if current:
            try:
                current_path = Path(current).expanduser().resolve()
            except OSError:
                current_path = Path(current)
            if path_in_install(current_path, base):
                applied[key] = str(current_path)
                return
        dest.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(dest)
        applied[key] = str(dest)

    for key, rel in _CACHE_ENV:
        assign(key, cache / rel)
    hf_root = Path(applied.get("HF_HOME") or (cache / "huggingface"))
    assign("HF_HUB_CACHE", hf_root / "hub")
    assign("HUGGINGFACE_HUB_CACHE", hf_root / "hub")
    assign("TRANSFORMERS_CACHE", hf_root / "transformers")
    for key in ("TMPDIR", "TEMP", "TMP"):
        assign(key, tmp)
    if _should_migrate_spilled(base):
        migrate_spilled_library_caches(install=base, extra_roots=extra_roots)
    return applied
