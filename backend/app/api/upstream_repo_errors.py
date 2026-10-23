"""将上游数据仓未同步错误映射为前端可统一处理的 HTTP 错误。"""

from __future__ import annotations

from fastapi import HTTPException

from app.services.upstream_repos import RepoNotSyncedError

UPSTREAM_REPO_NOT_SYNCED_CODE = "UPSTREAM_REPO_NOT_SYNCED"


def upstream_repo_not_synced_http_error(
    exc: BaseException,
) -> HTTPException | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, RepoNotSyncedError):
            return HTTPException(
                status_code=503,
                detail={
                    "code": UPSTREAM_REPO_NOT_SYNCED_CODE,
                    "repo_id": current.repo_id,
                    "message": "所需的外部数据仓尚未同步，请先运行外部仓库更新。",
                },
                headers={"X-Upstream-Repo-State": "not-synced"},
            )
        current = current.__cause__ or current.__context__
    return None
