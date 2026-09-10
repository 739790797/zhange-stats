"""Align install-root ``config/*.json`` with ``scripts/config.example``.

User values win. Missing keys are copied from the template. ``database.json``
is never created from the example (the setup wizard owns engine selection).
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

from app.core.file_config import (
    CONFIG_NAMES,
    SKIP_CREATE_FROM_EXAMPLE,
    VERSION_KEY,
    config_schema_version,
    read_example,
    read_json,
    write_json,
)
from app.core.paths import resolve_install_dir

logger = logging.getLogger("zhange.config")


def fill_missing(template: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    if current is None:
        return copy.deepcopy(template)
    out = _fill_dict(template, current)
    out[VERSION_KEY] = config_schema_version(template)
    return out


def _fill_dict(template: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    out = dict(current)
    for key, tval in template.items():
        if key == VERSION_KEY:
            continue
        if key not in out:
            out[key] = copy.deepcopy(tval)
            continue
        if isinstance(tval, dict) and isinstance(out.get(key), dict):
            out[key] = _fill_dict(tval, out[key])
    return out


def sync_site_config(*, install: Path | None = None) -> list[str]:
    """Create missing files (except database) and fill new keys. Returns names written."""

    base = (install or resolve_install_dir()).resolve()
    written: list[str] = []
    for name in CONFIG_NAMES:
        template = read_example(name, install=base)
        if template is None:
            continue
        current = read_json(name)
        if current is None:
            if name in SKIP_CREATE_FROM_EXAMPLE:
                continue
            write_json(name, fill_missing(template, None))
            written.append(name)
            continue
        merged = fill_missing(template, current)
        if merged != current:
            write_json(name, merged)
            written.append(name)
    if written:
        logger.info("site config synced files=%s", ",".join(written))
    return written


def prepare_site_config(*, install: Path | None = None) -> list[str]:
    from app.services.config_import import import_legacy_dotenv

    import_legacy_dotenv()
    return sync_site_config(install=install)


def main() -> None:
    names = prepare_site_config()
    if names:
        print("synced " + ",".join(names))


if __name__ == "__main__":
    main()
