from __future__ import annotations

from pathlib import Path
import io
import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database
from app.models.job_run import JobRun
from app.services import upstream_repos as repos
from app.services import job_run_progress
from app.services.job_run_progress import create_queued_job_run, job_run_context


@pytest.fixture
def repo_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(repos, "resolve_install_dir", lambda: tmp_path)
    root = tmp_path / "data" / "repos"
    root.mkdir(parents=True)
    return root


def _fake_git(*, fail_fetch: bool = False, fail_reset: bool = False):
    flags = {"fail_fetch": fail_fetch, "fail_reset": fail_reset, "commands": []}

    def run(args: list[str]) -> repos.GitResult:
        flags["commands"].append(list(args))
        if args[1] == "clone":
            target = Path(args[-1])
            target.mkdir(parents=True)
            (target / ".git").mkdir()
            (target / ".git" / "HEAD").write_text("commit-one", encoding="utf-8")
            (target / "payload.json").write_text("old", encoding="utf-8")
            return repos.GitResult(0, "", "")

        target = Path(args[2])
        operation = args[3]
        if operation == "rev-parse":
            return repos.GitResult(0, (target / ".git" / "HEAD").read_text(encoding="utf-8"), "")
        if operation == "fetch":
            if flags["fail_fetch"]:
                return repos.GitResult(1, "", "network unavailable")
            return repos.GitResult(0, "", "")
        if operation == "reset":
            revision = args[5]
            if revision == "origin/main":
                (target / "payload.json").write_text("partially changed", encoding="utf-8")
                if flags["fail_reset"]:
                    return repos.GitResult(1, "", "checkout failed")
                (target / ".git" / "HEAD").write_text("commit-two", encoding="utf-8")
                (target / "payload.json").write_text("new", encoding="utf-8")
                return repos.GitResult(0, "", "")
            (target / ".git" / "HEAD").write_text(revision, encoding="utf-8")
            (target / "payload.json").write_text("old", encoding="utf-8")
            return repos.GitResult(0, "", "")
        raise AssertionError(f"unexpected git command: {args}")

    return run, flags


def test_arknights_clone_checks_out_full_tree_and_updates_incrementally(
    repo_home: Path,
) -> None:
    run, flags = _fake_git()

    first = repos.sync_repo(repos.REPO_ARKNIGHTS, run=run)
    clone_args = next(args for args in flags["commands"] if args[1] == "clone")
    assert first["ok"] is True
    assert clone_args == [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        "main",
        "--single-branch",
        "--progress",
        repos.get_repo(repos.REPO_ARKNIGHTS).url,
        str(repo_home / f"{repos.REPO_ARKNIGHTS}.clone"),
    ]
    assert all(not arg.startswith("--filter") for arg in clone_args)
    assert "--sparse" not in clone_args
    assert (repo_home / repos.REPO_ARKNIGHTS / "payload.json").is_file()

    second = repos.sync_repo(repos.REPO_ARKNIGHTS, run=run)
    fetch_args = [
        args for args in flags["commands"] if len(args) > 3 and args[3] == "fetch"
    ][-1]
    assert second["ok"] is True
    assert fetch_args == [
        "git",
        "-C",
        str(repo_home / repos.REPO_ARKNIGHTS),
        "fetch",
        "--depth",
        "1",
        "--progress",
        "origin",
        "main",
    ]


def test_git_command_runner_defaults_to_thirty_minutes_and_accepts_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    timeouts: list[float] = []

    class FakeTimer:
        def __init__(self, interval, _function, *, args=(), kwargs=None):
            timeouts.append(interval)

        def start(self) -> None:
            pass

        def cancel(self) -> None:
            pass

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = io.BytesIO(b"")
            self.returncode = 0

        def poll(self) -> int:
            return self.returncode

        def wait(self) -> int:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    def fake_popen(args, **kwargs):
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr(repos.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(repos.threading, "Timer", FakeTimer)

    default = repos._default_run(["git", "clone"])
    custom = repos._default_run(["git", "fetch"], timeout_seconds=95)

    assert default.returncode == custom.returncode == 0
    assert calls == [["git", "clone"], ["git", "fetch"]]
    assert timeouts == [30 * 60, 95]


def test_git_command_runner_kills_process_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_holder = []

    class BlockingStdout:
        def __init__(self, exited: threading.Event) -> None:
            self.exited = exited

        def read1(self, _size: int) -> bytes:
            self.exited.wait(timeout=1)
            return b""

        def close(self) -> None:
            pass

    class FakeProcess:
        def __init__(self) -> None:
            self.exited = threading.Event()
            self.stdout = BlockingStdout(self.exited)
            self.killed = False

        def poll(self):
            return -9 if self.exited.is_set() else None

        def kill(self) -> None:
            self.killed = True
            self.exited.set()

        def wait(self) -> int:
            self.exited.wait(timeout=1)
            return -9 if self.killed else 0

    def fake_popen(_args, **_kwargs):
        process = FakeProcess()
        process_holder.append(process)
        return process

    monkeypatch.setattr(repos.subprocess, "Popen", fake_popen)

    with pytest.raises(repos.RepoTimeoutError, match="fake sync timeout"):
        repos._default_run(
            ["git", "clone"],
            timeout_seconds=0.01,
            timeout_message="fake sync timeout",
        )

    assert process_holder[0].killed is True


def test_git_progress_logs_milestones_and_diagnostics_not_each_path(caplog) -> None:
    caplog.set_level("INFO", logger=repos.logger.name)
    progress: dict[str, int] = {}
    repos._log_git_line("Updating files: 11% (3/27)", progress)
    repos._log_git_line("Updating files: 15% (4/27)", progress)
    repos._log_git_line("Updating files: 20% (6/27)", progress)
    repos._log_git_line("  'portrait/char_fixture_ambience.png'", progress)
    repos._log_git_line("warning: paths collided on a case-insensitive filesystem", progress)

    infos = [record.message for record in caplog.records if record.levelname == "INFO"]
    warnings = [record.message for record in caplog.records if record.levelname == "WARNING"]
    assert len(infos) == 2
    assert all("portrait/" not in message for message in infos)
    assert warnings == ["git: warning: paths collided on a case-insensitive filesystem"]


def test_readonly_remove_retries_transient_permission_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "pack.idx"
    target.write_bytes(b"pack index")
    calls = 0

    def flaky_unlink(path: str) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError(5, "sharing violation", path)
        repos.os.unlink(path)

    monkeypatch.setattr(repos.time, "sleep", lambda _delay: None)
    initial_error = PermissionError(5, "access denied", str(target))
    repos._retry_remove_readonly(
        flaky_unlink,
        str(target),
        (PermissionError, initial_error, None),
    )

    assert calls == 3
    assert not target.exists()


def test_clone_removes_stale_readonly_pack_before_fresh_clone(
    repo_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = repo_home / f"{repos.REPO_ARKNIGHTS}.clone"
    pack_dir = staging / ".git" / "objects" / "pack"
    pack_dir.mkdir(parents=True)
    readonly_files = [pack_dir / "pack-test.idx", pack_dir / "pack-test.pack"]
    for path in readonly_files:
        path.write_bytes(b"stale")
        path.chmod(0o444)

    real_rmtree = repos.shutil.rmtree
    retried: list[Path] = []

    def windows_rmtree(path, *, onerror=None, ignore_errors=False):
        if onerror is not None:
            for readonly in readonly_files:
                if readonly.exists():
                    error = PermissionError(5, "Access is denied", str(readonly))
                    onerror(
                        repos.os.unlink,
                        str(readonly),
                        (PermissionError, error, None),
                    )
                    retried.append(readonly)
        return real_rmtree(path, ignore_errors=ignore_errors)

    monkeypatch.setattr(repos.shutil, "rmtree", windows_rmtree)
    run, _flags = _fake_git()

    result = repos.sync_repo(repos.REPO_ARKNIGHTS, run=run)

    assert result["ok"] is True
    assert result["commit"] == "commit-one"
    assert len(retried) == 2
    assert not staging.exists()
    assert (repo_home / repos.REPO_ARKNIGHTS / "payload.json").read_text(encoding="utf-8") == "old"


def test_clone_cleanup_failure_preserves_git_error(
    repo_home: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    staging = repo_home / f"{repos.REPO_ARKNIGHTS}.clone"
    pack_index = staging / ".git" / "objects" / "pack" / "pack-test.idx"

    def failed_clone(args: list[str]) -> repos.GitResult:
        if args[1] == "clone":
            pack_index.parent.mkdir(parents=True)
            pack_index.write_bytes(b"stale")
            return repos.GitResult(1, "", "clone failed")
        raise AssertionError(f"unexpected git command: {args}")

    def denied_chmod(path, mode):
        raise PermissionError(5, "Access is denied", str(path))

    def windows_rmtree(path, *, onerror=None, ignore_errors=False):
        assert onerror is not None
        error = PermissionError(5, "Access is denied", str(pack_index))
        onerror(repos.os.unlink, str(pack_index), (PermissionError, error, None))

    monkeypatch.setattr(repos.shutil, "rmtree", windows_rmtree)
    monkeypatch.setattr(repos.os, "chmod", denied_chmod)
    monkeypatch.setattr(repos.time, "sleep", lambda _delay: None)

    result = repos.sync_repo(repos.REPO_ARKNIGHTS, run=failed_clone)

    assert result["ok"] is False
    assert result["error"] == "clone failed"
    assert staging.exists()
    assert any(
        "failed to remove upstream repo staging directory" in record.message
        and "Access is denied" in record.message
        and record.exc_info is None
        for record in caplog.records
    )


def test_shallow_clone_and_update_failure_keep_old_checkout(repo_home: Path) -> None:
    run, flags = _fake_git()
    cloned = repos.sync_repo(repos.REPO_ENDFIELD, run=run)
    checkout = repo_home / repos.REPO_ENDFIELD
    assert cloned["ok"] is True
    assert cloned["commit"] == "commit-one"
    assert (checkout / "payload.json").read_text(encoding="utf-8") == "old"

    flags["fail_reset"] = True
    failed = repos.sync_repo(repos.REPO_ENDFIELD, run=run)
    assert failed["ok"] is False
    assert failed["commit"] == "commit-one"
    assert (checkout / "payload.json").read_text(encoding="utf-8") == "old"

    flags["fail_reset"] = False
    updated = repos.sync_repo(repos.REPO_ENDFIELD, run=run)
    assert updated["ok"] is True
    assert updated["commit"] == "commit-two"
    assert (checkout / "payload.json").read_text(encoding="utf-8") == "new"


def test_fetch_failure_keeps_existing_checkout(repo_home: Path) -> None:
    run, flags = _fake_git()
    repos.sync_repo(repos.REPO_ENDFIELD, run=run)
    flags["fail_fetch"] = True
    result = repos.sync_repo(repos.REPO_ENDFIELD, run=run)
    checkout = repo_home / repos.REPO_ENDFIELD
    assert result["ok"] is False
    assert result["commit"] == "commit-one"
    assert (checkout / "payload.json").read_text(encoding="utf-8") == "old"


def test_manual_repo_sync_reuses_queued_run_and_records_repository_result(
    repo_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    JobRun.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(job_run_progress, "SessionLocal", session_factory)
    monkeypatch.setattr(
        repos, "_configured_repo_sync_timeout_minutes", lambda _repo_id: 95
    )

    timeout_values: list[float] = []
    original_sync_repo = repos.sync_repo

    def record_sync_timeout(
        repo_id: str,
        *,
        run=None,
        timeout_seconds: float,
    ) -> dict[str, object]:
        timeout_values.append(timeout_seconds)
        return original_sync_repo(
            repo_id,
            run=run,
            timeout_seconds=timeout_seconds,
        )

    monkeypatch.setattr(repos, "sync_repo", record_sync_timeout)
    job_key = repos.REPO_SYNC_JOB_IDS[repos.REPO_ARKNIGHTS]
    with session_factory() as db:
        queued = create_queued_job_run(db, job_key, "repository")
        run_id = queued.id

    git_runner, _flags = _fake_git()
    with job_run_context(job_key, run_id):
        repos.upstream_repo_sync_job(repos.REPO_ARKNIGHTS, git_runner=git_runner)

    with session_factory() as db:
        rows = db.scalars(select(JobRun).where(JobRun.job_key == job_key)).all()

    assert len(rows) == 1
    assert rows[0].id == run_id
    assert rows[0].status == "ok"
    assert rows[0].stats["schema_version"] == 1
    assert rows[0].stats["category"] == "repository"
    assert rows[0].stats["result"]["repository"] == repos.REPO_ARKNIGHTS
    assert rows[0].stats["result"]["commit"] == "commit-one"
    assert timeout_values == [95 * 60]
    engine.dispose()


def test_tarkov_svg_reads_are_not_blocked_by_arknights_sync(
    repo_home: Path,
) -> None:
    svg_repo = repo_home / repos.REPO_TARKOV_SVG
    (svg_repo / ".git").mkdir(parents=True)
    (svg_repo / "customs.svg").write_text("<svg />", encoding="utf-8")

    started = threading.Event()
    release = threading.Event()
    sync_rows: list[dict[str, object]] = []
    base_run, _flags = _fake_git()

    def blocking_run(args: list[str]) -> repos.GitResult:
        started.set()
        if not release.wait(timeout=3):
            raise AssertionError("test did not release blocked Git runner")
        return base_run(args)

    sync_thread = threading.Thread(
        target=lambda: sync_rows.append(
            repos.sync_repo(repos.REPO_ARKNIGHTS, run=blocking_run)
        ),
        daemon=True,
    )
    sync_thread.start()
    reader_done = threading.Event()
    read_rows: list[str] = []
    reader_thread = threading.Thread(
        target=lambda: (
            read_rows.append(repos.read_repo_text(repos.REPO_TARKOV_SVG, "customs.svg")),
            reader_done.set(),
        ),
        daemon=True,
    )
    try:
        assert started.wait(timeout=1)
        reader_thread.start()
        assert reader_done.wait(timeout=0.5)
    finally:
        release.set()
        sync_thread.join(timeout=3)
        if reader_thread.ident is not None:
            reader_thread.join(timeout=3)

    assert read_rows == ["<svg />"]
    assert sync_rows and sync_rows[0]["ok"] is True


def test_ensure_repo_requires_the_sync_job_to_clone_missing_repository(
    repo_home: Path,
) -> None:
    run, _flags = _fake_git()
    with pytest.raises(repos.RepoNotSyncedError):
        repos.ensure_repo(repos.REPO_ENDFIELD, run=run)
    assert not (repo_home / repos.REPO_ENDFIELD).exists()
    assert not (repo_home / repos.REPO_ARKNIGHTS).exists()


def test_unknown_repo_is_rejected() -> None:
    with pytest.raises(repos.RepoError, match="未知数据仓"):
        repos.get_repo("../../outside")


def test_repo_file_rejects_traversal_and_reports_missing(repo_home: Path) -> None:
    checkout = repo_home / repos.REPO_ENDFIELD
    (checkout / ".git").mkdir(parents=True)
    (checkout / "ok.txt").write_text("ok", encoding="utf-8")
    assert repos.resolve_repo_file(repos.REPO_ENDFIELD, "ok.txt").read_text(encoding="utf-8") == "ok"
    for unsafe in ("../outside.txt", "C:/outside.txt", "/outside.txt"):
        with pytest.raises(repos.RepoPathError):
            repos.resolve_repo_file(repos.REPO_ENDFIELD, unsafe)
    with pytest.raises(repos.RepoFileNotFound):
        repos.resolve_repo_file(repos.REPO_ENDFIELD, "missing.txt")


def test_repo_file_allows_internal_link_and_rejects_external_link(
    repo_home: Path, tmp_path: Path
) -> None:
    checkout = repo_home / repos.REPO_ENDFIELD
    (checkout / ".git").mkdir(parents=True)
    (checkout / "source.txt").write_text("inside", encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        (checkout / "inside-link.txt").symlink_to(checkout / "source.txt")
        (checkout / "outside-link.txt").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    assert repos.resolve_repo_file(repos.REPO_ENDFIELD, "inside-link.txt").read_text(encoding="utf-8") == "inside"
    with pytest.raises(repos.RepoPathError):
        repos.resolve_repo_file(repos.REPO_ENDFIELD, "outside-link.txt")
