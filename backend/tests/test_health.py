"""health 探测结构（不依赖真实 MySQL 连通时仍返回字段）。"""

from fastapi.responses import JSONResponse

from app.main import health


def test_health_shape(monkeypatch) -> None:
    # 不强制 DB 成功；只断言字段齐全与状态码约定
    resp = health()
    assert isinstance(resp, JSONResponse)
    data = resp.body
    import json

    payload = json.loads(data)
    assert "status" in payload
    assert "version" in payload
    assert "database" in payload
    assert "scheduler" in payload
    assert payload["database"] in ("ok", "error")
    assert payload["status"] in ("ok", "degraded")
    if payload["status"] == "ok":
        assert resp.status_code == 200
    else:
        assert resp.status_code == 503
