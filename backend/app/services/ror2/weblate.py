"""Weblate 是雨中冒险 2 的唯一译文出口。

每一次 Wiki 请求留下的原文文件，整份推去翻译，译文保持同一份格式。
已审且原文指纹还一致的译文，按同样的资源名写到 ``zh-Hans/`` 下。
展示用的数据只解析这些译文；没有译文的部分是空的。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.biz_logging import log_until_change
from app.core.database import SessionLocal
from app.core.http_client import HttpRequestError, http_request
from app.core.timeutil import now_naive
from app.models.job_run import JobRun
from app.services.guide_raw.lock import SyncBusy, SyncGate
from app.services.guide_raw.pipeline import load_row, upsert_raw
from app.services.job_runs_prune import fail_job_run
from app.services.ror2.strings import fingerprint

log = logging.getLogger("zhange.ror2")

JOB_KEY = "ror2_weblate_sync"
RESOURCE = "weblate/zh_Hans.json"
TRANSLATION_PREFIX = "zh-Hans/"
_SKIP_PREFIXES = ("zh-CN/", "zh-Hans/", "weblate/")
SOURCE_LANG = "en"
TARGET_LANG = "zh_Hans"
SNAPSHOT_VERSION = 1
_LOG_KEY = "ror2-weblate"
_PAGE_LIMIT = 200
_LOOPBACK = frozenset({"127.0.0.1", "localhost"})

GATE = SyncGate("雨中冒险2译文正在同步")


class WeblateError(Exception):
    pass


def weblate_revision(db: Session) -> str:
    row = load_row(db, "ror2", RESOURCE)
    if row is None or row.synced_at is None:
        return ""
    return row.synced_at.isoformat()


def load_units(db: Session) -> dict[str, dict[str, str]]:
    from app.services.guide_raw.codec import unpack_raw_text

    row = load_row(db, "ror2", RESOURCE, with_body=True)
    if row is None:
        return {}
    try:
        body = unpack_raw_text(row.raw_body)
        accept_snapshot(body)
    except (WeblateError, ValueError):
        log_until_change(log, _LOG_KEY, "雨中冒险2译文快照无法解析，页面先显示英文")
        return {}
    units = json.loads(body)["units"]
    return units if isinstance(units, dict) else {}


def accept_snapshot(body: str) -> None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise WeblateError("译文快照不是 JSON") from exc
    if not isinstance(payload, dict) or payload.get("version") != SNAPSHOT_VERSION:
        raise WeblateError("译文快照版本无法识别")
    units = payload.get("units")
    if not isinstance(units, dict):
        raise WeblateError("译文快照缺少 units")
    for key, unit in units.items():
        if not isinstance(key, str) or not key or not isinstance(unit, dict):
            raise WeblateError("译文快照有一条无法识别")
        if unit.get("state") != "approved":
            raise WeblateError(f"译文快照只收已审条目：{key}")
        if not isinstance(unit.get("source"), str) or not isinstance(unit.get("target"), str):
            raise WeblateError(f"译文快照条目缺原文或译文：{key}")


def dump_snapshot(units: dict[str, dict[str, str]]) -> str:
    body = json.dumps({"version": SNAPSHOT_VERSION, "units": units}, ensure_ascii=False, sort_keys=True, indent=2)
    accept_snapshot(body)
    return body + "\n"


def approved_units(raw_units: list[dict]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for unit in raw_units:
        if not isinstance(unit, dict) or not unit.get("approved") or unit.get("fuzzy"):
            continue
        key = str(unit.get("context") or "").strip()
        source = _plain(unit.get("source"))
        target = _plain(unit.get("target"))
        if not key or not source.strip() or not target.strip():
            continue
        found[key] = {"source": source, "target": target, "state": "approved"}
    return found


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


def normalize_base_url(url: str) -> str:
    parsed = urlsplit((url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.username or parsed.password:
        raise WeblateError("不要把令牌写进 Weblate 地址")
    if parsed.scheme == "https" or (parsed.scheme == "http" and host in _LOOPBACK):
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    raise WeblateError("Weblate 地址需要 https")


def same_origin(url: str, base: str) -> bool:
    target = urlsplit(url)
    root = urlsplit(base)
    return (
        target.scheme == root.scheme
        and target.netloc == root.netloc
        and (target.path or "").startswith("/api/")
    )


def translation_resource(resource: str) -> str:
    return f"{TRANSLATION_PREFIX}{resource}"


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


def matching_translation(db: Session, resource: str) -> str | None:
    """译文文件和当前原文指纹一致才返回正文。"""
    from app.services.guide_raw.codec import unpack_raw_text

    source = load_row(db, "ror2", resource, with_body=True)
    translated = load_row(db, "ror2", translation_resource(resource), with_body=True)
    if source is None or translated is None:
        return None
    original = unpack_raw_text(source.raw_body)
    if (translated.note or "") != fingerprint(original):
        return None
    return unpack_raw_text(translated.raw_body)


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
    batches = _batches(strings)
    log.info("雨中冒险2译文开始上传：%s 条，分 %s 批", len(strings), len(batches))
    for batch in batches:
        upload_json(cfg, SOURCE_LANG, "add", batch, client=sender)
    listed = list_units(cfg, client=sender)
    _require_context(listed)
    approved = approved_units(listed)
    kept: dict[str, dict[str, str]] = {}
    for key, source in strings.items():
        unit = approved.get(key)
        if unit and fingerprint(unit["source"]) == fingerprint(source):
            kept[key] = unit
    upsert_raw(
        db,
        "ror2",
        RESOURCE,
        f"{cfg['base']}/projects/{cfg['project']}/{cfg['component']}/{TARGET_LANG}/",
        dump_snapshot(kept),
    )
    report = f"原文 {len(strings)} 条，已审 {len(kept)} 条"
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


def _drop_translation(db: Session, resource: str) -> None:
    row = load_row(db, "ror2", resource)
    if row is None:
        return
    db.delete(row)
    db.commit()


def sync_job() -> None:
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running", started_at=now_naive())
    db.add(job)
    db.commit()
    run_id = job.id
    try:
        try:
            with GATE.exclusive():
                report = sync_weblate(db)
        except SyncBusy:
            job.status = "ok"
            job.message = "已有同步在跑"
            job.finished_at = now_naive()
            db.commit()
            return
        job.status = "ok"
        job.message = report
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
    for _ in range(_PAGE_LIMIT):
        if url in seen or not same_origin(url, cfg["base"]):
            raise WeblateError("Weblate 分页跳到了站外")
        seen.add(url)
        payload = _read_json(cfg, "GET", url, client=client)
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise WeblateError("Weblate 没有返回条目列表")
        found.extend(row for row in rows if isinstance(row, dict))
        nxt = payload.get("next") or ""
        if not nxt:
            return found
        if not isinstance(nxt, str):
            raise WeblateError("Weblate 分页地址无法识别")
        url = nxt
    raise WeblateError("Weblate 分页没有结束")


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
    if status >= 400:
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
    if status >= 400:
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
