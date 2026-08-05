"""health 探测结构（不依赖真实 MySQL 连通时仍返回字段）。"""

from app.main import health


def test_health_shape(monkeypatch) -> None:
    # 不强制 DB 成功；只断言字段齐全
    data = health()
    assert "status" in data
    assert "version" in data
    assert "database" in data
    assert "scheduler" in data
    assert data["database"] in ("ok", "error")
    assert data["status"] in ("ok", "degraded")
