"""从 FastAPI 应用导出 OpenAPI JSON 到前端目录。

**SPA fallback 不算契约。** `/{full_path:path}` 只在 `STATIC_DIR` 指向已存在的目录、
且 `main` 已 import 之后才会注册。本机 `config/app.json` 的 `STATIC_DIR` 一般写着本地的
`static/`（目录存在，哪怕空），CI 的 checkout 没有 `static/` —— 两边导出的 spec 会差出这条
路由，`openapi-drift` 就会红。这里生成前先把 STATIC_DIR 收成空串，让本机与 CI 的产物一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保 backend 根目录在 sys.path 中
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

OUTPUT = (
    BACKEND_ROOT.parent / "frontend" / "src" / "shared" / "api" / "generated" / "openapi.json"
)


def hide_spa_fallback() -> None:
    """让 app 更像 CI 环境：没有 static 目录时不挂 SPA fallback。

    `app.main` import 时若 STATIC_DIR 已指向存在的目录，路由就已经挂上了；
    这里把它从 app 上摘掉，默认路由表不受影响（该方法本来就排在最后）。
    """
    get_settings.cache_clear()
    removed = [r for r in app.router.routes if getattr(r, "path", "") == "/{full_path:path}"]
    for route in removed:
        app.router.routes.remove(route)
    if removed:
        # spec 有缓存，摘完路由要清掉才会重算
        app.openapi_schema = None
        print("export:openapi: dropped SPA fallback (STATIC_DIR is a local artifact)")


def main() -> None:
    hide_spa_fallback()
    schema = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema written to {OUTPUT}")


if __name__ == "__main__":
    main()
