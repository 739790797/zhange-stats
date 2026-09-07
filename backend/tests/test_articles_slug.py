from app.services.articles.slug import ensure_slug, is_reserved_slug, slugify


def test_slugify_ascii_and_dash() -> None:
    assert slugify("Hello World") == "hello-world"
    assert slugify("  Foo__Bar  ") == "foo-bar"


def test_slugify_strips_cjk_to_empty_then_ensure_fallback() -> None:
    assert slugify("你好世界") == ""
    assert ensure_slug("你好世界", None) == "post"
    assert ensure_slug("你好", "My Post") == "my-post"


def test_reserved_slugs() -> None:
    assert is_reserved_slug("manage")
    assert is_reserved_slug("New")
    assert is_reserved_slug("write")
    assert is_reserved_slug("admin")
    assert not is_reserved_slug("raid-notes")
