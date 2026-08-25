"""OpenAPI 不变量：签到 status force 默认、已弃用路径标记。"""

from app.main import app

_STATUS_PATHS = (
    "/api/skland/status",
    "/api/taygedo/status",
    "/api/exilium/status",
    "/api/kujiequ/status",
)


def test_checkin_status_force_defaults_true() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _STATUS_PATHS:
        op = (paths.get(path) or {}).get("get")
        assert op is not None, f"missing GET {path}"
        params = {p["name"]: p for p in (op.get("parameters") or []) if "name" in p}
        assert "force" in params, f"{path} missing force"
        assert params["force"].get("schema", {}).get("default") is True, path


def test_arknights_box_marked_deprecated() -> None:
    schema = app.openapi()
    op = (schema.get("paths") or {}).get("/api/skland/arknights/box", {}).get("get")
    assert op is not None
    assert op.get("deprecated") is True
