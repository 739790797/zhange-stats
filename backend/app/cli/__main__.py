"""Run registered sync tasks from Windows or Linux terminals."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Sequence

from app.core.biz_logging import record_timestamp


class _JobConsoleFormatter(logging.Formatter):
    def __init__(self, *, json_events: bool) -> None:
        super().__init__()
        self.json_events = json_events

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        if self.json_events:
            return json.dumps(
                {
                    "ts": record_timestamp(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": message,
                },
                ensure_ascii=False,
            )
        return f"{record_timestamp(record)} {record.levelname:<8} {record.name}: {message}"


def _configure_logging(*, json_events: bool) -> None:
    if json_events:
        # Structured events are consumed by the web process as UTF-8 JSON lines.
        # Keep the encoding explicit when stdout is redirected on Windows.
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(_JobConsoleFormatter(json_events=json_events))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)
    logging.getLogger("zhange").setLevel(logging.INFO)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    run_job = sub.add_parser("run-job", help="执行一个已登记的同步任务")
    run_job.add_argument("job_id")
    run_job.add_argument("--run-id", type=int, help=argparse.SUPPRESS)
    run_job.add_argument("--json-events", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _configure_logging(json_events=bool(args.json_events))

    from app.core.database import SessionLocal
    from app.services.job_run_progress import category_for_job
    from app.services.job_runner import SyncJobFailed, execute_sync_job
    from app.services.scheduler_runtime import resolve_sync_job_handler

    if category_for_job(args.job_id) is None:
        logging.getLogger("zhange.cli").error("未知同步任务：%s", args.job_id)
        return 2

    db = SessionLocal()
    try:
        try:
            handler = resolve_sync_job_handler(args.job_id, db)
        except (KeyError, RuntimeError) as exc:
            logging.getLogger("zhange.cli").error("无法启动任务：%s", exc)
            return 2
    finally:
        db.close()

    try:
        run_id, status = execute_sync_job(
            args.job_id,
            handler,
            run_id=args.run_id,
            capture_logs=not args.json_events,
        )
    except SyncJobFailed as exc:
        logging.getLogger("zhange.cli").error("任务失败：%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("zhange.cli").exception("任务执行异常：%s", exc)
        return 1

    logging.getLogger("zhange.cli").info(
        "任务结束 run_id=%s status=%s", run_id, status
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
