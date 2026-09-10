#!/usr/bin/env python3
"""Host-side version update. Same GitHub Release apply as the admin UI.

Called from scripts/linux/update.sh and scripts/win/update.ps1.
Does not os.execv — wrappers restart after a successful apply.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.runtime_cache import pin_library_cache_env  # noqa: E402

pin_library_cache_env()
from app.services.app_updator import host_update_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(host_update_main())
