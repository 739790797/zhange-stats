from app.services.articles.halo_parse import detect_halo_version, parse_halo1_posts, parse_halo2
from app.services.articles.service import FORMAT_HTML, FORMAT_MARKDOWN, STATUS_PUBLISHED


def test_detect_halo_version() -> None:
    assert detect_halo_version({"posts", "categories"}) == "halo1"
    assert detect_halo_version({"extensions", "flyway_schema_history"}) == "halo2"


def test_parse_halo1_markdown_post() -> None:
    posts = [
        {
            "id": 3,
            "title": "出门带什么",
            "slug": "raid-kit",
            "original_content": "## 清单\n- 水",
            "format_content": "<h2>清单</h2>",
            "status": 0,
            "type": 0,
            "summary": "摘要",
            "thumbnail": "/upload/cover.png",
            "create_time": 1_700_000_000_000,
            "create_from": 9,
            "editor_type": "markdown",
        }
    ]
    parsed = parse_halo1_posts(
        posts,
        categories_by_post={3: [("攻略", "guides")]},
        tags_by_post={3: [("塔科夫", "tarkov")]},
        owners_by_id={9: "alice"},
    )
    assert len(parsed) == 1
    art = parsed[0]
    assert art.source_id == "halo1:post:3"
    assert art.slug == "raid-kit"
    assert art.status == STATUS_PUBLISHED
    assert art.body.startswith("## 清单")
    assert art.body_format == FORMAT_MARKDOWN
    assert art.owner_key == "alice"
    assert art.categories == [("攻略", "guides")]


def test_parse_halo2_uses_snapshot_body() -> None:
    post_name = "post-uuid"
    snap_name = "snap-uuid"
    extensions = [
        (
            f"/registry/content.halo.run/posts/{post_name}",
            {
                "kind": "Post",
                "metadata": {"name": post_name},
                "spec": {
                    "title": "从快照来",
                    "slug": "from-snap",
                    "publish": True,
                    "releaseSnapshot": snap_name,
                    "owner": "bob",
                    "categories": ["cat-1"],
                    "excerpt": {"raw": "摘"},
                },
                "status": {"phase": "PUBLISHED"},
            },
        ),
        (
            f"/registry/content.halo.run/snapshots/{snap_name}",
            {
                "kind": "Snapshot",
                "metadata": {"name": snap_name},
                "spec": {
                    "rawType": "markdown",
                    "raw": "# 正文",
                    "content": "<h1>正文</h1>",
                },
            },
        ),
        (
            "/registry/content.halo.run/categories/cat-1",
            {
                "kind": "Category",
                "metadata": {"name": "cat-1"},
                "spec": {"displayName": "随笔", "slug": "notes"},
            },
        ),
    ]
    articles, comments = parse_halo2(extensions)
    assert comments == []
    assert len(articles) == 1
    art = articles[0]
    assert art.source_id == f"halo2:post:{post_name}"
    assert art.body == "# 正文"
    assert art.body_format == FORMAT_MARKDOWN
    assert art.owner_key == "bob"
    assert art.categories == [("随笔", "notes")]
    assert art.status == STATUS_PUBLISHED


def test_parse_halo2_html_snapshot() -> None:
    extensions = [
        (
            "/registry/content.halo.run/posts/p1",
            {
                "kind": "Post",
                "metadata": {"name": "p1"},
                "spec": {
                    "title": "HTML",
                    "slug": "html-post",
                    "publish": True,
                    "releaseSnapshot": "s1",
                },
                "status": {"phase": "PUBLISHED"},
            },
        ),
        (
            "/registry/content.halo.run/snapshots/s1",
            {
                "kind": "Snapshot",
                "metadata": {"name": "s1"},
                "spec": {"rawType": "HTML", "raw": "<p>hi</p>"},
            },
        ),
    ]
    articles, _ = parse_halo2(extensions)
    assert articles[0].body_format == FORMAT_HTML
    assert articles[0].body == "<p>hi</p>"
