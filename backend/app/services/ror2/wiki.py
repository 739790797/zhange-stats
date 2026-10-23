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
from app.services.guide_raw.codec import unpack_raw_text
from app.services.guide_raw.lock import SyncBusy
from app.services.guide_raw.pipeline import GuideRawPipeline, RawSpec, load_row, upsert_raw
from app.services.job_runs_prune import fail_job_run
from app.services.ror2.catalog import (
    WIKI_ORIGIN,
    Ror2WikiError,
    artifacts_from_module,
    challenges_from_module,
    drones_from_module,
    environments_from_module,
    interactables_from_module,
    items_from_module,
    monsters_from_module,
    survivors_from_module,
    wiki_page_url,
)
from app.services.ror2.schemas import (
    Ror2CatalogOut,
    Ror2CatalogResponse,
    Ror2SurvivorDetailOut,
    Ror2SurvivorDetailResponse,
)
from app.services.ror2.survivor_page import (
    Ror2MissingSurvivor,
    accept_survivor_page,
    build_survivor_detail,
    lore_table,
    lore_text,
    skills_table,
    survivor_page_resource,
)
from app.services.ror2.wiki_structure import (
    ArticleSource,
    WIKI_ARTICLE_TITLES,
    WIKI_EXPANSION_TITLES,
    article_resource,
    expansion_resource,
    parse_article,
    parse_expansion_article,
    WikiStructureError,
)

log = logging.getLogger("zhange.ror2")

WIKI_API = f"{WIKI_ORIGIN}/api.php"
USER_AGENT = "ZhangeStats/ror2 (Risk of Rain 2 catalog; +https://riskofrain2.wiki.gg/)"
JOB_KEY = "ror2_wiki_sync"
_LOG_KEY = "ror2-wiki"

_MEMO: dict[str, Ror2CatalogOut] = {}
_retry_not_before = 0.0
_COLD_START_RETRY_SEC = 60.0
_WIKI_RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})
_WIKI_HTTP_ATTEMPTS = 2
_WIKI_HTTP_RETRY_DELAY_SEC = 1.0


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


def _accept_enemies(body: str) -> None:
    monsters_from_module(body)
    drones_from_module(body)


def _accept_environments(body: str) -> None:
    environments_from_module(body)


def _accept_challenges(body: str) -> None:
    challenges_from_module(body)


def _accept_interactables(body: str) -> None:
    interactables_from_module(body)


def _accept_artifacts(body: str) -> None:
    artifacts_from_module(body)


def _accept_skills(body: str) -> None:
    skills_table(body)


def _accept_lore(body: str) -> None:
    lore_table(body)


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
        _spec("enemies", "Module:Enemies/Data", _accept_enemies),
        _spec("environments", "Module:Environments/Data", _accept_environments),
        _spec("challenges", "Module:Challenges/Data", _accept_challenges),
        _spec("interactables", "Module:Interactables/Data", _accept_interactables),
        _spec("artifacts", "Module:Artifacts/Data", _accept_artifacts),
        _spec("skills", "Module:Skills/Data", _accept_skills),
        _spec("lore", "Module:Lore/Data", _accept_lore),
    ),
)

MODULE_NAMESPACE = "828"
_MODULE_LIST_PAGES = 20


def pipeline_module_titles() -> dict[str, str]:
    """图鉴会解析的模块。键是 Wiki 标题，值是 guide_raws 的 resource。"""
    prefix = f"{WIKI_ORIGIN}/wiki/"
    return {spec.source.removeprefix(prefix): spec.resource for spec in PIPELINE.specs}


def module_resource(title: str) -> str:
    """图鉴不解析的模块。resource 最长 64。"""
    if not title.startswith("Module:"):
        raise Ror2WikiError(f"拒绝的模块名 {title}")
    resource = f"module/{title.removeprefix('Module:')}"
    if len(resource) > 64:
        raise Ror2WikiError(f"模块名太长：{title}")
    return resource


def accept_extra_module(body: str) -> None:
    if not body.strip():
        raise Ror2WikiError("模块正文为空")


def module_titles_from_query(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise Ror2WikiError("模块列表响应格式不对")
    query = payload.get("query")
    pages = query.get("allpages") if isinstance(query, dict) else None
    if not isinstance(pages, list):
        raise Ror2WikiError("模块列表没有 allpages")
    titles: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            raise Ror2WikiError("模块列表有一条无法识别")
        title = page.get("title")
        if not isinstance(title, str) or not title.startswith("Module:"):
            raise Ror2WikiError(f"模块列表里有不是模块的标题：{title!r}")
        titles.append(title)
    return titles


def list_module_titles() -> list[str]:
    """Module 命名空间里的每一页。只走 api.php。"""
    params: dict[str, str] = {
        "action": "query",
        "list": "allpages",
        "apnamespace": MODULE_NAMESPACE,
        "aplimit": "500",
        "format": "json",
        "formatversion": "2",
    }
    titles: list[str] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for _ in range(_MODULE_LIST_PAGES):
        try:
            response = http_request(
                "GET",
                WIKI_API,
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=30,
            )
        except HttpRequestError as exc:
            raise Ror2WikiError(f"模块列表请求失败：{exc}") from exc
        if response.status_code != 200:
            raise Ror2WikiError(f"模块列表 HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise Ror2WikiError("模块列表响应不是 JSON") from exc
        titles.extend(module_titles_from_query(payload))
        cont = payload.get("continue") if isinstance(payload, dict) else None
        if not isinstance(cont, dict) or not cont:
            return titles
        key = tuple(sorted((str(name), str(value)) for name, value in cont.items()))
        if key in seen:
            raise Ror2WikiError("模块列表分页重复")
        seen.add(key)
        params = {**params, **{str(name): str(value) for name, value in cont.items()}}
    raise Ror2WikiError("模块列表分页没有结束")


def sync_extra_modules(
    db: Session,
    titles: list[str],
    *,
    fetch: Callable[[RawSpec], str] | None = None,
) -> list[dict[str, object]]:
    """图鉴名单以外的模块也各存一行。一份失败不覆盖旧行，也不挡住其余模块。"""
    known = pipeline_module_titles()
    results: list[dict[str, object]] = []
    for title in titles:
        if title in known:
            continue
        resource = title
        try:
            if _rejected_title(title):
                raise Ror2WikiError(f"拒绝的模块名 {title}")
            resource = module_resource(title)
            spec = RawSpec(
                resource,
                f"{WIKI_ORIGIN}/wiki/{title}",
                lambda title=title: fetch_module(title),
                accept_extra_module,
            )
            body = fetch(spec) if fetch else spec.fetch()
            accept_extra_module(body)
            saved = upsert_raw(db, "ror2", resource, spec.source, body)
            results.append({**saved, "ok": True, "error": None})
        except Exception as exc:  # noqa: BLE001 — 一份失败留给其余模块
            db.rollback()
            results.append({"resource": resource, "ok": False, "changed": False, "error": str(exc)})
    return results


def sync_wiki(
    db: Session,
    *,
    fetch: Callable[[RawSpec], str] | None = None,
    list_modules: Callable[[], list[str]] | None = None,
) -> list[dict[str, object]]:
    """回源图鉴用的模块。传了 list_modules 时，再把 Module 命名空间里其余页面一并落库。"""
    results = PIPELINE.sync(db, fetch=fetch)
    failed = [row for row in results if not row["ok"]]
    if failed:
        detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed)
        log_until_change(log, _LOG_KEY, "雨中冒险2图鉴同步未完成：%s", detail)
        raise Ror2WikiError(detail)
    if list_modules is not None:
        extras = sync_extra_modules(db, list_modules(), fetch=fetch)
        failed_extras = [row for row in extras if not row["ok"]]
        changed = [str(row["resource"]) for row in extras if row["changed"]]
        unchanged = len(extras) - len(changed) - len(failed_extras)
        summary = f"其余模块 {len(extras)} 份"
        if changed:
            summary += "，更新 " + "、".join(changed)
        if unchanged:
            summary += f"，未变 {unchanged}"
        results.append({"resource": summary, "changed": bool(changed), "ok": not failed_extras, "error": None})
        if failed_extras:
            detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed_extras)
            log_until_change(log, _LOG_KEY, "雨中冒险2其余模块同步未完成：%s", detail)
            raise Ror2WikiError(detail)
    clear_log_until_change(_LOG_KEY)
    changed = [str(row["resource"]) for row in results if row["changed"]]
    log.info("雨中冒险2图鉴已落库：%s", "、".join(changed) if changed else "内容未变")
    reset_catalog_memo()
    return results


def _catalog_with_units(db: Session):
    from app.services.ror2.strings import apply_catalog
    from app.services.ror2.weblate import load_snapshot

    # get_catalog 只解析 Wiki 原文并缓存；深拷贝后再叠加令牌译文，避免译文污染缓存。
    catalog = get_catalog(db).model_copy(deep=True)
    snapshot = load_snapshot(db)
    apply_catalog(catalog, snapshot.units, snapshot.sources)
    return catalog, snapshot


def stored_wiki_articles(db: Session) -> list[ArticleSource]:
    """读已同步的 Wiki 文章结构，以及 DLC 页的标题单元；不投影 DLC 正文结构。"""
    articles: list[ArticleSource] = []
    for title in WIKI_ARTICLE_TITLES:
        resource = article_resource(title)
        row = load_row(db, "ror2", resource, with_body=True)
        if row is None:
            continue
        try:
            articles.append(parse_article(resource, title, unpack_raw_text(row.raw_body)))
        except (Ror2WikiError, ValueError) as exc:
            log_until_change(log, _LOG_KEY, "雨中冒险2 Wiki 结构解析失败：%s：%s", title, str(exc))
    for code, title in WIKI_EXPANSION_TITLES.items():
        resource = expansion_resource(code)
        row = load_row(db, "ror2", resource, with_body=True)
        if row is None:
            continue
        try:
            articles.append(parse_expansion_article(resource, unpack_raw_text(row.raw_body)))
        except (Ror2WikiError, ValueError) as exc:
            log_until_change(log, _LOG_KEY, "雨中冒险2资料片 Wiki 标题解析失败：%s：%s", title, str(exc))
    return articles


def translated_catalog(db: Session) -> Ror2CatalogResponse:
    """Wiki 原文为底稿；只有真实源 context 存在时才附令牌，译文还须已审且指纹匹配。"""
    from app.services.ror2.projection import catalog_response

    catalog, snapshot = _catalog_with_units(db)
    return catalog_response(catalog, snapshot.sources, snapshot.units, stored_wiki_articles(db))


def translated_detail(db: Session, name: str) -> Ror2SurvivorDetailResponse:
    """幸存者详情按相同令牌边界投影；未匹配 source 的 Wiki 内容不带交互令牌。"""
    from app.services.ror2.projection import detail_response
    from app.services.ror2.weblate import load_snapshot

    detail = get_survivor_detail(db, name)
    snapshot = load_snapshot(db)
    return detail_response(detail, snapshot.sources, snapshot.units)

def catalog_from_db(db: Session) -> Ror2CatalogOut:
    """读已落库模块并关联日志原文，不套译文。"""
    texts = PIPELINE.load_texts(db)
    items = items_from_module(texts["items"])
    equipment = items_from_module(texts["equipment"], default_rarity="Equipment")
    lore = lore_table(texts["lore"])
    for row in (*items, *equipment):
        row.lore = lore_text(lore, row.name)
    return Ror2CatalogOut(
        source=f"{WIKI_ORIGIN}/",
        fetched_at=_latest_synced(PIPELINE.revision(db)),
        items=items,
        equipment=equipment,
        survivors=survivors_from_module(texts["survivors"]),
        monsters=monsters_from_module(texts["enemies"]),
        drones=drones_from_module(texts["enemies"]),
        environments=environments_from_module(texts["environments"]),
        challenges=challenges_from_module(texts["challenges"]),
        interactables=interactables_from_module(texts["interactables"]),
        artifacts=artifacts_from_module(texts["artifacts"]),
    )


def stored_survivor_details(db: Session, catalog: Ror2CatalogOut) -> list[Ror2SurvivorDetailOut]:
    """只解析已经落库的幸存者词条，缺页留给图鉴同步。"""
    if PIPELINE.missing(db):
        return []
    texts = PIPELINE.load_texts(db)
    skills = skills_table(texts["skills"])
    lore = lore_table(texts["lore"])
    details: list[Ror2SurvivorDetailOut] = []
    for survivor in catalog.survivors:
        row = load_row(db, "ror2", survivor_page_resource(survivor.name), with_body=True)
        if row is None:
            continue
        try:
            details.append(build_survivor_detail(survivor, unpack_raw_text(row.raw_body), skills, lore))
        except (Ror2WikiError, ValueError):
            log_until_change(log, _LOG_KEY, "雨中冒险2幸存者词条跳过：%s", survivor.name)
    return details


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
    catalog = catalog_from_db(db)
    _MEMO.clear()
    _MEMO[token] = catalog
    return catalog


def get_survivor_detail(
    db: Session,
    name: str,
    *,
    fetch_page: Callable[[str], str] | None = None,
) -> Ror2SurvivorDetailOut:
    """词条不在库里时只补这一页；字段译文按当前令牌快照匹配，缺译文保留原文。"""
    catalog, snapshot = _catalog_with_units(db)
    survivor = next((row for row in catalog.survivors if row.name == name), None)
    if survivor is None:
        raise Ror2MissingSurvivor(name)
    texts = PIPELINE.load_texts(db)
    from app.services.ror2.strings import apply_detail

    page = _survivor_page_text(db, name, fetch_page=fetch_page)
    detail = build_survivor_detail(survivor, page, skills_table(texts["skills"]), lore_table(texts["lore"]))
    apply_detail(detail, snapshot.units, snapshot.sources)
    return detail

def _accept_wiki_article(title: str, body: str) -> None:
    if not body.strip():
        raise Ror2WikiError("Wiki 文章正文为空")
    try:
        parse_article(article_resource(title), title, body)
    except WikiStructureError as exc:
        raise Ror2WikiError(f"Wiki 文章结构无效：{exc}") from exc


def sync_wiki_articles(
    db: Session,
    *,
    fetch_page: Callable[[str], str] | None = None,
) -> list[dict[str, object]]:
    """同步页面实际引用的普通 Wiki 文章；每页失败都保留旧 raw。"""
    getter = fetch_page or fetch_wiki_text
    results: list[dict[str, object]] = []
    for title in WIKI_ARTICLE_TITLES:
        resource = article_resource(title)
        try:
            body = getter(title)
            _accept_wiki_article(title, body)
            saved = upsert_raw(db, "ror2", resource, wiki_page_url(title), body)
            results.append({**saved, "ok": True, "error": None})
        except Exception as exc:  # noqa: BLE001 — 普通文章逐页保存，失败保留旧 raw
            db.rollback()
            results.append({"resource": resource, "ok": False, "changed": False, "error": str(exc)})
    return results


def sync_wiki_expansion_pages(
    db: Session,
    *,
    fetch_page: Callable[[str], str] | None = None,
) -> list[dict[str, object]]:
    """缓存 DLC Wiki raw；只把每页标题解析为令牌源，失败保留旧 raw。"""
    getter = fetch_page or fetch_wiki_text
    results: list[dict[str, object]] = []
    for code, title in WIKI_EXPANSION_TITLES.items():
        resource = expansion_resource(code)
        try:
            body = getter(title)
            parse_expansion_article(resource, body)
            saved = upsert_raw(db, "ror2", resource, wiki_page_url(title), body)
            results.append({**saved, "ok": True, "error": None})
        except Exception as exc:  # noqa: BLE001 — 每页失败都保留旧 raw
            db.rollback()
            results.append({"resource": resource, "ok": False, "changed": False, "error": str(exc)})
    return results


def sync_survivor_pages(
    db: Session,
    *,
    fetch_page: Callable[[str], str] | None = None,
) -> list[dict[str, object]]:
    if PIPELINE.missing(db):
        return []
    texts = PIPELINE.load_texts(db)
    getter = fetch_page or fetch_wiki_text
    results: list[dict[str, object]] = []
    for survivor in survivors_from_module(texts["survivors"]):
        resource = survivor_page_resource(survivor.name)
        try:
            body = getter(survivor.name)
            accept_survivor_page(body)
            saved = upsert_raw(db, "ror2", resource, wiki_page_url(survivor.name), body)
            results.append({**saved, "ok": True, "error": None})
        except Exception as exc:  # noqa: BLE001 — 一页失败留给其余幸存者
            db.rollback()
            results.append({"resource": resource, "ok": False, "changed": False, "error": str(exc)})
    return results


def _survivor_page_text(
    db: Session,
    name: str,
    *,
    fetch_page: Callable[[str], str] | None,
) -> str:
    resource = survivor_page_resource(name)
    row = load_row(db, "ror2", resource, with_body=True)
    if row is not None:
        return unpack_raw_text(row.raw_body)
    getter = fetch_page or fetch_wiki_text
    body = getter(name)
    accept_survivor_page(body)
    upsert_raw(db, "ror2", resource, wiki_page_url(name), body)
    return body


def _remember_cold_start_failure() -> None:
    global _retry_not_before
    _retry_not_before = time.monotonic() + _COLD_START_RETRY_SEC


def sync_job() -> None:
    db = SessionLocal()
    from app.services.job_run_progress import create_or_reuse_job_run, versioned_job_stats

    job = create_or_reuse_job_run(
        db, JOB_KEY, message="正在同步图鉴数据", stats={"phase": "start"}
    )
    db.commit()
    run_id = job.id
    try:
        try:
            with PIPELINE.gate.exclusive():
                results = sync_wiki(db, list_modules=list_module_titles)
                pages = sync_survivor_pages(db)
                results.extend(pages)
                failed_pages = [row for row in pages if not row["ok"]]
                if failed_pages:
                    detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed_pages)
                    log_until_change(log, _LOG_KEY, "雨中冒险2幸存者词条同步未完成：%s", detail)
                    raise Ror2WikiError(detail)
                article_pages = sync_wiki_articles(db)
                results.extend(article_pages)
                failed_articles = [row for row in article_pages if not row["ok"]]
                if failed_articles:
                    detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed_articles)
                    log_until_change(log, _LOG_KEY, "雨中冒险2普通 Wiki 文章同步未完成：%s", detail)
                    raise Ror2WikiError(detail)
                expansion_pages = sync_wiki_expansion_pages(db)
                results.extend(expansion_pages)
                failed_expansions = [row for row in expansion_pages if not row["ok"]]
                if failed_expansions:
                    detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed_expansions)
                    log_until_change(log, _LOG_KEY, "雨中冒险2资料片 Wiki 标题同步未完成：%s", detail)
                    raise Ror2WikiError(detail)
        except SyncBusy:
            job.status = "ok"
            job.message = "已有同步在跑"
            job.stats = versioned_job_stats(
                JOB_KEY,
                status="ok",
                stats={"phase": "skip", "result": {"summary": job.message}},
                message=job.message,
            )
            job.finished_at = now_naive()
            db.commit()
            return
        job.status = "ok"
        job.message = "、".join(
            f"{row['resource']}{' 已更新' if row['changed'] else ' 未变'}" for row in results
        )
        job.stats = versioned_job_stats(
            JOB_KEY,
            status="ok",
            stats={
                "phase": "done",
                "result": {
                    "summary": f"图鉴同步完成，共处理 {len(results)} 项",
                    "counts": {
                        "updated": sum(1 for row in results if row.get("changed")),
                        "unchanged": sum(1 for row in results if not row.get("changed")),
                    },
                },
            },
            message=f"图鉴同步完成，共处理 {len(results)} 项",
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
    return fetch_wiki_text(title)


def fetch_wiki_text(title: str) -> str:
    """词条和模块都只走 api.php 的修订正文。"""
    if _rejected_title(title):
        raise Ror2WikiError(f"拒绝的页面名 {title}")
    for attempt in range(_WIKI_HTTP_ATTEMPTS):
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
        if (
            response.status_code not in _WIKI_RETRYABLE_STATUS_CODES
            or attempt + 1 == _WIKI_HTTP_ATTEMPTS
        ):
            break
        time.sleep(_WIKI_HTTP_RETRY_DELAY_SEC)
    if response.status_code != 200:
        raise Ror2WikiError(f"{title} HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise Ror2WikiError(f"{title} 响应不是 JSON") from exc
    return module_text(payload, title)


def _rejected_title(title: str) -> bool:
    if not title or title != title.strip():
        return True
    if any(char in title for char in "\n\r|[]{}#"):
        return True
    lowered = title.casefold()
    return lowered.startswith(("http://", "https://", "special:", "file:"))


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
