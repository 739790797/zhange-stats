"""Tests for business log tagging."""

from __future__ import annotations

import logging

from app.core.biz_logging import (
    BizTagFilter,
    log_context,
    resolve_biz_tag,
)


def test_resolve_biz_tag_platform_services() -> None:
    assert resolve_biz_tag("app.services.skland_checkin") == "skland.checkin"
    assert resolve_biz_tag("app.services.taygedo_boxes") == "taygedo.boxes"
    assert resolve_biz_tag("app.services.mihoyo_checkin") == "mihoyo.checkin"
    assert resolve_biz_tag("app.services.checkin_orchestrator") == "checkin.orchestrator"
    assert resolve_biz_tag("zhange.scheduler") == "scheduler"
    assert resolve_biz_tag("uvicorn.access") == "infra.http"


def test_biz_tag_filter_and_context() -> None:
    record = logging.LogRecord(
        name="app.services.skland_checkin",
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
