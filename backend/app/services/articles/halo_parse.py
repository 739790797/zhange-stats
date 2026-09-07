"""从 Halo 1 / 2 表行抽出文章与评论（纯函数，不连库）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.timeutil import BEIJING
from app.services.articles.service import FORMAT_HTML, FORMAT_MARKDOWN, STATUS_DRAFT, STATUS_PUBLISHED
from app.services.articles.slug import ensure_slug


@dataclass
class ParsedArticle:
    source_id: str
    slug: str
    title: str
    summary: str
    body: str
    body_format: str
    cover_url: str | None
    status: str
    published_at: datetime | None
    owner_key: str | None
    categories: list[tuple[str, str]] = field(default_factory=list)
    tags: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ParsedComment:
    source_id: str
    post_source_id: str
    body: str
    guest_name: str | None
    owner_key: str | None
    parent_source_id: str | None
    created_at: datetime | None


def detect_halo_version(table_names: set[str]) -> str:
    names = {n.lower() for n in table_names}
    if "extensions" in names:
        return "halo2"
    if "posts" in names:
        return "halo1"
    raise ValueError("无法识别 Halo 版本：库中既没有 extensions 也没有 posts")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return {}


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=BEIJING)
        return value
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=BEIJING)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING)
    return dt


def _halo1_status(raw: Any) -> str:
    if raw in (0, "0", "PUBLISHED", "published"):
        return STATUS_PUBLISHED
    if isinstance(raw, str) and raw.upper() == "PUBLISHED":
        return STATUS_PUBLISHED
    return STATUS_DRAFT


def _halo1_is_post(row: dict[str, Any]) -> bool:
    kind = row.get("type")
    if kind in (None, 0, "0", "post", "POST", "Post"):
        return True
    return False


def parse_halo1_posts(
    posts: list[dict[str, Any]],
    *,
    categories_by_post: dict[Any, list[tuple[str, str]]] | None = None,
    tags_by_post: dict[Any, list[tuple[str, str]]] | None = None,
    owners_by_id: dict[Any, str] | None = None,
) -> list[ParsedArticle]:
    out: list[ParsedArticle] = []
    categories_by_post = categories_by_post or {}
    tags_by_post = tags_by_post or {}
    owners_by_id = owners_by_id or {}
    for row in posts:
        if not _halo1_is_post(row):
            continue
        pid = row.get("id")
        title = str(row.get("title") or "未命名").strip()
        slug = ensure_slug(title, str(row.get("slug") or ""))
        original = str(row.get("original_content") or "")
        formatted = str(row.get("format_content") or "")
        editor = str(row.get("editor_type") or "markdown").lower()
        if original.strip():
            body = original
            body_format = FORMAT_MARKDOWN if "html" not in editor else FORMAT_HTML
        else:
            body = formatted
            body_format = FORMAT_HTML if formatted.strip() else FORMAT_MARKDOWN
        owner = owners_by_id.get(row.get("create_from") or row.get("createFrom"))
        if not owner:
            owner = row.get("create_from") or row.get("owner")
            owner = str(owner) if owner is not None else None
        published = _parse_dt(row.get("create_time") or row.get("createTime"))
        out.append(
            ParsedArticle(
                source_id=f"halo1:post:{pid}",
                slug=slug,
                title=title,
                summary=str(row.get("summary") or "")[:512],
                body=body,
                body_format=body_format,
                cover_url=(str(row.get("thumbnail") or "").strip() or None),
                status=_halo1_status(row.get("status")),
                published_at=published,
                owner_key=str(owner) if owner else None,
                categories=list(categories_by_post.get(pid) or []),
                tags=list(tags_by_post.get(pid) or []),
            )
        )
    return out


def parse_halo1_comments(rows: list[dict[str, Any]]) -> list[ParsedComment]:
    out: list[ParsedComment] = []
    for row in rows:
        pid = row.get("post_id") or row.get("postId")
        cid = row.get("id")
        if pid is None or cid is None:
            continue
        status = row.get("status")
        if status not in (None, 0, 1, "0", "1", "PUBLISHED", "published"):
            continue
        parent = row.get("parent_id") or row.get("parentId")
        out.append(
            ParsedComment(
                source_id=f"halo1:comment:{cid}",
                post_source_id=f"halo1:post:{pid}",
                body=str(row.get("content") or row.get("body") or "").strip(),
                guest_name=str(row.get("author") or "").strip() or None,
                owner_key=str(row.get("email") or "").strip() or None,
                parent_source_id=f"halo1:comment:{parent}" if parent not in (None, 0, "0") else None,
                created_at=_parse_dt(row.get("create_time") or row.get("createTime")),
            )
        )
    return out


def _decode_extension_blob(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, (bytes, bytearray)):
        return _as_dict(data)
    if isinstance(data, str):
        return _as_dict(data)
    return {}


def _halo2_body_from_snapshot(snap: dict[str, Any]) -> tuple[str, str]:
    spec = snap.get("spec") or {}
    raw_type = str(spec.get("rawType") or spec.get("raw_type") or "markdown").lower()
    raw = spec.get("raw") or spec.get("content") or ""
    if isinstance(raw, dict):
        raw = raw.get("content") or raw.get("raw") or ""
    body = str(raw or "")
    html = str(spec.get("content") or "")
    if "html" in raw_type or raw_type == "richtext":
        return (body or html, FORMAT_HTML)
    return (body or html, FORMAT_MARKDOWN)


def parse_halo2(
    extensions: list[tuple[str, Any]],
) -> tuple[list[ParsedArticle], list[ParsedComment]]:
    """extensions: (name, data_blob) 来自 Halo 2 `extensions` 表。"""
    posts: dict[str, dict[str, Any]] = {}
    snapshots: dict[str, dict[str, Any]] = {}
    categories: dict[str, dict[str, Any]] = {}
    tags: dict[str, dict[str, Any]] = {}
    comments: list[dict[str, Any]] = []

    for name, blob in extensions:
        key = str(name or "")
        data = _decode_extension_blob(blob)
        kind = str(data.get("kind") or "")
        if "/posts/" in key or kind == "Post":
            meta = (data.get("metadata") or {}).get("name") or key.rsplit("/", 1)[-1]
            posts[str(meta)] = data
        elif "/snapshots/" in key or kind == "Snapshot":
            meta = (data.get("metadata") or {}).get("name") or key.rsplit("/", 1)[-1]
            snapshots[str(meta)] = data
        elif "/categories/" in key or kind == "Category":
            meta = (data.get("metadata") or {}).get("name") or key.rsplit("/", 1)[-1]
            categories[str(meta)] = data
        elif "/tags/" in key or kind == "Tag":
            meta = (data.get("metadata") or {}).get("name") or key.rsplit("/", 1)[-1]
            tags[str(meta)] = data
        elif "/comments/" in key or kind == "Comment":
            comments.append(data)

    def term_pair(store: dict[str, dict[str, Any]], ref: str) -> tuple[str, str] | None:
        node = store.get(ref)
        if not node:
            return None
        spec = node.get("spec") or {}
        name = str(spec.get("displayName") or spec.get("name") or ref)
        slug = str(spec.get("slug") or ensure_slug(name, ref))
        return name, slug

    articles: list[ParsedArticle] = []
    for post_name, data in posts.items():
        spec = data.get("spec") or {}
        status = data.get("status") or {}
        title = str(spec.get("title") or "未命名").strip()
        slug = ensure_slug(title, str(spec.get("slug") or ""))
        excerpt = spec.get("excerpt") or {}
        summary = ""
        if isinstance(excerpt, dict):
            summary = str(excerpt.get("raw") or status.get("excerpt") or "")
        else:
            summary = str(excerpt or status.get("excerpt") or "")
        snap_name = spec.get("releaseSnapshot") or spec.get("headSnapshot")
        body = str(spec.get("content") or "")
        body_format = FORMAT_MARKDOWN
        if snap_name and str(snap_name) in snapshots:
            body, body_format = _halo2_body_from_snapshot(snapshots[str(snap_name)])
        phase = str(status.get("phase") or "")
        published = bool(spec.get("publish")) or phase.upper() == "PUBLISHED"
        owner = spec.get("owner")
        if isinstance(owner, dict):
            owner_key = str(owner.get("name") or owner.get("displayName") or "") or None
        else:
            owner_key = str(owner) if owner else None
        cat_pairs = []
        for ref in spec.get("categories") or []:
            pair = term_pair(categories, str(ref))
            if pair:
                cat_pairs.append(pair)
        tag_pairs = []
        for ref in spec.get("tags") or []:
            pair = term_pair(tags, str(ref))
            if pair:
                tag_pairs.append(pair)
        articles.append(
            ParsedArticle(
                source_id=f"halo2:post:{post_name}",
                slug=slug,
                title=title,
                summary=summary[:512],
                body=body,
                body_format=body_format,
                cover_url=(str(spec.get("cover") or "").strip() or None),
                status=STATUS_PUBLISHED if published else STATUS_DRAFT,
                published_at=_parse_dt(spec.get("publishTime") or status.get("lastModifyTime")),
                owner_key=owner_key,
                categories=cat_pairs,
                tags=tag_pairs,
            )
        )

    parsed_comments: list[ParsedComment] = []
    for data in comments:
        spec = data.get("spec") or {}
        meta = (data.get("metadata") or {}).get("name")
        subject = spec.get("subjectRef") or {}
        post_name = str(subject.get("name") or "")
        if not meta or not post_name:
            continue
        owner = spec.get("owner") or {}
        display = ""
        owner_key = None
        if isinstance(owner, dict):
            display = str(owner.get("displayName") or owner.get("name") or "")
            owner_key = str(owner.get("name") or owner.get("email") or "") or None
        parsed_comments.append(
            ParsedComment(
                source_id=f"halo2:comment:{meta}",
                post_source_id=f"halo2:post:{post_name}",
                body=str(spec.get("content") or spec.get("raw") or "").strip(),
                guest_name=display or None,
                owner_key=owner_key,
                parent_source_id=(
                    f"halo2:comment:{spec.get('quoteCommentName')}"
                    if spec.get("quoteCommentName")
                    else None
                ),
                created_at=_parse_dt((data.get("metadata") or {}).get("creationTimestamp")),
            )
        )
    return articles, parsed_comments
