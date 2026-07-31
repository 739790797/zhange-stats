"""Resolve and persist application secrets."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path

logger = logging.getLogger("zhange.secret")

DEFAULT_SECRET_KEY = "change-me-in-production-use-a-long-random-string"
_SECRET_FILENAME = ".secret_key"


def _resolve_dir(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


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


def ensure_secret_key(configured: str, *, data_dir: str, upload_dir: str) -> str:
    """Return a stable SECRET_KEY, generating one on first run when unset.

    Priority:
    1. Non-empty, non-placeholder value from environment / .env
    2. Existing file under DATA_DIR/.secret_key (outside the public uploads tree)
    3. Legacy UPLOAD_DIR/.secret_key — migrate into DATA_DIR then prefer that
    4. Generate a new key and persist to DATA_DIR (fails hard if unwritable)
    """

    value = (configured or "").strip()
    if value and value != DEFAULT_SECRET_KEY:
        return value

    data_root = _resolve_dir(data_dir)
    secret_path = data_root / _SECRET_FILENAME
    legacy_path = _resolve_dir(upload_dir) / _SECRET_FILENAME

    stored = _read_secret_file(secret_path)
    if stored:
        return stored

    legacy = _read_secret_file(legacy_path)
    if legacy:
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
