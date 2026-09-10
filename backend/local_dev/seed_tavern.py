"""开发环境：灌入酒馆示例文章。

用法（仓库 backend 目录）:
  .venv\\Scripts\\python.exe -m local_dev.seed_tavern
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.database import SessionLocal
from app.services.articles.dev_samples import ensure_dev_sample_articles


def main() -> int:
    db = SessionLocal()
    try:
        stats = ensure_dev_sample_articles(db)
        print("酒馆示例文:", stats)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
