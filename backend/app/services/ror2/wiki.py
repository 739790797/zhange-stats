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
from app.services.ror2.schemas import Ror2CatalogOut, Ror2SurvivorDetailOut
from app.services.ror2.survivor_page import (
    Ror2MissingSurvivor,
    accept_survivor_page,
    build_survivor_detail,
    lore_table,
    skills_table,
    survivor_page_resource,
)

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


def _table_or_empty(body: str | None, parser: Callable) -> dict:
    if not body:
        return {}
    try:
        table = parser(body)
    except (Ror2WikiError, ValueError):
        return {}
    return table if isinstance(table, dict) else {}


def _parsed_or_empty(resource: str, body: str | None, parser: Callable, default: list):
    if not body:
        return default
    try:
        return parser(body)
    except (Ror2WikiError, ValueError):
        log_until_change(log, _LOG_KEY, "雨中冒险2译文解析失败：%s", resource)
        return default


def translated_catalog(db: Session) -> Ror2CatalogOut:
    """列表数据只来自已审译文。某一份没有译文，这一栏就是空的。"""
    from app.services.ror2.weblate import matching_translation

    if PIPELINE.missing(db):
        get_catalog(db)
    texts = {spec.resource: matching_translation(db, spec.resource) for spec in PIPELINE.specs}
    enemies = texts.get("enemies")
    return Ror2CatalogOut(
        source=f"{WIKI_ORIGIN}/",
        fetched_at="",
        items=_parsed_or_empty("items", texts.get("items"), items_from_module, []),
        equipment=_parsed_or_empty(
            "equipment",
            texts.get("equipment"),
            lambda body: items_from_module(body, default_rarity="Equipment"),
            [],
        ),
        survivors=_parsed_or_empty("survivors", texts.get("survivors"), survivors_from_module, []),
        monsters=_parsed_or_empty("enemies", enemies, monsters_from_module, []),
        drones=_parsed_or_empty("enemies", enemies, drones_from_module, []),
        environments=_parsed_or_empty("environments", texts.get("environments"), environments_from_module, []),
        challenges=_parsed_or_empty("challenges", texts.get("challenges"), challenges_from_module, []),
        interactables=_parsed_or_empty("interactables", texts.get("interactables"), interactables_from_module, []),
        artifacts=_parsed_or_empty("artifacts", texts.get("artifacts"), artifacts_from_module, []),
    )


def translated_detail(db: Session, name: str) -> Ror2SurvivorDetailOut:
    """详情只解析译文文件。词条或模块没有译文时，对应段落留空。"""
    from app.services.ror2.weblate import matching_translation

    survivors = _parsed_or_empty("survivors", matching_translation(db, "survivors"), survivors_from_module, [])
    survivor = next((row for row in survivors if row.name == name), None)
    if survivor is None:
        raise Ror2MissingSurvivor(name)
    page = matching_translation(db, survivor_page_resource(name)) or ""
    skills = _table_or_empty(matching_translation(db, "skills"), skills_table)
    lore = _table_or_empty(matching_translation(db, "lore"), lore_table)
    try:
        return build_survivor_detail(survivor, page, skills, lore)
    except (Ror2WikiError, ValueError):
        log_until_change(log, _LOG_KEY, "雨中冒险2幸存者译文解析失败：%s", name)
        return build_survivor_detail(survivor, "", {}, {})


def catalog_from_db(db: Session) -> Ror2CatalogOut:
    """读已落库的模块，不套译文。"""
    texts = PIPELINE.load_texts(db)
    return Ror2CatalogOut(
        source=f"{WIKI_ORIGIN}/",
        fetched_at=_latest_synced(PIPELINE.revision(db)),
        items=items_from_module(texts["items"]),
        equipment=items_from_module(texts["equipment"], default_rarity="Equipment"),
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
    """词条不在库里时只补这一页，不把整份图鉴重新回源。"""
    catalog = get_catalog(db)
    survivor = next((row for row in catalog.survivors if row.name == name), None)
    if survivor is None:
        raise Ror2MissingSurvivor(name)
    texts = PIPELINE.load_texts(db)
    from app.services.ror2.strings import apply_detail
    from app.services.ror2.weblate import load_units

    page = _survivor_page_text(db, name, fetch_page=fetch_page)
    detail = build_survivor_detail(survivor, page, skills_table(texts["skills"]), lore_table(texts["lore"]))
    apply_detail(detail, load_units(db))
    return detail


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
    job = JobRun(job_key=JOB_KEY, status="running", started_at=now_naive())
    db.add(job)
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
    return fetch_wiki_text(title)


def fetch_wiki_text(title: str) -> str:
    """词条和模块都只走 api.php 的修订正文。"""
    if _rejected_title(title):
        raise Ror2WikiError(f"拒绝的页面名 {title}")
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
