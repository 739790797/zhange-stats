"""Weblate is accessed only through its API; normalized unit snapshots are cached locally.

Wiki raws stay in guide_raws. Pages read both local caches and never call Weblate.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from sqlalchemy.orm import Session

from app.core.biz_logging import log_until_change
from app.core.database import SessionLocal
from app.core.http_client import HttpRequestError, http_request
from app.core.timeutil import now_naive
from app.services.guide_raw.lock import SyncBusy, SyncGate
from app.models.guide_token_translation import GuideTokenTranslation, GuideTokenTranslationSync
from app.services.guide_raw.pipeline import load_row
from app.services.job_runs_prune import fail_job_run
from app.services.ror2.strings import fingerprint

log = logging.getLogger("zhange.ror2")

JOB_KEY = "ror2_weblate_sync"
RESOURCE = "weblate/zh_Hans.json"
_SKIP_PREFIXES = ("zh-CN/", "zh-Hans/", "weblate/")
SOURCE_LANG = "en"
TARGET_LANG = "zh_Hans"
GAME = "ror2"
SNAPSHOT_VERSION = 2
_LOG_KEY = "ror2-weblate"
_PAGE_LIMIT = 200
_LOOPBACK = frozenset({"127.0.0.1", "localhost"})

GATE = SyncGate("雨中冒险2译文正在同步")


class WeblateError(Exception):
    pass


@dataclass(frozen=True)
class WeblateSnapshot:
    """Weblate 当前源单元清单与目标译文状态；二者不可相互推断。"""

    sources: dict[str, str]
    units: dict[str, dict[str, str]]


def weblate_revision(db: Session) -> str:
    state = db.get(GuideTokenTranslationSync, (GAME, TARGET_LANG))
    if state is not None:
        return state.snapshot_fingerprint
    row = load_row(db, GAME, RESOURCE)
    if row is None or row.synced_at is None:
        return ""
    return row.synced_at.isoformat()


def load_snapshot(db: Session) -> WeblateSnapshot:
    state = db.get(GuideTokenTranslationSync, (GAME, TARGET_LANG))
    if state is None:
        return _load_legacy_snapshot(db)

    rows = (
        db.query(GuideTokenTranslation)
        .filter(
            GuideTokenTranslation.game == GAME,
            GuideTokenTranslation.target_language == TARGET_LANG,
        )
        .order_by(GuideTokenTranslation.context_hash)
        .all()
    )
    if len(rows) != state.unit_count:
        log_until_change(
            log,
            _LOG_KEY,
            "雨中冒险2 Weblate 快照数量校验失败，页面使用 Wiki 原文且不显示令牌",
        )
        return WeblateSnapshot({}, {})

    sources: dict[str, str] = {}
    units: dict[str, dict[str, str]] = {}
    for row in rows:
        if (
            _context_fingerprint(row.context) != row.context_hash
            or fingerprint(row.source_text) != row.source_fingerprint
            or not row.context
            or not row.source_text.strip()
        ):
            log_until_change(
                log,
                _LOG_KEY,
                "雨中冒险2 Weblate 快照完整性校验失败，忽略无效令牌",
            )
            continue
        sources[row.context] = row.source_text
        units[row.context] = {
            "source": row.source_text,
            "target": row.target_text or "",
            "state": row.translation_state,
        }
    if (
        len(units) != state.unit_count
        or _snapshot_fingerprint(units) != state.snapshot_fingerprint
    ):
        log_until_change(
            log,
            _LOG_KEY,
            "雨中冒险2 Weblate 快照指纹校验失败，页面使用 Wiki 原文且不显示令牌",
        )
        return WeblateSnapshot({}, {})
    return WeblateSnapshot(sources, units)


def _load_legacy_snapshot(db: Session) -> WeblateSnapshot:
    from app.services.guide_raw.codec import unpack_raw_text

    row = load_row(db, GAME, RESOURCE, with_body=True)
    if row is None:
        return WeblateSnapshot({}, {})
    try:
        body = unpack_raw_text(row.raw_body)
        payload = json.loads(body)
        if isinstance(payload, dict) and type(payload.get("version")) is int and payload.get("version") == 1:
            return _upgrade_v1_snapshot(payload)
        accept_snapshot(body)
    except (WeblateError, ValueError):
        log_until_change(log, _LOG_KEY, "雨中冒险2 Weblate 快照无法解析，页面使用 Wiki 原文且不显示令牌")
        return WeblateSnapshot({}, {})
    return WeblateSnapshot(payload["sources"], payload["units"])


def _upgrade_v1_snapshot(payload: dict) -> WeblateSnapshot:
    """Version 1 stored only approved units; their source strings are its manifest."""
    raw_units = payload.get("units")
    if not isinstance(raw_units, dict):
        raise WeblateError("旧版译文快照缺少 units")

    sources: dict[str, str] = {}
    units: dict[str, dict[str, str]] = {}
    for context, row in raw_units.items():
        if not isinstance(context, str) or not context.strip() or not isinstance(row, dict):
            raise WeblateError("旧版译文快照有一条单元无法识别")
        source = row.get("source")
        target = row.get("target")
        if (
            row.get("state") != "approved"
            or not isinstance(source, str)
            or not source.strip()
            or not isinstance(target, str)
            or not target.strip()
        ):
            raise WeblateError("旧版译文快照包含无效或未审核单元")
        sources[context] = source
        units[context] = {"source": source, "target": target, "state": "approved"}
    return WeblateSnapshot(sources, units)


def load_units(db: Session) -> dict[str, dict[str, str]]:
    """兼容内部同步调用；页面解析应使用 load_snapshot 以保留源单元清单。"""
    return load_snapshot(db).units


def accept_snapshot(body: str) -> None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WeblateError("译文快照不是 JSON") from exc
    if not isinstance(payload, dict) or payload.get("version") != SNAPSHOT_VERSION:
        raise WeblateError("译文快照版本无法识别")
    sources = payload.get("sources")
    units = payload.get("units")
    if not isinstance(sources, dict) or not isinstance(units, dict):
        raise WeblateError("译文快照缺少 sources 或 units")
    for key, source in sources.items():
        if not isinstance(key, str) or not key or not isinstance(source, str) or not source.strip():
            raise WeblateError("译文快照有一条源单元无法识别")
    for key, unit in units.items():
        if not isinstance(key, str) or not key or not isinstance(unit, dict):
            raise WeblateError("译文快照有一条译文无法识别")
        if unit.get("state") != "approved":
            raise WeblateError(f"译文快照只收已审条目：{key}")
        source = unit.get("source")
        target = unit.get("target")
        if not isinstance(source, str) or not isinstance(target, str) or not target.strip():
            raise WeblateError(f"译文快照条目缺原文或译文：{key}")
        listed_source = sources.get(key)
        if not isinstance(listed_source, str) or fingerprint(source) != fingerprint(listed_source):
            raise WeblateError(f"译文快照的已审译文不属于当前源单元：{key}")


def dump_snapshot(
    units: dict[str, dict[str, str]],
    sources: dict[str, str],
) -> str:
    body = json.dumps(
        {"version": SNAPSHOT_VERSION, "sources": sources, "units": units},
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    accept_snapshot(body)
    return body + "\n"


def cached_units(raw_units: list[dict], expected: dict[str, str]) -> dict[str, dict[str, str]]:
    """Keep current Weblate state for known contexts, including untranslated units."""
    found: dict[str, dict[str, str]] = {}
    for unit in raw_units:
        if not isinstance(unit, dict):
            continue
        context = str(unit.get("context") or "").strip()
        if not context or context not in expected:
            continue
        source = _plain(unit.get("source"))
        if not source.strip():
            continue
        target = _plain(unit.get("target"))
        fuzzy = bool(unit.get("fuzzy"))
        if bool(unit.get("approved")) and not fuzzy and target.strip():
            state = "approved"
        elif fuzzy:
            state = "fuzzy"
        elif bool(unit.get("pending")):
            state = "pending"
        elif target.strip():
            state = "translated"
        else:
            state = "untranslated"
        record = {"source": source, "target": target, "state": state}
        previous = found.get(context)
        if previous is not None and previous != record:
            raise WeblateError(f"Weblate 返回了冲突的单元：{context}")
        found[context] = record
    return found


def _context_fingerprint(context: str) -> str:
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


def _scope_fingerprint(cfg: dict[str, str]) -> str:
    scope = json.dumps(
        [cfg["base"], cfg["project"], cfg["component"], SOURCE_LANG, TARGET_LANG],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()


def _snapshot_fingerprint(units: dict[str, dict[str, str]]) -> str:
    canonical = [
        [context, row["source"], row["target"], row["state"]]
        for context, row in sorted(units.items())
    ]
    body = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source_manifest_fingerprint(strings: dict[str, str]) -> str:
    canonical = [[context, text] for context, text in sorted(strings.items())]
    body = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _source_manifest_matches(
    records: dict[str, dict[str, str]], expected: dict[str, str]
) -> bool:
    if len(records) != len(expected):
        return False
    return all(
        context in records
        and fingerprint(records[context]["source"]) == fingerprint(source)
        for context, source in expected.items()
    )


def _store_snapshot(
    db: Session,
    units: dict[str, dict[str, str]],
    cfg: dict[str, str],
    *,
    source_manifest_fingerprint: str | None = None,
) -> None:
    scope_hash = _scope_fingerprint(cfg)
    snapshot_hash = _snapshot_fingerprint(units)
    state = db.get(GuideTokenTranslationSync, (GAME, TARGET_LANG))
    cached_count = (
        db.query(GuideTokenTranslation)
        .filter(
            GuideTokenTranslation.game == GAME,
            GuideTokenTranslation.target_language == TARGET_LANG,
        )
        .count()
    )

    if (
        state is None
        or state.snapshot_fingerprint != snapshot_hash
        or state.unit_count != len(units)
        or cached_count != len(units)
    ):
        db.query(GuideTokenTranslation).filter(
            GuideTokenTranslation.game == GAME,
            GuideTokenTranslation.target_language == TARGET_LANG,
        ).delete(synchronize_session=False)
        db.add_all(
            GuideTokenTranslation(
                game=GAME,
                target_language=TARGET_LANG,
                context_hash=_context_fingerprint(context),
                context=context,
                source_text=row["source"],
                source_fingerprint=fingerprint(row["source"]),
                target_text=row["target"] or None,
                translation_state=row["state"],
            )
            for context, row in units.items()
        )
        if state is None:
            state = GuideTokenTranslationSync(
                game=GAME,
                target_language=TARGET_LANG,
                scope_fingerprint=scope_hash,
                source_manifest_fingerprint=source_manifest_fingerprint,
                snapshot_fingerprint=snapshot_hash,
                unit_count=len(units),
                synced_at=now_naive(),
            )
            db.add(state)
        else:
            state.scope_fingerprint = scope_hash
            state.snapshot_fingerprint = snapshot_hash
            state.unit_count = len(units)
            state.synced_at = now_naive()
    elif state.scope_fingerprint != scope_hash:
        state.scope_fingerprint = scope_hash
    state.source_manifest_fingerprint = source_manifest_fingerprint

    # Remove the legacy Weblate row only after a complete API snapshot is ready.
    legacy = load_row(db, GAME, RESOURCE)
    if legacy is not None:
        db.delete(legacy)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def select_suggestions(raw_units: list[dict], suggestions: dict[str, str]) -> dict[str, str]:
    """空译文才接受游戏中文建议。已经有译文或待审建议的条目不再重复提交。"""
    known: dict[str, dict] = {}
    for unit in raw_units:
        if not isinstance(unit, dict):
            continue
        key = str(unit.get("context") or "").strip()
        if key:
            known[key] = unit
    chosen: dict[str, str] = {}
    for key, text in suggestions.items():
        if not str(text or "").strip():
            continue
        unit = known.get(key)
        if unit is None:
            chosen[key] = text
            continue
        if unit.get("pending") or _plain(unit.get("target")).strip():
            continue
        chosen[key] = text
    return chosen


def _safe_api_path(path: str) -> str | None:
    decoded = path or "/"
    for _ in range(8):
        if "\\" in decoded:
            return None
        unescaped = unquote(decoded)
        if unescaped == decoded:
            break
        if unescaped.count("/") != decoded.count("/"):
            return None
        decoded = unescaped
    else:
        return None
    if "\\" in decoded or any(part in {".", ".."} for part in decoded.split("/")):
        return None
    return decoded


def normalize_base_url(url: str) -> str:
    try:
        parsed = urlsplit((url or "").strip())
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise WeblateError("Weblate 地址格式无效") from exc
    if parsed.username or parsed.password:
        raise WeblateError("不要把令牌写进 Weblate 地址")
    if (
        not host
        or port == 0
        or parsed.query
        or parsed.fragment
        or _safe_api_path(parsed.path) is None
    ):
        raise WeblateError("Weblate 地址不能包含查询、片段或不安全路径")
    if parsed.scheme == "https" or (parsed.scheme == "http" and host in _LOOPBACK):
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    raise WeblateError("Weblate 地址需要 https")


def same_origin(url: str, base: str) -> bool:
    try:
        target = urlsplit(url)
        root = urlsplit(base)
    except ValueError:
        return False
    if (
        target.username
        or target.password
        or root.username
        or root.password
        or target.fragment
        or root.query
        or root.fragment
        or target.scheme.lower() not in {"http", "https"}
        or not target.hostname
        or not root.hostname
        or target.scheme.lower() != root.scheme.lower()
        or target.hostname.casefold() != root.hostname.casefold()
    ):
        return False
    try:
        default_port = 443 if target.scheme.lower() == "https" else 80
        target_port = target.port if target.port is not None else default_port
        root_port = root.port if root.port is not None else default_port
    except ValueError:
        return False
    if target_port == 0 or root_port == 0 or target_port != root_port:
        return False

    target_path = _safe_api_path(target.path)
    root_path = _safe_api_path(root.path)
    if target_path is None or root_path is None:
        return False
    base_path = root_path.rstrip("/")
    api_prefix = f"{base_path}/api/" if base_path else "/api/"
    return target_path.startswith(api_prefix)


def source_documents(db: Session) -> dict[str, str]:
    """Wiki 同步留下的每一份原文。语言文件和译文本身不再送去翻译。"""
    from sqlalchemy.orm import undefer

    from app.models.guide_raw import GuideRaw
    from app.services.guide_raw.codec import unpack_raw_text

    rows = (
        db.query(GuideRaw)
        .options(undefer(GuideRaw.raw_body))
        .filter(GuideRaw.game == "ror2")
        .all()
    )
    documents: dict[str, str] = {}
    for row in rows:
        if row.resource.startswith(_SKIP_PREFIXES):
            continue
        documents[row.resource] = unpack_raw_text(row.raw_body)
    return documents


def sync_weblate(db: Session, *, client: Callable[..., object] | None = None) -> str:
    from app.services.ror2.wiki import PIPELINE

    cfg = weblate_settings()
    if PIPELINE.missing(db):
        raise WeblateError("wiki 图鉴还没有落库")
    documents = source_documents(db)
    if not documents:
        raise WeblateError("wiki 图鉴里没有可翻译的原文")
    from app.services.ror2.strings import Ror2StringError
    from app.services.ror2.units import extract_units

    strings: dict[str, str] = {}
    for resource, body in documents.items():
        try:
            found = extract_units(resource, body)
        except Ror2StringError as exc:
            raise WeblateError(str(exc)) from exc
        overlap = strings.keys() & found.keys()
        conflict = next((key for key in overlap if strings[key] != found[key]), None)
        if conflict:
            raise WeblateError(f"编号冲突：{conflict}")
        strings.update(found)
    if not strings:
        raise WeblateError("wiki 图鉴里没有可翻译的原文")
    sender = client or http_request
    manifest_hash = _source_manifest_fingerprint(strings)

    listed = list_units(cfg, client=sender)
    _require_context(listed)
    records = cached_units(listed, strings)
    source_confirmed = _source_manifest_matches(records, strings)
    if not source_confirmed:
        _repair_source_manifest(cfg, strings, listed, client=sender)
        listed = list_units(cfg, client=sender)
        _require_context(listed)
        records = cached_units(listed, strings)
        source_confirmed = _source_manifest_matches(records, strings)
    if not source_confirmed:
        log_until_change(
            log,
            _LOG_KEY,
            "Weblate 源单元尚未与本地 Wiki 清单完全一致；保留上一份译文快照",
        )
        raise WeblateError("Weblate 源单元与 Wiki 清单仍不一致；未刷新本地译文快照")

    approved_count = sum(
        1
        for context, row in records.items()
        if row["state"] == "approved"
        and fingerprint(row["source"]) == fingerprint(strings[context])
    )
    _store_snapshot(
        db,
        records,
        cfg,
        source_manifest_fingerprint=manifest_hash if source_confirmed else None,
    )
    report = f"原文 {len(strings)} 条，Weblate 源单元 {len(records)} 条，已审 {approved_count} 条"
    log.info("雨中冒险2译文已同步：%s", report)
    return report


def _batches(strings: dict[str, str], max_bytes: int = 300_000) -> list[dict[str, str]]:
    """按正文大小切开，避免反代在一次大上传上超时。"""
    batches: list[dict[str, str]] = []
    current: dict[str, str] = {}
    size = 2
    for key, value in strings.items():
        piece = len(key.encode("utf-8")) + len(value.encode("utf-8")) + 8
        if current and size + piece > max_bytes:
            batches.append(current)
            current = {}
            size = 2
        current[key] = value
        size += piece
    if current:
        batches.append(current)
    return batches


def sync_job() -> None:
    db = SessionLocal()
    from app.services.job_run_progress import create_or_reuse_job_run, versioned_job_stats

    job = create_or_reuse_job_run(
        db, JOB_KEY, message="正在同步图鉴译文", stats={"phase": "start"}
    )
    db.commit()
    run_id = job.id
    try:
        try:
            with GATE.exclusive():
                report = sync_weblate(db)
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
        job.message = report
        job.stats = versioned_job_stats(
            JOB_KEY,
            status="ok",
            stats={"phase": "done", "result": {"summary": report[:300]}},
            message=report,
        )
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.exception("雨中冒险2译文同步失败")
        fail_job_run(db, run_id, str(exc))
    finally:
        db.close()


def weblate_settings() -> dict[str, str]:
    from app.services.integrations_config import load_integrations

    cfg = load_integrations()
    base = (cfg.get("weblate_url") or "").strip()
    token = (cfg.get("weblate_token") or "").strip()
    project = (cfg.get("weblate_project") or "").strip()
    component = (cfg.get("weblate_component") or "").strip()
    if not (base and token and project and component):
        raise WeblateError("还没有配置 Weblate。在集成密钥里填写地址、项目、组件和令牌")
    if not _slug(project) or not _slug(component):
        raise WeblateError("Weblate 项目和组件只使用字母、数字、下划线和连字符")
    return {
        "base": normalize_base_url(base),
        "token": token,
        "project": project,
        "component": component,
    }


def list_units(cfg: dict[str, str], *, client: Callable[..., object]) -> list[dict]:
    url = (
        f"{cfg['base']}/api/translations/{cfg['project']}/{cfg['component']}/{TARGET_LANG}/units/"
        "?page_size=200"
    )
    found: list[dict] = []
    seen: set[str] = set()
    expected_count: int | None = None
    for _ in range(_PAGE_LIMIT):
        if url in seen or not same_origin(url, cfg["base"]):
            raise WeblateError("Weblate 分页跳到了站外")
        seen.add(url)
        payload = _read_json(cfg, "GET", url, client=client)
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise WeblateError("Weblate 没有返回条目列表")
        if "count" in payload:
            count = payload["count"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise WeblateError("Weblate 条目总数无法识别")
            if expected_count is None:
                expected_count = count
            elif expected_count != count:
                raise WeblateError("Weblate 分页期间条目总数发生变化")
        found.extend(row for row in rows if isinstance(row, dict))
        nxt = payload.get("next") or ""
        if not nxt:
            if expected_count is not None and len(found) != expected_count:
                raise WeblateError(
                    f"Weblate 分页不完整：返回 {len(found)} 条，声称共 {expected_count} 条"
                )
            return found
        if not isinstance(nxt, str):
            raise WeblateError("Weblate 分页地址无法识别")
        url = nxt
    raise WeblateError("Weblate 分页没有结束")


def _repair_source_manifest(
    cfg: dict[str, str],
    expected: dict[str, str],
    raw_units: list[dict],
    *,
    client: Callable[..., object],
) -> None:
    """Add missing contexts and edit changed sources without replacing the component file."""
    by_context: dict[str, dict[str, object]] = {}
    for unit in raw_units:
        if not isinstance(unit, dict):
            continue
        context = str(unit.get("context") or "").strip()
        source = _plain(unit.get("source"))
        if not context or not source.strip():
            continue
        row = {
            "source": source,
            "id": unit.get("id"),
            "content_hash": unit.get("content_hash"),
        }
        previous = by_context.get(context)
        if previous is not None and previous != row:
            raise WeblateError(f"Weblate 返回了冲突的源单元：{context}")
        by_context[context] = row

    missing = {context: text for context, text in expected.items() if context not in by_context}
    for batch in _batches(missing):
        upload_json(cfg, SOURCE_LANG, "add", batch, client=client)

    changed = [
        (
            context,
            text,
            by_context[context].get("id"),
            by_context[context].get("content_hash"),
        )
        for context, text in expected.items()
        if context in by_context
        and fingerprint(str(by_context[context]["source"])) != fingerprint(text)
    ]
    for context, text, unit_id, content_hash in changed:
        if isinstance(unit_id, bool) or not isinstance(unit_id, (int, str)) or not str(unit_id).isdigit():
            raise WeblateError(f"Weblate 源单元无法更新：缺少有效单元 ID（{context}）")
        _edit_source_unit(
            cfg,
            str(unit_id),
            context,
            text,
            content_hash=content_hash,
            client=client,
        )


def _edit_source_unit(
    cfg: dict[str, str],
    unit_id: str,
    context: str,
    source: str,
    *,
    content_hash: object,
    client: Callable[..., object],
) -> None:
    if isinstance(content_hash, bool) or not isinstance(content_hash, int):
        raise WeblateError(f"Weblate 源单元无法更新：缺少有效 content_hash（{context}）")
    url = f"{cfg['base']}/api/units/{unit_id}/source/"
    if not same_origin(url, cfg["base"]):
        raise WeblateError("Weblate 源单元地址不在配置的 API 路径内")
    response = _send(
        cfg,
        "POST",
        url,
        client=client,
        json={"source": [source], "content_hash": content_hash},
        timeout=60,
    )
    status = getattr(response, "status_code", 0)
    if status < 200 or status >= 300:
        detail = _error_detail(response, cfg["token"])
        raise WeblateError(
            f"Weblate 源字符串 API 更新失败：HTTP {status} {_redact(detail, cfg['token'])[:300]}；"
            f"未使用会替换文件的上传方式（context：{context}）"
        )


def upload_json(
    cfg: dict[str, str],
    language: str,
    method: str,
    payload: dict[str, str],
    *,
    client: Callable[..., object],
) -> None:
    if method not in {"add", "suggest"}:
        raise WeblateError("不支持的 Weblate 上传方式")
    content, content_type = _multipart(method, payload)
    url = f"{cfg['base']}/api/translations/{cfg['project']}/{cfg['component']}/{language}/file/"
    response = _send(
        cfg,
        "POST",
        url,
        client=client,
        content=content,
        headers={"Content-Type": content_type},
        timeout=120,
    )
    status = getattr(response, "status_code", 0)
    if status < 200 or status >= 300:
        raise WeblateError(f"Weblate 上传失败：HTTP {status} {_error_detail(response, cfg['token'])}")
    body = _json_body(response)
    if not isinstance(body, dict):
        raise WeblateError("Weblate 没有返回上传结果")
    accepted = int(body.get("accepted") or 0)
    skipped = int(body.get("skipped") or 0)
    not_found = int(body.get("not_found") or 0)
    total = int(body.get("total") or 0)
    if body.get("result") is False and not (method == "add" and skipped > 0 and not_found == 0):
        detail = str(body.get("detail") or "").strip()
        counts = f"接受 {accepted}，跳过 {skipped}，对不上 {not_found}，一共 {total}"
        message = f"Weblate 没有接受这份文件（{counts}）"
        if detail:
            message = f"{message}：{detail}"
        if method == "add" and accepted == 0 and skipped == 0:
            message += "。请在组件设置里打开「管理字符串」，并确认翻译语言里有 zh_Hans"
        raise WeblateError(_redact(message, cfg["token"])[:500])


def _require_context(raw_units: list[dict]) -> None:
    if raw_units and not any(str(unit.get("context") or "").strip() for unit in raw_units):
        raise WeblateError("Weblate 条目没有 context。组件需要单语 JSON，键会落在 context 上")


def _read_json(cfg: dict[str, str], method: str, url: str, *, client: Callable[..., object]) -> dict:
    response = _send(cfg, method, url, client=client, timeout=60)
    status = getattr(response, "status_code", 0)
    if status < 200 or status >= 300:
        raise WeblateError(f"Weblate 请求失败：HTTP {status} {_safe_text(response, cfg['token'])}")
    body = _json_body(response)
    if not isinstance(body, dict):
        raise WeblateError("Weblate 返回的不是 JSON 对象")
    return body


def _send(cfg: dict[str, str], method: str, url: str, *, client: Callable[..., object], **kwargs: object):
    headers = {"Authorization": f"Token {cfg['token']}", "Accept": "application/json"}
    extra = kwargs.pop("headers", None)
    if isinstance(extra, dict):
        headers.update(extra)
    kwargs.setdefault("follow_redirects", False)
    try:
        return client(method, url, headers=headers, **kwargs)
    except HttpRequestError as exc:
        raise WeblateError(_redact(str(exc), cfg["token"])) from exc


def _json_body(response: object) -> object:
    parser = getattr(response, "json", None)
    if not callable(parser):
        raise WeblateError("Weblate 返回的不是 JSON")
    try:
        return parser()
    except ValueError as exc:
        raise WeblateError("Weblate 返回的不是 JSON") from exc


def _error_detail(response: object, token: str) -> str:
    body = _json_body_or_none(response)
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, list):
            parts = [
                str(item.get("detail")).strip()
                for item in errors
                if isinstance(item, dict) and str(item.get("detail") or "").strip()
            ]
            if parts:
                return _redact(" ".join(parts), token)[:500]
        detail = str(body.get("detail") or "").strip()
        if detail:
            return _redact(detail, token)[:500]
    return _safe_text(response, token)


def _json_body_or_none(response: object) -> object:
    parser = getattr(response, "json", None)
    if not callable(parser):
        return None
    try:
        return parser()
    except ValueError:
        return None


def _safe_text(response: object, token: str) -> str:
    text = str(getattr(response, "text", "") or "").strip().replace("\n", " ")
    return _redact(text, token)[:180]


def _redact(text: str, token: str) -> str:
    if token and token in text:
        return text.replace(token, "***")
    return text


def _plain(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return ""


def _slug(value: str) -> bool:
    if not value or len(value) > 64:
        return False
    for char in value:
        if not (char.isalnum() or char in {"_", "-"}):
            return False
    return True


def _multipart(method: str, payload: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----zhangeRor2Weblate"
    file_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    chunks = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="method"\r\n\r\n'
            f"{method}\r\n"
        ).encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="ror2.json"\r\n'
            f"Content-Type: application/json\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
