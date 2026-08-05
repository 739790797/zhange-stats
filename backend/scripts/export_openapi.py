"""从 FastAPI 应用导出 OpenAPI JSON 到前端目录。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保 backend 根目录在 sys.path 中
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402

OUTPUT = (
    BACKEND_ROOT.parent / "frontend" / "src" / "api" / "generated" / "openapi.json"
)


def main() -> None:
    schema = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema written to {OUTPUT}")


if __name__ == "__main__":
    main()
