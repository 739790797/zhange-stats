"""CSP 上报聚合：来源只留 scheme://host，刷屏时每分钟最多一条 WARNING。"""

from __future__ import annotations

import json
import logging

import pytest

from app.services import csp_report as svc


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    now = {"t": 100.0}
    monkeypatch.setattr(svc, "_monotonic", lambda: now["t"])
    svc.reset_csp_reports_for_tests()
    yield now
    svc.reset_csp_reports_for_tests()


def _report(blocked: str, directive: str = "script-src-elem") -> bytes:
    return json.dumps(
        {"csp-report": {"blocked-uri": blocked, "effective-directive": directive}}
    ).encode("utf-8")


def _warnings(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "zhange.csp" and r.levelno == logging.WARNING]


def test_summarize_blocked_uri_drops_path_query_and_userinfo() -> None:
    assert svc.summarize_blocked_uri("https://evil.example:8443/a/b?token=abc") == "https://evil.example:8443"
    assert svc.summarize_blocked_uri("wss://user:pw@ws.example/x") == "wss://ws.example"
    assert svc.summarize_blocked_uri("inline") == "inline"
    assert svc.summarize_blocked_uri("eval") == "eval"
    assert svc.summarize_blocked_uri("data:image/png;base64,AAAA") == "data"
    assert svc.summarize_blocked_uri("blob:https://site.example/uuid") == "blob"
    assert svc.summarize_blocked_uri("") == "-"
    assert svc.summarize_blocked_uri("https://a.example/\nFAKE LOG LINE") == "https://a.example"


def test_parse_csp_report_shapes() -> None:
    assert svc.parse_csp_report(_report("https://x.example/p", "IMG-SRC")) == ("img-src", "https://x.example")
    legacy = json.dumps({"csp-report": {"blocked-uri": "inline", "violated-directive": "script-src 'self'"}})
    assert svc.parse_csp_report(legacy.encode()) == ("script-srcself", "inline")
    assert svc.parse_csp_report(b"") is None
    assert svc.parse_csp_report(b"not json") is None
    assert svc.parse_csp_report(b"[1, 2]") is None
    assert svc.parse_csp_report(b'{"csp-report": "x"}') is None


def test_flood_is_aggregated_once_per_minute(clock, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="zhange.csp"):
        svc.record_csp_report(_report("https://evil.example/first"))
        assert len(_warnings(caplog)) == 1

        for i in range(500):
            svc.record_csp_report(_report(f"https://evil.example/p{i}?token=s{i}"))
        svc.record_csp_report(b"garbage")
        clock["t"] += svc.FLUSH_INTERVAL_SEC - 1
        svc.record_csp_report(_report("https://evil.example/late"))
        assert len(_warnings(caplog)) == 1

        clock["t"] += 2
        svc.record_csp_report(_report("https://cdn.example/x.png", "img-src"))
        warnings = _warnings(caplog)
        assert len(warnings) == 2
        msg = warnings[1].getMessage()
        assert "reports=503" in msg
        assert "script-src-elem https://evil.example x501" in msg
        assert "- unparsable x1" in msg
        assert "img-src https://cdn.example x1" in msg
        assert "token" not in msg and "/p1" not in msg


def test_distinct_keys_are_capped(clock, caplog, monkeypatch) -> None:
    monkeypatch.setattr(svc, "MAX_DISTINCT_KEYS", 3)
    with caplog.at_level(logging.WARNING, logger="zhange.csp"):
        svc.record_csp_report(_report("https://h0.example/"))
        for i in range(1, 11):
            svc.record_csp_report(_report(f"https://h{i}.example/"))
        clock["t"] += svc.FLUSH_INTERVAL_SEC + 1
        svc.record_csp_report(_report("https://h1.example/"))
    msg = _warnings(caplog)[-1].getMessage()
    assert "distinct=3" in msg
    assert "other=7" in msg
    assert "reports=11" in msg
    assert "https://h1.example x2" in msg
