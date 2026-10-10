"""一次性：把原先按 UTC 写入的业务时间改为北京墙钟（+8 小时）。

只有 UTC 时代的旧库需要平移。迁移时就记下这份库的口径：从 UTC 时代修订出发的升级由
`alembic/env.py` 挂的 `UtcEraUpgradeMarker` 标 `utc_pending`（命令行直接 `alembic upgrade` 也会记）；
其余库由 `run_migrations` 标 `beijing_v1`。启动时 `ensure_beijing_time_storage` 平移后再改成 `beijing_v1`。
"""

from __future__ import annotations

import logging

from alembic.runtime.migration import MigrationContext, MigrationInfo
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

_MARKER_KEY = "time_storage"
_MARKER_VALUE = "beijing_v1"
_PENDING_VALUE = "utc_pending"

# v0.1.8 改写北京墙钟时 head 是 0006；停在这些修订（或没有 alembic_version）的库才可能存着 UTC 数据
UTC_ERA_REVISIONS = frozenset(
    {
        "20260731_0001",
        "20260801_0002",
        "20260801_0003",
        "20260801_0004",
        "20260801_0005",
        "20260801_0006",
    }
)

# 仅迁移应用曾用 datetime.now(UTC) 写入的列；不动 created_at/joined_at（server_default）
_SHIFTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("presence_segments", ("started_at", "last_seen_at", "ended_at")),
    ("play_sessions", ("started_at", "last_seen_at", "ended_at")),
    ("job_runs", ("started_at", "finished_at")),
    ("steam_apps", ("fetched_at", "details_fetched_at")),
    ("register_challenges", ("expires_at",)),
)


def current_revision(engine: Engine) -> str | None:
    """没有 alembic_version 表或表为空时返回 None。"""
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _insert_marker_if_missing(conn: Connection, value: str) -> None:
    table = SystemConfig.__table__
    existing = conn.execute(select(table.c.value).where(table.c.key == _MARKER_KEY)).first()
    if existing is None:
        conn.execute(table.insert().values(key=_MARKER_KEY, value=value))


def record_time_storage_origin(engine: Engine, *, utc_era: bool) -> None:
    """迁移时记下口径；已有标记不动，没有 system_configs 时跳过。"""
    if "system_configs" not in set(inspect(engine).get_table_names()):
        return
    with engine.begin() as conn:
        _insert_marker_if_missing(conn, _PENDING_VALUE if utc_era else _MARKER_VALUE)


class UtcEraUpgradeMarker:
    """Alembic `on_version_apply` 钩子：本次升级从 UTC 时代修订出发时记 `utc_pending`。

    升级完修订号就分不出旧库了，所以在升级途中、与修订号同一事务里记。按本次第一步的起点判断：
    从 base 建起的空库链会途经 0001–0006，但那是新库，不记。每次 env.py 运行新建一个实例。
    """

    def __init__(self) -> None:
        self._first_step_seen = False
        self._pending = False

    def __call__(
        self, *, ctx: MigrationContext, step: MigrationInfo, heads: set, run_args: dict
    ) -> None:
        if ctx.as_sql or not step.is_upgrade or step.is_stamp:
            return
        if not self._first_step_seen:
            self._first_step_seen = True
            self._pending = bool(set(step.source_revision_ids) & UTC_ERA_REVISIONS)
        if not self._pending:
            return
        conn = ctx.connection
        if conn is None or "system_configs" not in set(inspect(conn).get_table_names()):
            return
        _insert_marker_if_missing(conn, _PENDING_VALUE)
        self._pending = False


def _needs_shift(marker: str, engine: Engine) -> bool:
    if marker == _PENDING_VALUE:
        return True
    # 迁移时没记口径的库（早于标记的版本升级上来）：按当前修订判断
    revision = current_revision(engine)
    return revision is None or revision in UTC_ERA_REVISIONS


def _shift_to_beijing(db: Session, engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    for table, cols in _SHIFTS:
        if table not in table_names:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for col in cols:
            if col not in existing:
                continue
            db.execute(
                text(
                    f"UPDATE `{table}` SET `{col}` = DATE_ADD(`{col}`, INTERVAL 8 HOUR) "
                    f"WHERE `{col}` IS NOT NULL"
                )
            )


def ensure_beijing_time_storage(db: Session, engine: Engine) -> None:
    row = db.get(SystemConfig, _MARKER_KEY)
    marker = (row.value or "").strip() if row is not None else ""
    if marker == _MARKER_VALUE:
        return

    # SQLite 支持晚于北京墙钟改造，库里没有 UTC 时代的数据
    shift = engine.dialect.name != "sqlite" and _needs_shift(marker, engine)
    if shift:
        logger.info("migrating business timestamps UTC -> Beijing (+8h)")
        _shift_to_beijing(db, engine)

    # 平移与标记同一事务提交，中途失败不会重复平移
    if row is None:
        db.add(SystemConfig(key=_MARKER_KEY, value=_MARKER_VALUE))
    else:
        row.value = _MARKER_VALUE
    db.commit()
    if shift:
        logger.info("business timestamps now stored as Beijing wall clock")
