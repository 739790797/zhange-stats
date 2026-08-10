"""CLI entry for scripts/update.sh — applies in-app update then restarts."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Zhange Stats self-update")
    parser.add_argument("--version", default="latest", help="latest or vX.Y.Z")
    parser.add_argument("--proxy", default="", help="Optional URL prefix for GitHub")
    parser.add_argument(
        "--no-reboot",
        action="store_true",
        help="Apply files/deps only; do not restart process",
    )
    args = parser.parse_args()

    from app.services.app_updator import apply_update, trigger_restart

    result = asyncio.run(
        apply_update(
            version=args.version,
            proxy=args.proxy or None,
            reboot=False,
        )
    )
    print(result.message)
    if result.ok and not args.no_reboot:
        print("触发重启…")
        trigger_restart(delay_sec=0.5)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
