"""Tests for log line merge/filter and JSONL persistence."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.log_line import LogLine, filter_log_lines, merge_log_lines
from app.core.log_persistence import _parse_json_line, tail_file_logs


def _line(
    id_: int,
    ts: str,
    *,
    level: str = "INFO",
    logger: str = "app.services.demo",
    biz: str = "demo",
    context: str = "",
    message: str = "hello",
) -> LogLine:
    return LogLine(
        id=id_,
        ts=ts,
        level=level,
        logger=logger,
        biz=biz,
        context=context,
        message=message,
    )


def test_merge_log_lines_dedupes_and_sorts() -> None:
    ring = [
        _line(1, "2026-03-24 10:00:00", message="a"),
        _line(2, "2026-03-24 10:00:02", message="b"),
    ]
    file_rows = [
        _line(1_000_000_001, "2026-03-24 09:59:59", message="old"),
        _line(1_000_000_002, "2026-03-24 10:00:02", message="b"),
    ]
    merged = merge_log_lines(ring, file_rows, limit=10)
    assert [x.message for x in merged] == ["old", "a", "b"]
    assert merged[-1].id == 3


def test_filter_log_lines_by_biz() -> None:
    rows = [
        _line(1, "t1", biz="skland.checkin"),
        _line(2, "t2", biz="steam.poller"),
    ]
    out = filter_log_lines(rows, limit=10, biz_prefix="skland")
    assert len(out) == 1
    assert out[0].biz == "skland.checkin"


def test_parse_json_line_and_tail(tmp_path: Path, monkeypatch) -> None:
    log_file = tmp_path / "app.jsonl"
    payload = {
        "ts": "2026-03-24 10:00:00",
        "level": "INFO",
        "logger": "zhange.http",
        "biz": "http",
        "context": "method=GET path=/api/demo",
        "message": "GET /api/demo -> 200 3ms",
    }
    log_file.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

    parsed = _parse_json_line(log_file.read_text(encoding="utf-8"), 1)
    assert parsed is not None
    assert parsed.biz == "http"

    class _Settings:
        APP_LOG_FILE = True
        DATA_DIR = str(tmp_path)

    monkeypatch.setattr("app.core.log_persistence.get_settings", lambda: _Settings())
    monkeypatch.setattr(
        "app.core.log_persistence.resolve_log_file_path",
        lambda: log_file,
    )
    path, total, lines = tail_file_logs(limit=10, biz_prefix="http")
    assert path == str(log_file)
    assert total == 1
    assert len(lines) == 1
