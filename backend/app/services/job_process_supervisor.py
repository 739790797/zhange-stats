"""Launch and supervise CLI child processes for manually triggered sync jobs."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
from queue import Empty, Queue
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from app.core.database import SessionLocal
from app.core.timeutil import now_naive, to_naive
from app.models.job_run import JobRun
from app.services.job_run_logs import JobRunLogEvent, append_job_run_logs
from app.services.job_run_progress import finish_manual_job_run, write_job_run

logger = logging.getLogger("zhange.job_process")
_LOCK = threading.Lock()
_PROCESSES: dict[int, "ManagedSyncProcess"] = {}
_STOPPING = threading.Event()
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ManagedSyncProcess:
    job_id: str
    run_id: int
    process: subprocess.Popen[str]
    monitor: threading.Thread | None = None
    on_finish: Callable[[], None] | None = None


def _platform_process_options(os_name: str) -> dict[str, object]:
    if os_name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _parse_log_line(raw: str) -> JobRunLogEvent:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if isinstance(payload, dict):
        level = str(payload.get("level") or "INFO").upper()
        logger_name = str(payload.get("logger") or "zhange.cli")
        message = str(payload.get("message") or "")
        raw_ts = str(payload.get("ts") or "")
        try:
            created_at = datetime.fromisoformat(raw_ts)
            created_at = to_naive(created_at)
        except ValueError:
            created_at = now_naive()
    else:
        level = "INFO"
        logger_name = "zhange.cli"
        message = raw.rstrip("\r\n")
        created_at = now_naive()
    if level not in {"INFO", "WARNING", "ERROR", "CRITICAL"}:
        level = "INFO"
    return JobRunLogEvent(
        level=level,
        logger=logger_name,
        message=message,
        created_at=created_at,
    )


def _read_run_state(run_id: int) -> tuple[str | None, str | None]:
    db = SessionLocal()
    try:
        row = db.get(JobRun, run_id)
        return (row.status, row.message) if row else (None, None)
    finally:
        db.close()


def _finalize_child(job_id: str, run_id: int, return_code: int) -> None:
    status, message = _read_run_state(run_id)
    if status not in {"queued", "running"}:
        return
    if _STOPPING.is_set():
        write_job_run(
            run_id,
            job_id,
            status="error",
            message="服务关闭，任务已中断",
            stats={"phase": "error", "result": {"summary": "服务关闭，任务已中断"}},
            finished=True,
        )
    elif return_code == 0:
        finish_manual_job_run(run_id, job_id)
    else:
        detail = f"同步命令退出，代码 {return_code}"
        write_job_run(
            run_id,
            job_id,
            status="error",
            message=detail if not message else f"{message[:350]}；{detail}",
            stats={"phase": "error", "result": {"summary": detail}},
            finished=True,
        )


def _monitor_process(entry: ManagedSyncProcess) -> None:
    process = entry.process
    output: Queue[str | None] = Queue()

    def _read_output() -> None:
        try:
            if process.stdout is not None:
                for line in process.stdout:
                    output.put(line)
        finally:
            output.put(None)

    reader = threading.Thread(
        target=_read_output,
        name=f"sync-process-output-{entry.run_id}",
        daemon=True,
    )
    reader_started = False
    try:
        reader.start()
        reader_started = True
        events: list[JobRunLogEvent] = []
        stream_finished = False
        while not stream_finished:
            try:
                line = output.get(timeout=0.25)
            except Empty:
                line = ""
            if line is None:
                stream_finished = True
            elif line:
                event = _parse_log_line(line)
                if event.message:
                    events.append(event)
            if events and (len(events) >= 25 or stream_finished or not line):
                append_job_run_logs(entry.run_id, events)
                events = []
        return_code = process.wait()
        _finalize_child(entry.job_id, entry.run_id, return_code)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "sync process monitor failed job_id=%s run_id=%s",
            entry.job_id,
            entry.run_id,
        )
        _terminate_process(process, timeout=2)
        write_job_run(
            entry.run_id,
            entry.job_id,
            status="error",
            message=f"无法读取同步进程输出：{exc}"[:500],
            stats={"phase": "error"},
            finished=True,
        )
    finally:
        if process.poll() is None:
            _terminate_process(process, timeout=2)
        if reader_started:
            reader.join(timeout=1)
        if process.stdout is not None:
            process.stdout.close()
        with _LOCK:
            _PROCESSES.pop(entry.run_id, None)
        if entry.on_finish is not None:
            try:
                entry.on_finish()
            except Exception:  # noqa: BLE001
                logger.exception("sync process completion callback failed run_id=%s", entry.run_id)


def launch_sync_job_process(
    job_id: str,
    run_id: int,
    *,
    on_finish: Callable[[], None] | None = None,
) -> None:
    """Start the same Python CLI used by operators, without invoking a shell."""
    command = [
        sys.executable,
        "-u",
        "-m",
        "app.cli",
        "run-job",
        job_id,
        "--run-id",
        str(run_id),
        "--json-events",
    ]
    options: dict[str, object] = {
        "args": command,
        "shell": False,
        "cwd": _BACKEND_ROOT,
        # The parent decodes this pipe as UTF-8. On Windows Python may otherwise
        # encode redirected stdout using the active locale code page.
        "env": {**os.environ, "PYTHONIOENCODING": "utf-8:replace"},
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }
    options.update(_platform_process_options(os.name))
    process = subprocess.Popen(**options)  # type: ignore[arg-type]
    entry = ManagedSyncProcess(job_id, run_id, process, on_finish=on_finish)
    monitor = threading.Thread(
        target=_monitor_process,
        args=(entry,),
        name=f"sync-process-monitor-{run_id}",
        daemon=True,
    )
    entry.monitor = monitor
    with _LOCK:
        _PROCESSES[run_id] = entry
    try:
        monitor.start()
    except Exception:
        with _LOCK:
            _PROCESSES.pop(run_id, None)
        _terminate_process(process, timeout=2)
        raise


def _terminate_process(process: subprocess.Popen[str], *, timeout: float) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ValueError):
        process.terminate()
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError):
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.error("sync child did not exit after force termination pid=%s", process.pid)


def stop_all_sync_job_processes(*, timeout: float = 5.0) -> None:
    """Terminate managed child process groups during application shutdown."""
    _STOPPING.set()
    with _LOCK:
        entries = list(_PROCESSES.values())
    for entry in entries:
        _terminate_process(entry.process, timeout=timeout)
    for entry in entries:
        if entry.monitor is not None:
            entry.monitor.join(timeout=timeout)
