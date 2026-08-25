"""Resolve and persist application secrets."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

from app.core.paths import (
    iter_legacy_data_dirs,
    resolve_install_dir,
    resolve_runtime_path,
)

logger = logging.getLogger("zhange.secret")

DEFAULT_SECRET_KEY = "change-me-in-production-use-a-long-random-string"
_SECRET_FILENAME = ".secret_key"


def _read_secret_file(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        stored = path.read_text(encoding="utf-8").strip()
        return stored or None
    except OSError as exc:
        logger.warning("Failed to read SECRET_KEY from %s: %s", path, exc)
        return None


def _write_secret_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _legacy_secret_candidates(
    *,
    dest: Path,
    upload_root: Path,
    install: Path,
) -> list[Path]:
    seen: set[Path] = {dest}
    out: list[Path] = []
    for path in (
        upload_root / _SECRET_FILENAME,
        *(root / _SECRET_FILENAME for root in iter_legacy_data_dirs(install)),
    ):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def ensure_secret_key(
    configured: str,
    *,
    data_dir: str,
    upload_dir: str,
    install_dir: str = "",
) -> str:
    """Return a stable SECRET_KEY, generating one on first run when unset.

    Priority:
    1. Non-empty, non-placeholder value from environment / .env
    2. Existing file under DATA_DIR/.secret_key (outside the public uploads tree)
    3. Legacy locations (UPLOAD_DIR, install/data, backend/data, frontend/data)
       — migrate into DATA_DIR then prefer that
    4. Generate a new key and persist to DATA_DIR (fails hard if unwritable)
    """

    value = (configured or "").strip()
    if value and value != DEFAULT_SECRET_KEY:
        return value

    install = resolve_install_dir(configured=install_dir)
    data_root = resolve_runtime_path(data_dir, configured_install=str(install))
    secret_path = data_root / _SECRET_FILENAME
    upload_root = resolve_runtime_path(upload_dir, configured_install=str(install))

    stored = _read_secret_file(secret_path)
    if stored:
        return stored

    for legacy_path in _legacy_secret_candidates(
        dest=secret_path,
        upload_root=upload_root,
        install=install,
    ):
        legacy = _read_secret_file(legacy_path)
        if not legacy:
            continue
        try:
            _write_secret_file(secret_path, legacy)
            logger.info(
                "Migrated SECRET_KEY from %s to %s",
                legacy_path,
                secret_path,
            )
            try:
                legacy_path.unlink(missing_ok=True)
            except OSError:
                pass
        except OSError as exc:
            logger.warning(
                "Could not migrate SECRET_KEY to %s (%s); using legacy file",
                secret_path,
                exc,
            )
        return legacy

    generated = secrets.token_urlsafe(48)
    try:
        _write_secret_file(secret_path, generated)
    except OSError as exc:
        raise RuntimeError(
            f"Could not persist SECRET_KEY to {secret_path}. "
            "Set SECRET_KEY in the environment, or make DATA_DIR writable."
        ) from exc
    logger.info("Generated SECRET_KEY and saved to %s", secret_path)
    return generated
