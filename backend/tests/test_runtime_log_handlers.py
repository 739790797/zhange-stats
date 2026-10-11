"""平台日志 handler 挂在 root 与 uvicorn 的 logger 上：每次打日志，环缓冲与 JSONL 各只记一条。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from uvicorn.config import LOGGING_CONFIG

from app.core import log_persistence, runtime_log_buffer

_LOGGERS = (
    "",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "alembic",
    "alembic.runtime.migration",
    "app",
    "zhange",
    "sqlalchemy.engine",
)


def _apply_uvicorn_cli_logging() -> None:
    # `uvicorn app.main:app` 导入应用前 dictConfig 的级别与 propagate（不挂它的 stdout handler）
    for name, conf in LOGGING_CONFIG["loggers"].items():
        logger = logging.getLogger(name)
        logger.setLevel(conf["level"])
        if "propagate" in conf:
            logger.propagate = conf["propagate"]


@pytest.fixture
def fresh_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    log_file = tmp_path / "logs" / "app.jsonl"
    old = [h for h in (runtime_log_buffer._BUFFER, log_persistence._FILE_HANDLER) if h is not None]
    loggers = {name: logging.getLogger(name) for name in _LOGGERS}
    saved = {
        name: (lg.propagate, lg.level, [h for h in old if h in lg.handlers])
        for name, lg in loggers.items()
    }
    for name, lg in loggers.items():
        for handler in saved[name][2]:
            lg.removeHandler(handler)
    monkeypatch.setattr(runtime_log_buffer, "_BUFFER", None)
    monkeypatch.setattr(log_persistence, "_FILE_HANDLER", None)
    monkeypatch.setattr(log_persistence, "resolve_log_file_path", lambda: log_file)
    yield log_file
    fresh = [h for h in (runtime_log_buffer._BUFFER, log_persistence._FILE_HANDLER) if h is not None]
    for name, lg in loggers.items():
        propagate, level, removed = saved[name]
        for handler in fresh:
            lg.removeHandler(handler)
        for handler in removed:
            lg.addHandler(handler)
        lg.propagate = propagate
        lg.setLevel(level)
    for handler in fresh:
        handler.close()


@pytest.mark.parametrize("uvicorn_cli", [True, False], ids=["uvicorn-cli-logging", "all-propagate"])
def test_each_record_is_kept_once(fresh_install: Path, uvicorn_cli: bool) -> None:
    if uvicorn_cli:
        _apply_uvicorn_cli_logging()
    else:
        logging.getLogger("uvicorn").setLevel(logging.INFO)
    buffer = runtime_log_buffer.install_runtime_log_buffer(capacity=200)
    assert log_persistence._FILE_HANDLER is not None

    # uvicorn.access 被 configure_runtime_logging 压到 WARNING
    calls = (
        ("uvicorn.error", logging.INFO, "Shutting down"),
        ("uvicorn", logging.INFO, "uvicorn root line"),
        ("uvicorn.access", logging.WARNING, "access line"),
        ("alembic", logging.WARNING, "alembic line"),
        ("alembic.runtime.migration", logging.WARNING, "migration line"),
        ("zhange.test.once", logging.INFO, "app line"),
    )
    for index, (name, level, text) in enumerate(calls):
        logging.getLogger(name).log(level, "%s #%s", text, index)

    rows = [json.loads(line) for line in fresh_install.read_text(encoding="utf-8").splitlines()]
    for index, (name, _level, text) in enumerate(calls):
        message = f"{text} #{index}"
        _, lines = buffer.snapshot(limit=50, q=message)
        assert [(x.logger, x.message) for x in lines] == [(name, message)], name
        assert [r["logger"] for r in rows if r["message"] == message] == [name], name
