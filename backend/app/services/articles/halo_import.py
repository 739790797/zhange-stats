"""从临时 Halo 库导入文章到战鸽酒馆。

用法（在 backend/ 下）：

    python -m app.services.articles.halo_import \\
      --source-url mysql+pymysql://user:pass@127.0.0.1:3306/halo \\
      --author-map '{"halo用户名": 1}' \\
      --default-author-id 1 \\
      --uploads /path/to/halo/upload
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.timeutil import now_naive, to_naive
from app.models.articles import Article, ArticleComment
from app.models.user import User
from app.services.articles import service as articles_svc
from app.services.articles.errors import ArticleError
from app.services.articles.halo_parse import (
    ParsedArticle,
    ParsedComment,
    detect_halo_version,
    parse_halo1_comments,
    parse_halo1_posts,
    parse_halo2,
)
from app.services.articles.sanitize import normalize_cover_url, prepare_article_body
from app.services.articles.slug import ensure_slug
from app.services.articles.store import articles_dir
from app.services.articles.urls import copy_halo_uploads, rewrite_body_urls

logger = logging.getLogger("zhange.halo_import")


def _load_author_map(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    path = Path(raw)
    text_val = path.read_text(encoding="utf-8") if path.is_file() else raw
    data = json.loads(text_val)
    if not isinstance(data, dict):
        raise SystemExit("author-map 必须是 JSON 对象")
    out: dict[str, int] = {}
    for key, val in data.items():
        out[str(key).strip().lower()] = int(val)
    return out


def _resolve_author_id(
    owner_key: str | None,
    mapping: dict[str, int],
    default_id: int,
) -> int:
    if not owner_key:
        return default_id
    hit = mapping.get(owner_key.strip().lower())
    return hit if hit is not None else default_id


def _fetch_table(conn, table: str) -> list[dict[str, Any]]:
    insp = inspect(conn)
    names = {n.lower(): n for n in insp.get_table_names()}
    real = names.get(table.lower())
    if not real:
        return []
    rows = conn.execute(text(f"SELECT * FROM `{real}`")).mappings().all()
    return [dict(r) for r in rows]


def _load_halo1(conn) -> tuple[list[ParsedArticle], list[ParsedComment]]:
    posts = _fetch_table(conn, "posts")
    users = _fetch_table(conn, "users")
    owners = {}
    for u in users:
        uid = u.get("id")
        key = str(u.get("username") or u.get("email") or uid)
        owners[uid] = key
    cats = _fetch_table(conn, "categories")
    cat_by_id = {
        c.get("id"): (
            str(c.get("name") or c.get("slug") or c.get("id")),
            str(c.get("slug") or ensure_slug(str(c.get("name") or ""), "")),
        )
        for c in cats
    }
    post_cats = _fetch_table(conn, "post_categories")
    categories_by_post: dict[Any, list[tuple[str, str]]] = {}
    for link in post_cats:
        pid = link.get("post_id") or link.get("postId")
        cid = link.get("category_id") or link.get("categoryId")
        pair = cat_by_id.get(cid)
        if pid is None or pair is None:
            continue
        categories_by_post.setdefault(pid, []).append(pair)
    tags = _fetch_table(conn, "tags")
    tag_by_id = {
        t.get("id"): (
            str(t.get("name") or t.get("slug") or t.get("id")),
            str(t.get("slug") or ensure_slug(str(t.get("name") or ""), "")),
        )
        for t in tags
    }
    post_tags = _fetch_table(conn, "post_tags")
    tags_by_post: dict[Any, list[tuple[str, str]]] = {}
    for link in post_tags:
        pid = link.get("post_id") or link.get("postId")
        tid = link.get("tag_id") or link.get("tagId")
        pair = tag_by_id.get(tid)
        if pid is None or pair is None:
            continue
        tags_by_post.setdefault(pid, []).append(pair)
    articles = parse_halo1_posts(
        posts,
        categories_by_post=categories_by_post,
        tags_by_post=tags_by_post,
        owners_by_id=owners,
    )
    comments = parse_halo1_comments(_fetch_table(conn, "comments"))
    return articles, comments


def _load_halo2(conn) -> tuple[list[ParsedArticle], list[ParsedComment]]:
    rows = _fetch_table(conn, "extensions")
    pairs: list[tuple[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "")
        data = row.get("data")
        pairs.append((name, data))
    return parse_halo2(pairs)


def _upsert_article(
    db: Session,
    parsed: ParsedArticle,
    *,
    author_id: int,
    url_map: dict[str, str],
    dry_run: bool,
) -> Article | None:
    body = rewrite_body_urls(parsed.body, url_map)
    body = prepare_article_body(body, parsed.body_format)
    cover = parsed.cover_url
    if cover:
        from app.services.articles.urls import halo_rel_key

        key = halo_rel_key(cover)
        if key and key in url_map:
            cover = url_map[key]
    try:
        cover = normalize_cover_url(cover)
    except ArticleError:
        cover = None
    existing = (
        db.query(Article).filter(Article.halo_source_id == parsed.source_id).first()
    )
    cats = [
        articles_svc.ensure_category_by_slug(db, name=n, slug=s)
        for n, s in parsed.categories
    ]
    tags = [
        articles_svc.ensure_tag_by_slug(db, name=n, slug=s) for n, s in parsed.tags
    ]
    if dry_run:
        logger.info("dry-run article %s slug=%s title=%s", parsed.source_id, parsed.slug, parsed.title)
        return existing
    if existing:
        existing.title = parsed.title
        existing.summary = parsed.summary
        existing.body = body
        existing.body_format = parsed.body_format
        existing.cover_url = cover
        existing.status = parsed.status
        existing.author_user_id = author_id
        existing.published_at = (
            to_naive(parsed.published_at) if parsed.published_at else existing.published_at
        )
        existing.categories = cats
        existing.tags = tags
        existing.updated_at = now_naive()
        db.flush()
        articles_svc.append_version_if_changed(db, existing, actor_id=author_id)
        return existing
    slug = articles_svc._unique_slug(db, ensure_slug(parsed.title, parsed.slug))
    now = now_naive()
    row = Article(
        slug=slug,
        title=parsed.title,
        summary=parsed.summary,
        body=body,
        body_format=parsed.body_format,
        cover_url=cover,
        status=parsed.status,
        author_user_id=author_id,
        halo_source_id=parsed.source_id,
        published_at=to_naive(parsed.published_at) if parsed.published_at else None,
        created_at=now,
        updated_at=now,
    )
    if parsed.status == articles_svc.STATUS_PUBLISHED and row.published_at is None:
        row.published_at = now_naive()
    row.categories = cats
    row.tags = tags
    db.add(row)
    db.flush()
    articles_svc.append_version_if_changed(db, row, actor_id=author_id, force=True)
    return row


def _upsert_comments(
    db: Session,
    comments: list[ParsedComment],
    article_by_source: dict[str, Article],
    mapping: dict[str, int],
    default_id: int,
    dry_run: bool,
) -> None:
    by_source: dict[str, ArticleComment] = {}
    pending = list(comments)
    # 先无父、再有父
    pending.sort(key=lambda c: 1 if c.parent_source_id else 0)
    for parsed in pending:
        article = article_by_source.get(parsed.post_source_id)
        if article is None or not parsed.body:
            continue
        existing = (
            db.query(ArticleComment)
            .filter(
                ArticleComment.article_id == article.id,
                ArticleComment.body == parsed.body[:2000],
                ArticleComment.guest_name == (parsed.guest_name[:64] if parsed.guest_name else None),
            )
            .first()
        )
        if existing:
            by_source[parsed.source_id] = existing
            continue
        parent = by_source.get(parsed.parent_source_id or "")
        author_id = _resolve_author_id(parsed.owner_key, mapping, default_id)
        user = db.query(User).filter(User.id == author_id).first()
        if dry_run:
            logger.info("dry-run comment on %s", parsed.post_source_id)
            continue
        row = ArticleComment(
            article_id=article.id,
            user_id=user.id if user and parsed.owner_key and parsed.owner_key.lower() in mapping else None,
            guest_name=None if (user and parsed.owner_key and parsed.owner_key.lower() in mapping) else (parsed.guest_name or parsed.owner_key),
            body=parsed.body[:2000],
            parent_id=parent.id if parent and parent.parent_id is None else None,
            created_at=to_naive(parsed.created_at) if parsed.created_at else now_naive(),
        )
        db.add(row)
        db.flush()
        by_source[parsed.source_id] = row


def run_import(
    *,
    source_url: str,
    author_map: dict[str, int],
    default_author_id: int,
    uploads: Path | None,
    dry_run: bool,
    dest_db: Session | None = None,
) -> dict[str, int]:
    src_engine = create_engine(source_url)
    with src_engine.connect() as conn:
        version = detect_halo_version(set(inspect(conn).get_table_names()))
        logger.info("detected Halo %s", version)
        if version == "halo2":
            articles, comments = _load_halo2(conn)
        else:
            articles, comments = _load_halo1(conn)

    url_map: dict[str, str] = {}
    dest_root = articles_dir()
    if uploads is not None:
        url_map = copy_halo_uploads(uploads, dest_root)
        logger.info("copied %s halo upload files", len(url_map))

    db = dest_db or SessionLocal()
    own_session = dest_db is None
    stats = {"articles": 0, "comments": 0}
    try:
        author = db.query(User).filter(User.id == default_author_id).first()
        if author is None:
            raise SystemExit(f"default-author-id={default_author_id} 在本站不存在")
        article_by_source: dict[str, Article] = {}
        for parsed in articles:
            author_id = _resolve_author_id(parsed.owner_key, author_map, default_author_id)
            if parsed.owner_key and parsed.owner_key.strip().lower() not in author_map:
                logger.warning("unmapped author %s -> %s", parsed.owner_key, default_author_id)
            row = _upsert_article(
                db,
                parsed,
                author_id=author_id,
                url_map=url_map,
                dry_run=dry_run,
            )
            if row is not None:
                article_by_source[parsed.source_id] = row
            stats["articles"] += 1
        if not dry_run:
            db.flush()
            _upsert_comments(db, comments, article_by_source, author_map, default_author_id, dry_run)
            stats["comments"] = len(comments)
            db.commit()
        else:
            stats["comments"] = len(comments)
            db.rollback()
    finally:
        if own_session:
            db.close()
        src_engine.dispose()
    return stats


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="从 Halo 库导入战鸽酒馆文章")
    parser.add_argument("--source-url", required=True, help="Halo 临时库 SQLAlchemy URL")
    parser.add_argument("--author-map", default="", help="JSON 对象或 JSON 文件路径")
    parser.add_argument("--default-author-id", type=int, required=True)
    parser.add_argument("--uploads", default="", help="Halo upload/ 目录，可选")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    get_settings()  # 确保路径配置已加载
    stats = run_import(
        source_url=args.source_url,
        author_map=_load_author_map(args.author_map or None),
        default_author_id=args.default_author_id,
        uploads=Path(args.uploads) if args.uploads else None,
        dry_run=args.dry_run,
    )
    logger.info("done articles=%s comments=%s dry_run=%s", stats["articles"], stats["comments"], args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
