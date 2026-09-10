"""Isolate config/*.json so tests never write the real install-root config/."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.file_config import set_config_dir_for_tests
from app.core.runtime_cache import pin_library_cache_env


@pytest.fixture(autouse=True)
def _isolate_config_dir(tmp_path):
    cfg = tmp_path / "zhange-config"
    cfg.mkdir()
    set_config_dir_for_tests(cfg)
    get_settings.cache_clear()
    yield
    set_config_dir_for_tests(None)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _pin_library_caches(tmp_path, monkeypatch):
    """Keep Hugging Face / Torch / tempfile off the developer home directory."""
    install = tmp_path / "lib-cache-root"
    install.mkdir()
    applied = pin_library_cache_env(install=install)
    for key, value in applied.items():
        monkeypatch.setenv(key, value)
