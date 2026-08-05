"""本地库：可选清空非 admin / 仅清演示假用户，或灌入假数据（用户A～Z）。

用法（仓库 backend 目录）:
  .venv\\Scripts\\python.exe -m local_dev.seed_local --purge-fake
  .venv\\Scripts\\python.exe -m local_dev.seed_local
  .venv\\Scripts\\python.exe -m local_dev.seed_local --wipe
  .venv\\Scripts\\python.exe -m local_dev.seed_local --reseed-history

登录示例: user_a / demopass123
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许直接 python local_dev/seed_local.py
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from local_dev.steam_fake import (
    FAKE_PASSWORD,
    ensure_local_fake_data,
    regenerate_fake_history,
    wipe_fake_users,
    wipe_non_admin_users,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地假数据种子")
    parser.add_argument(
        "--purge-fake",
        action="store_true",
        help="仅删除演示假用户 user_a～user_z 及其 Steam 历史（不重建）",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="先删除除 admin 外的全部用户及其关联数据",
    )
    parser.add_argument(
        "--reseed-history",
        action="store_true",
        help="清空演示账号游玩/在线记录并按作息重生成（上月1日～今天）",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.purge_fake:
            wiped = wipe_fake_users(db)
            print("已清空演示假用户及 Steam 历史:", wiped)
            return 0
        if args.wipe:
            wiped = wipe_non_admin_users(db)
            print("已清空非 admin 用户数据:", wiped)
        if args.reseed_history:
            stats = regenerate_fake_history(db)
            print("已重生成历史:", stats)
        else:
            stats = ensure_local_fake_data(db, force_history=args.wipe)
            print("本地假数据已就绪:", stats)
        print("登录查看:")
        print("  用户名: user_a … user_z（显示名：用户A～用户Z）")
        print("  作息:   A–I 大学生 / J–R 上班族 / S–Z 游戏主播")
        print(f"  密码:   {FAKE_PASSWORD}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
