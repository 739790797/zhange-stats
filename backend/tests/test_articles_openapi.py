"""OpenAPI：酒馆公开 GET 不得带 security。"""

from app.main import app

_PUBLIC_GETS = (
    "/api/articles",
    "/api/articles/categories",
    "/api/articles/tags",
    "/api/articles/{slug}",
    "/api/articles/{slug}/comments",
)


def test_article_public_gets_have_no_security() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _PUBLIC_GETS:
        op = (paths.get(path) or {}).get("get")
        assert op is not None, f"missing GET {path}"
        security = op.get("security")
        assert not security, f"{path} should be public, got security={security}"


def test_article_comment_post_requires_security() -> None:
    schema = app.openapi()
    op = (schema.get("paths") or {}).get("/api/articles/{slug}/comments", {}).get("post")
    assert op is not None
    assert op.get("security"), "POST comments must require auth"


def test_article_admin_get_requires_security() -> None:
    schema = app.openapi()
    op = (schema.get("paths") or {}).get("/api/articles/id/{article_id}", {}).get("get")
    assert op is not None
    assert op.get("security"), "GET editor article must require auth"


def test_article_list_query_has_search_and_sort() -> None:
    schema = app.openapi()
    params = (
        (schema.get("paths") or {}).get("/api/articles", {}).get("get", {}).get("parameters")
        or []
    )
    names = {item.get("name") for item in params}
    assert "q" in names
    assert "sort" in names
    props = (
        (schema.get("components") or {})
        .get("schemas", {})
        .get("ArticleListItemOut", {})
        .get("properties", {})
    )
    assert "comment_count" in props
    cats = props.get("categories") or {}
    ref = (cats.get("items") or {}).get("$ref", "")
    assert ref.endswith("ArticleCategoryOut")


def test_article_category_schema_has_admin_and_chip() -> None:
    schema = app.openapi()
    props = (
        (schema.get("components") or {})
        .get("schemas", {})
        .get("ArticleCategoryOut", {})
        .get("properties", {})
    )
    assert "admin_only" in props
    assert "chip_color" in props


def test_article_mine_and_authors_require_security() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    mine = (paths.get("/api/articles/mine") or {}).get("get")
    authors = (paths.get("/api/articles/authors") or {}).get("put")
    restore = (
        paths.get("/api/articles/id/{article_id}/versions/{version_id}/restore") or {}
    ).get("post")
    assert mine and mine.get("security")
    assert authors and authors.get("security")
    assert restore and restore.get("security")
    recognize = (paths.get("/api/articles/math/recognize") or {}).get("post")
    assert recognize and recognize.get("security")
    assets = (paths.get("/api/articles/assets") or {}).get("post")
    assert assets and assets.get("security")
    props = (
        (schema.get("components") or {})
        .get("schemas", {})
        .get("ArticleAssetOut", {})
        .get("properties", {})
    )
    assert "url" in props
    assert "serial" in props
