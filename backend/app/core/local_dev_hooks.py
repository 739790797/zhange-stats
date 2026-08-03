"""Optional local_dev hooks. Implementation: backend/local_dev/."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType

logger = logging.getLogger(__name__)


def import_steam_fake() -> ModuleType | None:
    """Return local_dev.steam_fake if present; otherwise None."""
    try:
        return importlib.import_module("local_dev.steam_fake")
    except ImportError:
        return None
