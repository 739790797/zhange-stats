"""OpenAPI：塔科夫图鉴 / 工具公开，个人数据与 OCR / 出图须登录。"""

from app.main import app

_PUBLIC_GETS = (
    "/api/guides/tarkov/items",
    "/api/guides/tarkov/items/{item_id}",
    "/api/guides/tarkov/search",
    "/api/guides/tarkov/ammo",
    "/api/guides/tarkov/guns",
    "/api/guides/tarkov/tasks",
    "/api/guides/tarkov/tasks/{task_id}",
    "/api/guides/tarkov/raid-prep",
    "/api/guides/tarkov/traders",
    "/api/guides/tarkov/bosses",
    "/api/guides/tarkov/maps",
    "/api/guides/tarkov/maps/{map_slug}",
    "/api/guides/tarkov/maps/{map_slug}/places",
    "/api/guides/tarkov/hideout",
    "/api/guides/tarkov/hideout/{station_slug}",
    "/api/guides/tarkov/key-packs",
    "/api/guides/tarkov/collection",
    "/api/guides/tarkov/workbench/guns/{gun_id}",
    "/api/guides/tarkov/workbench/community-builds",
    "/api/guides/tarkov/workbench/gunsmith-tasks",
    "/api/guides/tarkov/workbench/build-image/status",
    "/api/guides/tarkov/goons",
    "/api/guides/tarkov/raid-rooms",
    "/api/guides/tarkov/raid-rooms/{public_id}",
)

_PUBLIC_POSTS = (
    "/api/guides/tarkov/workbench/slots/allowed-items",
    "/api/guides/tarkov/workbench/calculate",
    "/api/guides/tarkov/workbench/gunsmith-solve",
)

_PROTECTED_GETS = (
    "/api/guides/tarkov/profile",
    "/api/guides/tarkov/hideout-levels",
    "/api/guides/tarkov/key-owns",
    "/api/guides/tarkov/collection-owns",
    "/api/guides/tarkov/collection-layout",
    "/api/guides/tarkov/task-dones",
    "/api/guides/tarkov/raid-logs",
    "/api/guides/tarkov/raid-prep/state",
    "/api/guides/tarkov/raid-rooms/mine",
)

_PROTECTED_POSTS = (
    "/api/guides/tarkov/workbench/build-image",
    "/api/guides/tarkov/key-owns/recognize",
    "/api/guides/tarkov/raid-prep/recognize",
    "/api/guides/tarkov/raid-rooms",
)


def test_tarkov_catalog_gets_have_no_security() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _PUBLIC_GETS:
        op = (paths.get(path) or {}).get("get")
        assert op is not None, f"missing GET {path}"
        security = op.get("security")
        assert not security, f"{path} should be public, got security={security}"


def test_tarkov_tool_posts_have_no_security() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _PUBLIC_POSTS:
        op = (paths.get(path) or {}).get("post")
        assert op is not None, f"missing POST {path}"
        security = op.get("security")
        assert not security, f"{path} should be public, got security={security}"


def test_tarkov_personal_gets_require_security() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _PROTECTED_GETS:
        op = (paths.get(path) or {}).get("get")
        assert op is not None, f"missing GET {path}"
        assert op.get("security"), f"{path} must require auth"


def test_tarkov_mutating_personal_posts_require_security() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _PROTECTED_POSTS:
        op = (paths.get(path) or {}).get("post")
        assert op is not None, f"missing POST {path}"
        assert op.get("security"), f"{path} must require auth"
