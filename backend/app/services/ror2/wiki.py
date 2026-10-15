"""雨中冒险 2：Wiki 模块落 guide_raws，读库后再解析成图鉴。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.database import SessionLocal
from app.core.http_client import HttpRequestError, http_request
from app.core.timeutil import now_naive
from app.models.job_run import JobRun
from app.services.guide_raw.lock import SyncBusy
from app.services.guide_raw.pipeline import GuideRawPipeline, RawSpec
from app.services.job_runs_prune import fail_job_run
from app.services.ror2.catalog import (
    WIKI_ORIGIN,
    Ror2WikiError,
    items_from_module,
    survivors_from_module,
)
from app.services.ror2.schemas import Ror2CatalogOut

log = logging.getLogger("zhange.ror2")

WIKI_API = f"{WIKI_ORIGIN}/api.php"
USER_AGENT = "ZhangeStats/ror2 (Risk of Rain 2 catalog; +https://riskofrain2.wiki.gg/)"
JOB_KEY = "ror2_wiki_sync"
_LOG_KEY = "ror2-wiki"

_MEMO: dict[str, Ror2CatalogOut] = {}
_retry_not_before = 0.0
_COLD_START_RETRY_SEC = 60.0


def _latest_synced(token: str) -> str:
    times = [part.partition("@")[2] for part in token.split("|") if "@" in part]
    return max(times) if times else ""


def reset_catalog_memo() -> None:
    global _retry_not_before
    _MEMO.clear()
    _retry_not_before = 0.0


def _accept_items(body: str) -> None:
    items_from_module(body)


def _accept_equipment(body: str) -> None:
    items_from_module(body, default_rarity="Equipment")


def _accept_survivors(body: str) -> None:
    survivors_from_module(body)


def _spec(resource: str, title: str, accept: Callable[[str], None]) -> RawSpec:
    return RawSpec(
        resource=resource,
        source=f"{WIKI_ORIGIN}/wiki/{title}",
        fetch=lambda title=title: fetch_module(title),
        accept=accept,
    )


PIPELINE = GuideRawPipeline(
    "ror2",
    (
        _spec("items", "Module:Items/Data", _accept_items),
        _spec("equipment", "Module:Equipment/Data", _accept_equipment),
        _spec("survivors", "Module:Survivors/Data", _accept_survivors),
    ),
)


def sync_wiki(db: Session, *, fetch: Callable[[RawSpec], str] | None = None) -> list[dict[str, object]]:
    """回源三份模块。一份不合格就不覆盖那一行。"""
    results = PIPELINE.sync(db, fetch=fetch)
    failed = [row for row in results if not row["ok"]]
    if failed:
        detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed)
        log_until_change(log, _LOG_KEY, "雨中冒险2图鉴同步未完成：%s", detail)
        raise Ror2WikiError(detail)
    clear_log_until_change(_LOG_KEY)
    changed = [str(row["resource"]) for row in results if row["changed"]]
    log.info("雨中冒险2图鉴已落库：%s", "、".join(changed) if changed else "内容未变")
    reset_catalog_memo()
    return results


def get_catalog(db: Session, *, fetch: Callable[[RawSpec], str] | None = None) -> Ror2CatalogOut:
    """读库解析。库是空的才冷启动回源；已有数据就等定时任务更新。"""
    if PIPELINE.missing(db):
        if time.monotonic() < _retry_not_before:
            raise Ror2WikiError("图鉴还没有同步")
        try:
            PIPELINE.gate.fill_once(db, lambda: PIPELINE.missing(db), lambda: sync_wiki(db, fetch=fetch))
        except SyncBusy as exc:
            raise Ror2WikiError(exc.message) from exc
        except Ror2WikiError:
            _remember_cold_start_failure()
            raise
    if PIPELINE.missing(db):
        _remember_cold_start_failure()
        raise Ror2WikiError("图鉴还没有同步")
    token = PIPELINE.revision(db)
    cached = _MEMO.get(token)
    if cached is not None:
        return cached
    texts = PIPELINE.load_texts(db)
    catalog = Ror2CatalogOut(
        source=f"{WIKI_ORIGIN}/",
        fetched_at=_latest_synced(token),
        items=items_from_module(texts["items"]),
        equipment=items_from_module(texts["equipment"], default_rarity="Equipment"),
        survivors=survivors_from_module(texts["survivors"]),
    )
    _MEMO.clear()
    _MEMO[token] = catalog
    return catalog


def _remember_cold_start_failure() -> None:
    global _retry_not_before
    _retry_not_before = time.monotonic() + _COLD_START_RETRY_SEC


def sync_job() -> None:
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running", started_at=now_naive())
    db.add(job)
    db.commit()
    run_id = job.id
    try:
        try:
            with PIPELINE.gate.exclusive():
                results = sync_wiki(db)
        except SyncBusy:
            job.status = "ok"
            job.message = "已有同步在跑"
            job.finished_at = now_naive()
            db.commit()
            return
        job.status = "ok"
        job.message = "、".join(
            f"{row['resource']}{' 已更新' if row['changed'] else ' 未变'}" for row in results
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.exception("雨中冒险2图鉴同步失败")
        fail_job_run(db, run_id, str(exc))
    finally:
        db.close()


def fetch_module(title: str) -> str:
    """只请求 wiki.gg 的 api.php。"""
    if not title.startswith("Module:"):
        raise Ror2WikiError(f"拒绝的模块名 {title}")
    try:
        response = http_request(
            "GET",
            WIKI_API,
            params={
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvslots": "main",
                "rvprop": "content",
                "format": "json",
                "formatversion": "2",
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=30,
        )
    except HttpRequestError as exc:
        raise Ror2WikiError(f"{title} 请求失败：{exc}") from exc
    if response.status_code != 200:
        raise Ror2WikiError(f"{title} HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise Ror2WikiError(f"{title} 响应不是 JSON") from exc
    return module_text(payload, title)


def module_text(payload: object, title: str) -> str:
    if not isinstance(payload, dict):
        raise Ror2WikiError(f"{title} 响应格式不对")
    query = payload.get("query")
    pages = query.get("pages") if isinstance(query, dict) else None
    if not isinstance(pages, list) or not pages or not isinstance(pages[0], dict):
        raise Ror2WikiError(f"{title} 没有页面")
    page = pages[0]
    if page.get("missing"):
        raise Ror2WikiError(f"wiki 没有 {title}")
    revisions = page.get("revisions")
    if not isinstance(revisions, list) or not revisions or not isinstance(revisions[0], dict):
        raise Ror2WikiError(f"{title} 没有修订")
    slots = revisions[0].get("slots")
    main = slots.get("main") if isinstance(slots, dict) else None
    content = main.get("content") if isinstance(main, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise Ror2WikiError(f"{title} 正文为空")
    return content
