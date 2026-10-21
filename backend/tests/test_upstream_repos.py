from __future__ import annotations

from pathlib import Path

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
    flags = {"fail_fetch": fail_fetch, "fail_reset": fail_reset}

    def run(args: list[str]) -> repos.GitResult:
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

    result = repos.sync_repo(repos.REPO_ARKNIGHTS, run=failed_clone)

    assert result["ok"] is False
    assert result["error"] == "clone failed"
    assert staging.exists()
    assert any(
        "failed to remove upstream repo staging directory" in record.message
        and record.exc_info is not None
        and isinstance(record.exc_info[1], PermissionError)
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

    job_key = repos.REPO_SYNC_JOB_IDS[repos.REPO_ENDFIELD]
    with session_factory() as db:
        queued = create_queued_job_run(db, job_key, "repository")
        run_id = queued.id

    git_runner, _flags = _fake_git()
    with job_run_context(job_key, run_id):
        repos.upstream_repo_sync_job(repos.REPO_ENDFIELD, git_runner=git_runner)

    with session_factory() as db:
        rows = db.scalars(select(JobRun).where(JobRun.job_key == job_key)).all()

    assert len(rows) == 1
    assert rows[0].id == run_id
    assert rows[0].status == "ok"
    assert rows[0].stats["schema_version"] == 1
    assert rows[0].stats["category"] == "repository"
    assert rows[0].stats["result"]["repository"] == repos.REPO_ENDFIELD
    assert rows[0].stats["result"]["commit"] == "commit-one"
    engine.dispose()


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
