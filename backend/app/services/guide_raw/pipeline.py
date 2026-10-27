"""图鉴上游原文：一个外部文件一行，失败不覆盖，展示时再解析。

新游戏用这个，不要再抄一份落库。塔科夫因为 PVP/PVE × 语言，仍用自己的 ``tarkov_*_raws``，
压缩格式走同一套 ``codec``。

用法::

    pipeline = GuideRawPipeline(
        "example_game",
        (
            RawSpec(
                resource="items",
                source="https://example/items",
                fetch=fetch_items_text,
                accept=parse_items_or_raise,
            ),
        ),
    )
    pipeline.sync(db)          # 定时任务 / 冷启动
    texts = pipeline.load_texts(db)  # 读库，不打上游
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session, undefer

from app.core.timeutil import now_naive
from app.models.guide_raw import GuideRaw
from app.services.guide_raw.codec import pack_raw_text, unpack_raw_text
from app.services.guide_raw.lock import SyncGate

FetchSpec = Callable[["RawSpec"], str]
Accept = Callable[[str], None]


class MissingRaw(Exception):
    def __init__(self, resource: str):
        super().__init__(resource)
        self.resource = resource


@dataclass(frozen=True)
class RawSpec:
    """一份上游文件。``accept`` 不过就不要写入，库里的旧行保持原样。"""

    resource: str
    source: str
    fetch: Callable[[], str]
    accept: Accept


class GuideRawPipeline:
    def __init__(self, game: str, specs: Sequence[RawSpec], *, gate: SyncGate | None = None) -> None:
        self.game = game
        self.specs = tuple(specs)
        self.gate = gate or SyncGate()

    def sync(
        self,
        db: Session,
        *,
        fetch: FetchSpec | None = None,
        abort_on: tuple[type[Exception], ...] = (),
    ) -> list[dict[str, object]]:
        """逐份拉取并落库；abort_on 指定需要立即中断整批同步的异常。"""
        reader = fetch or (lambda spec: spec.fetch())
        results: list[dict[str, object]] = []
        for spec in self.specs:
            try:
                body = reader(spec)
                spec.accept(body)
                saved = upsert_raw(db, self.game, spec.resource, spec.source, body)
                results.append({**saved, "ok": True, "error": None})
            except Exception as exc:  # noqa: BLE001 — 一份失败要留给其余文件
                db.rollback()
                if isinstance(exc, abort_on):
                    raise
                results.append({"resource": spec.resource, "ok": False, "changed": False, "error": str(exc)})
        return results

    def missing(self, db: Session) -> bool:
        return any(load_row(db, self.game, spec.resource) is None for spec in self.specs)

    def revision(self, db: Session) -> str:
        parts: list[str] = []
        for spec in self.specs:
            row = load_row(db, self.game, spec.resource)
            if row is None or row.synced_at is None:
                return ""
            parts.append(f"{spec.resource}@{row.synced_at.isoformat()}")
        return "|".join(parts)

    def load_texts(self, db: Session) -> dict[str, str]:
        texts: dict[str, str] = {}
        for spec in self.specs:
            row = load_row(db, self.game, spec.resource, with_body=True)
            if row is None:
                raise MissingRaw(spec.resource)
            texts[spec.resource] = unpack_raw_text(row.raw_body)
        return texts


def load_row(db: Session, game: str, resource: str, *, with_body: bool = False) -> GuideRaw | None:
    query = db.query(GuideRaw).filter(GuideRaw.game == game, GuideRaw.resource == resource)
    if with_body:
        query = query.options(undefer(GuideRaw.raw_body))
    return query.one_or_none()


def raw_fingerprint(body: str) -> str:
    """Return the exact UTF-8 content digest used to detect upstream raw changes."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def upsert_raw(
    db: Session,
    game: str,
    resource: str,
    source: str,
    body: str,
    *,
    note: str = "",
    commit: bool = True,
) -> dict[str, object]:
    """Hash the raw body; unchanged content keeps its timestamp. Callers validate first.

    ``commit=False`` lets a caller save coupled raw resources in one transaction.
    """
    packed = pack_raw_text(body)
    body_fingerprint = raw_fingerprint(body)
    now = now_naive()
    row = load_row(db, game, resource)
    changed = True
    if row is None:
        row = GuideRaw(
            game=game,
            resource=resource,
            source=source,
            raw_body=packed,
            content_fingerprint=body_fingerprint,
            synced_at=now,
            note=note or None,
        )
        db.add(row)
    else:
        if row.content_fingerprint is None:
            # Legacy rows are compared by their decoded source, then lazily backfilled.
            row = load_row(db, game, resource, with_body=True)
            assert row is not None
            changed = unpack_raw_text(row.raw_body) != body
        else:
            changed = row.content_fingerprint != body_fingerprint

        row.source = source
        if changed:
            row.raw_body = packed
            row.content_fingerprint = body_fingerprint
            row.synced_at = now
            row.note = note or None
        else:
            row.content_fingerprint = body_fingerprint
            if note:
                row.note = note
    if commit:
        db.commit()
    synced = row.synced_at.isoformat() if row.synced_at else now.isoformat()
    return {"resource": resource, "source": source, "synced_at": synced, "changed": changed}
