"""JSONL tail：从尾部按块回读、行数增量缓存、after_id 增量、轮转重置、目录懒创建。"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from app.core import log_persistence as lp
from app.core.log_persistence import file_log_stats, tail_file_logs

BASE = lp._FILE_ID_BASE


def _row(i: int, *, level: str = "INFO") -> str:
    return json.dumps(
        {
            "ts": f"2026-03-24 10:{i // 60 % 60:02d}:{i % 60:02d}",
            "level": level,
            "logger": "zhange.demo",
            "biz": "demo",
            "context": "",
            "message": f"line {i}",
        },
        ensure_ascii=False,
    )


def _write(path: Path, start: int, stop: int, *, mode: str = "a") -> None:
    with path.open(mode, encoding="utf-8") as fh:
        for i in range(start, stop):
            fh.write(_row(i) + "\n")


@pytest.fixture
def log_file(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "logs" / "app.jsonl"
    path.parent.mkdir()
    monkeypatch.setattr(lp, "resolve_log_file_path", lambda: path)
    lp.reset_line_count_cache_for_tests()
    yield path
    lp.reset_line_count_cache_for_tests()


def test_tail_returns_last_lines_with_absolute_ids(log_file: Path) -> None:
    _write(log_file, 1, 501)
    path, total, lines = tail_file_logs(limit=5, scan_lines=5)
    assert path == str(log_file)
    assert total == 500
    assert [x.message for x in lines] == [f"line {i}" for i in range(496, 501)]
    assert [x.id for x in lines] == [BASE + i for i in range(496, 501)]


def test_tail_reads_only_the_end_of_large_files(monkeypatch) -> None:
    monkeypatch.setattr(lp, "_READ_BLOCK", 1024)
    payload = "".join(_row(i) + "\n" for i in range(1, 20001)).encode("utf-8")

    class CountingIO(io.BytesIO):
        read_total = 0

        def read(self, n: int = -1) -> bytes:  # type: ignore[override]
            data = super().read(n)
            CountingIO.read_total += len(data)
            return data

    fh = CountingIO(payload)
    out = lp._tail_complete_lines(fh, len(payload), 10)
    assert [json.loads(x)["message"] for x in out] == [f"line {i}" for i in range(19991, 20001)]
    assert CountingIO.read_total < 8 * 1024


def test_partial_trailing_line_is_ignored_until_complete(log_file: Path) -> None:
    _write(log_file, 1, 4)
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(_row(4)[:20])
    _, total, lines = tail_file_logs(limit=10)
    assert total == 3
    assert [x.id for x in lines] == [BASE + 1, BASE + 2, BASE + 3]

    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(_row(4)[20:] + "\n")
    _, total, lines = tail_file_logs(limit=10, after_id=BASE + 3)
    assert total == 4
    assert [(x.id, x.message) for x in lines] == [(BASE + 4, "line 4")]


def test_line_count_is_incremental(log_file: Path, monkeypatch) -> None:
    _write(log_file, 1, 101)
    calls: list[tuple[int, int]] = []
    real = lp._count_newlines

    def spy(fh, start: int, end: int) -> int:
        calls.append((start, end))
        return real(fh, start, end)

    monkeypatch.setattr(lp, "_count_newlines", spy)
    _, lines, size = file_log_stats()
    assert lines == 100
    assert calls == [(0, size)]

    _write(log_file, 101, 111)
    _, lines, new_size = file_log_stats()
    assert lines == 110
    assert calls[-1] == (size, new_size)

    calls.clear()
    assert file_log_stats()[1] == 110
    assert calls == []


def test_after_id_returns_only_new_lines(log_file: Path) -> None:
    _write(log_file, 1, 51)
    _, _, first = tail_file_logs(limit=400)
    last_id = first[-1].id
    assert last_id == BASE + 50

    _, _, none_new = tail_file_logs(limit=400, after_id=last_id)
    assert none_new == []

    _write(log_file, 51, 54)
    _, total, fresh = tail_file_logs(limit=400, after_id=last_id)
    assert total == 53
    assert [x.id for x in fresh] == [BASE + 51, BASE + 52, BASE + 53]

    _, _, capped = tail_file_logs(limit=2, after_id=last_id)
    assert [x.id for x in capped] == [BASE + 51, BASE + 52]


def test_rotation_resets_count_and_stale_after_id(log_file: Path) -> None:
    _write(log_file, 1, 201)
    assert file_log_stats()[1] == 200

    log_file.rename(log_file.with_name("app.jsonl.1"))
    _write(log_file, 1000, 1003, mode="w")
    _, total, lines = tail_file_logs(limit=10, after_id=BASE + 200)
    assert total == 3
    assert [x.message for x in lines] == ["line 1000", "line 1001", "line 1002"]
    assert [x.id for x in lines] == [BASE + 1, BASE + 2, BASE + 3]


def test_truncate_in_place_recounts(log_file: Path) -> None:
    _write(log_file, 1, 30)
    assert file_log_stats()[1] == 29
    _write(log_file, 500, 540, mode="w")
    assert file_log_stats()[1] == 40


def test_missing_file_and_disabled(tmp_path: Path, monkeypatch) -> None:
    missing = tmp_path / "nope" / "app.jsonl"
    monkeypatch.setattr(lp, "resolve_log_file_path", lambda: missing)
    assert tail_file_logs() == (str(missing), 0, [])
    assert file_log_stats() == (str(missing), 0, 0)
    monkeypatch.setattr(lp, "resolve_log_file_path", lambda: None)
    assert tail_file_logs() == (None, 0, [])
    assert file_log_stats() == (None, 0, None)


def test_runtime_logs_api_honors_after_id_for_file_source(log_file: Path) -> None:
    from app.api.runtime_logs import get_runtime_logs

    _write(log_file, 1, 11)

    def call(after_id: int, source: str = "file"):
        return get_runtime_logs(
            None, limit=300, level=None, logger=None, biz=None, q=None, after_id=after_id, source=source
        )

    full = call(0)
    assert full.file_lines == 10
    assert full.file_bytes == log_file.stat().st_size
    assert [x.message for x in full.lines][-1] == "line 10"
    _write(log_file, 11, 13)
    delta = call(full.lines[-1].id)
    assert [x.message for x in delta.lines] == ["line 11", "line 12"]
    assert delta.file_lines == 12


def test_lazy_handler_creates_directory_on_first_record(tmp_path: Path) -> None:
    target = tmp_path / "data" / "logs" / "app.jsonl"
    handler = lp._LazyDirRotatingFileHandler(
        target, maxBytes=1024 * 1024, backupCount=1, encoding="utf-8", delay=True
    )
    handler.setFormatter(lp.JsonLineLogFormatter())
    try:
        assert not target.parent.exists()
        record = logging.LogRecord("zhange.demo", logging.INFO, __file__, 1, "hello %s", ("x",), None)
        handler.emit(record)
        handler.flush()
        assert json.loads(target.read_text(encoding="utf-8"))["message"] == "hello x"
    finally:
        handler.close()
