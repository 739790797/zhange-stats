"""Tests for in-process runtime log buffer."""

from __future__ import annotations

import logging

from app.core.runtime_log_buffer import RuntimeLogBuffer


def test_runtime_log_buffer_snapshot_filters() -> None:
    buf = RuntimeLogBuffer(capacity=50)
    log = logging.getLogger("zhange.test.buffer")
    log.handlers.clear()
    log.propagate = False
    log.setLevel(logging.DEBUG)
    log.addHandler(buf)

    log.debug("dbg")  # handler 默认 INFO，不进缓冲
    log.info("hello info")
    log.warning("warn me")
    log.error("boom")

    total, lines = buf.snapshot(limit=10, min_level="WARNING")
    assert total == 3
    assert [x.level for x in lines] == ["WARNING", "ERROR"]
    assert lines[-1].message == "boom"

    _, info_lines = buf.snapshot(limit=10, q="hello")
    assert len(info_lines) == 1
    assert "hello" in info_lines[0].message

    _, prefixed = buf.snapshot(limit=10, logger_prefix="zhange.test")
    assert len(prefixed) == 3
    assert all(x.biz == "test.buffer" for x in prefixed)

    _, biz_lines = buf.snapshot(limit=10, biz_prefix="test")
    assert len(biz_lines) == 3

    last_id = lines[-1].id
    _, newer = buf.snapshot(limit=10, after_id=last_id)
    assert newer == []

    log.info("after")
    _, newer2 = buf.snapshot(limit=10, after_id=last_id)
    assert len(newer2) == 1
    assert newer2[0].message == "after"

    buf.clear()
    total2, empty = buf.snapshot(limit=10)
    assert total2 == 0
    assert empty == []
