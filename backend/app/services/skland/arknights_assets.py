"""方舟资源仓里的图片，由本站从本地克隆读出。"""

from __future__ import annotations

import re

from app.services.upstream_repos import (
    REPO_ARKNIGHTS,
    RepoPathError,
    ensure_repo,
    resolve_repo_file,
)

ASSET_URL_PREFIX = "/api/skland/arknights/assets"
_KINDS = frozenset({"avatar", "item", "portrait"})
_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def asset_url(kind: str, name: str) -> str:
    return f"{ASSET_URL_PREFIX}/{kind}/{name}"


def resolve_asset(kind: str, name: str):
    if kind not in _KINDS or not _NAME.fullmatch(name or ""):
        raise RepoPathError("路径越界")
    ensure_repo(REPO_ARKNIGHTS)
    return resolve_repo_file(REPO_ARKNIGHTS, f"{kind}/{name}")
