"""ASGI /health 契约（AsyncClient，避免同步 TestClient / lifespan migrate）。"""

import anyio
import httpx

from app.main import app


def test_health_endpoint_shape() -> None:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.get("/health")

    resp = anyio.run(_call)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert data["database"] in ("ok", "error")
    assert data["scheduler"] in ("ok", "stopped")
    assert data["status"] in ("ok", "degraded")
