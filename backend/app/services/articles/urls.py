"""改写 Halo 正文里的配图 URL。"""

from __future__ import annotations

import re
from pathlib import Path

_MD_OR_HTML_URL = re.compile(
    r"""(?P<prefix>(?:src|href)\s*=\s*["']|!\[[^\]]*\]\()(?P<url>[^"')\s]+)(?P<suffix>["')])""",
    re.IGNORECASE,
)


def halo_rel_key(url: str) -> str | None:
    """从 Halo 站内 URL 抽出 upload 相对路径，外链返回 None。"""
    raw = (url or "").strip()
    if not raw or raw.startswith("data:") or raw.startswith("#"):
        return None
    path = raw.split("?", 1)[0].split("#", 1)[0]
    if "://" in path:
        path = path.split("://", 1)[1]
        slash = path.find("/")
        path = path[slash:] if slash >= 0 else ""
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    for marker in ("/upload/", "/uploads/"):
        idx = lower.find(marker)
        if idx >= 0:
            rel = normalized[idx + len(marker) :]
            return rel or None
    stripped = normalized.lstrip("/")
    if stripped.lower().startswith("upload/"):
        return stripped[7:] or None
    if stripped.lower().startswith("uploads/"):
        return stripped[8:] or None
    return None


def public_article_url(rel_key: str) -> str:
    rel = rel_key.replace("\\", "/").lstrip("/")
    return f"/uploads/articles/halo/{rel}"


def rewrite_body_urls(body: str, mapping: dict[str, str]) -> str:
    """mapping: halo 相对路径 -> 本站公开 URL。"""
    if not body or not mapping:
        return body

    def repl(match: re.Match[str]) -> str:
        url = match.group("url")
        key = halo_rel_key(url)
        if key and key in mapping:
            return f"{match.group('prefix')}{mapping[key]}{match.group('suffix')}"
        if url in mapping:
            return f"{match.group('prefix')}{mapping[url]}{match.group('suffix')}"
        return match.group(0)

    return _MD_OR_HTML_URL.sub(repl, body)


def copy_halo_uploads(src_dir: Path, dest_root: Path) -> dict[str, str]:
    """复制 Halo 上传目录，返回 相对路径 -> /uploads/articles/halo/... 。"""
    mapping: dict[str, str] = {}
    if not src_dir.is_dir():
        return mapping
    dest_halo = dest_root / "halo"
    for path in src_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src_dir).as_posix()
        target = dest_halo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(path.read_bytes())
        mapping[rel] = public_article_url(rel)
    return mapping
