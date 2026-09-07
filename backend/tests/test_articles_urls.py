from pathlib import Path

from app.services.articles.urls import (
    copy_halo_uploads,
    halo_rel_key,
    public_article_url,
    rewrite_body_urls,
)


def test_halo_rel_key_strips_host_and_query() -> None:
    assert halo_rel_key("https://blog.example/upload/2020/01/a.png?x=1") == "2020/01/a.png"
    assert halo_rel_key("/upload/foo/bar.jpg") == "foo/bar.jpg"
    assert halo_rel_key("upload/foo.png") == "foo.png"
    assert halo_rel_key("https://cdn.example/img.png") is None


def test_rewrite_markdown_and_html_src() -> None:
    mapping = {"2020/01/a.png": public_article_url("2020/01/a.png")}
    md = "见 ![x](/upload/2020/01/a.png)"
    html = '<p><img src="/upload/2020/01/a.png"></p>'
    assert "/uploads/articles/halo/2020/01/a.png" in rewrite_body_urls(md, mapping)
    assert "/uploads/articles/halo/2020/01/a.png" in rewrite_body_urls(html, mapping)


def test_copy_halo_uploads(tmp_path: Path) -> None:
    src = tmp_path / "upload" / "2020"
    src.mkdir(parents=True)
    (src / "a.png").write_bytes(b"png")
    dest = tmp_path / "articles"
    mapping = copy_halo_uploads(tmp_path / "upload", dest)
    assert mapping["2020/a.png"] == "/uploads/articles/halo/2020/a.png"
    assert (dest / "halo" / "2020" / "a.png").read_bytes() == b"png"
