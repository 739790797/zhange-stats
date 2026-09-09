"""Tests for business log tagging."""

from __future__ import annotations

import logging

from app.core.biz_logging import (
    BizTagFilter,
    clear_log_until_change,
    log_context,
    log_until_change,
    resolve_biz_tag,
)


def test_resolve_biz_tag_platform_services() -> None:
    assert resolve_biz_tag("app.services.skland.checkin") == "skland.checkin"
    assert resolve_biz_tag("app.services.taygedo.boxes") == "taygedo.boxes"
    assert resolve_biz_tag("app.services.mihoyo.checkin") == "mihoyo.checkin"
    assert resolve_biz_tag("app.services.checkin.orchestrator") == "checkin.orchestrator"
    assert resolve_biz_tag("zhange.scheduler") == "scheduler"
    assert resolve_biz_tag("uvicorn.access") == "infra.http"


def test_biz_tag_filter_and_context() -> None:
    record = logging.LogRecord(
        name="app.services.skland.checkin",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    filt = BizTagFilter()
    with log_context(platform="skland", member_id=42):
        assert filt.filter(record) is True
    assert record.biz_tag == "skland.checkin"  # type: ignore[attr-defined]
    assert record.log_context == "member_id=42 platform=skland"  # type: ignore[attr-defined]


def test_log_until_change_repeats_as_debug(caplog) -> None:
    clear_log_until_change()
    log = logging.getLogger("zhange.test.repeat")
    log.propagate = True
    with caplog.at_level(logging.DEBUG, logger="zhange.test.repeat"):
        log_until_change(log, "k", "redis down %s", "e1")
        log_until_change(log, "k", "redis down %s", "e1")
        log_until_change(log, "k", "redis down %s", "e2")
        clear_log_until_change("k")
        log_until_change(log, "k", "redis down %s", "e1")
    records = [r for r in caplog.records if r.name == "zhange.test.repeat"]
    assert [r.levelno for r in records] == [
        logging.WARNING,
        logging.DEBUG,
        logging.WARNING,
        logging.WARNING,
    ]
    assert "e1" in records[0].message
    assert "e2" in records[2].message

