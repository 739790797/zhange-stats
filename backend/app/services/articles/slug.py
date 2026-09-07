"""文章 slug 规范化。"""

from __future__ import annotations

import re
import unicodedata

RESERVED_SLUGS = frozenset(
    {
        "admin",
        "assets",
        "categories",
        "comments",
        "id",
        "manage",
        "new",
        "tags",
        "write",
        "mine",
        "authors",
        "versions",
        "restore",
        "capabilities",
    }
)

_SLUG_KEEP = re.compile(r"[^a-z0-9\-]+")
_MULTI_DASH = re.compile(r"-{2,}")


def slugify(text: str) -> str:
    raw = unicodedata.normalize("NFKC", (text or "").strip()).lower()
    raw = raw.replace(" ", "-").replace("_", "-")
    raw = _SLUG_KEEP.sub("-", raw)
    raw = _MULTI_DASH.sub("-", raw).strip("-")
    return raw[:191]


def is_reserved_slug(slug: str) -> bool:
    return slug.strip().lower() in RESERVED_SLUGS


def ensure_slug(title: str, explicit: str | None = None) -> str:
    candidate = slugify(explicit or "") or slugify(title)
    if not candidate:
        candidate = "post"
    return candidate
