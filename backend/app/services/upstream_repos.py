"""数据 git 仓库：浅克隆到安装根 data/repos，每天更新默认分支的全部文件。

接入一个仓库就是在 REPOS 登记并读本地树。不要再对该仓库请求单个 raw 文件。
pytest 注入 run，不执行 git、不访问 GitHub。
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath

from app.core.paths import resolve_install_dir

logger = logging.getLogger(__name__)

REPO_ENDFIELD = "endfield-data"
REPO_ARKNIGHTS = "arknights-game-resource"
REPO_TARKOV_OVERLAY = "tarkov-data-overlay"
REPO_TARKOV_SVG = "tarkov-dev-svg-maps"

REPO_SYNC_JOB_IDS = {
    REPO_ENDFIELD: "endfield_repo_sync",
    REPO_ARKNIGHTS: "arknights_repo_sync",
    REPO_TARKOV_OVERLAY: "tarkov_overlay_repo_sync",
    REPO_TARKOV_SVG: "tarkov_svg_repo_sync",
}

_CLONE_TIMEOUT_SEC = 30 * 60
_ERROR_LIMIT = 300


@dataclass(frozen=True)
class UpstreamRepo:
    repo_id: str
    url: str
    branch: str = "main"


REPOS: tuple[UpstreamRepo, ...] = (
    UpstreamRepo(REPO_ENDFIELD, "https://github.com/rmxlinux/EndfieldData.git"),
    UpstreamRepo(REPO_ARKNIGHTS, "https://github.com/yuanyan3060/ArknightsGameResource.git"),
    UpstreamRepo(REPO_TARKOV_OVERLAY, "https://github.com/MiwiDots/tarkov-data-overlay.git"),
    UpstreamRepo(REPO_TARKOV_SVG, "https://github.com/the-hideout/tarkov-dev-svg-maps.git"),
)

_BY_ID = {item.repo_id: item for item in REPOS}
_LOCK = threading.RLock()


class RepoError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RepoNotSyncedError(RepoError):
    """请求所需的数据仓尚未由同步任务克隆。"""

    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        super().__init__("上游数据仓尚未同步")


class RepoFileNotFound(RepoError):
    """仓库已就绪，但请求的仓库内文件不存在。"""


class RepoPathError(RepoError):
    """请求路径非法或通过链接越出仓库。"""


def _is_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


def repos_root() -> Path:
    return resolve_install_dir() / "data" / "repos"


def get_repo(repo_id: str) -> UpstreamRepo:
    spec = _BY_ID.get(repo_id)
    if spec is None:
        raise RepoError("未知数据仓")
    return spec


def repo_dir(repo_id: str) -> Path:
    spec = get_repo(repo_id)
    base = resolve_install_dir().resolve()
    repos = base / "data" / "repos"
    if _is_link(repos):
        raise RepoPathError("仓库目录不能是符号链接")
    actual_repos = repos.resolve()
    if not actual_repos.is_relative_to(base):
        raise RepoPathError("仓库目录越出安装根")
    dest = repos / spec.repo_id
    if _is_link(dest):
        raise RepoPathError("仓库目录不能是符号链接")
    if not dest.resolve().is_relative_to(actual_repos):
        raise RepoPathError("仓库目录越出仓库根")
    return dest


def resolve_repo_file(repo_id: str, relative: str) -> Path:
    """相对路径必须落在该克隆内。拒绝绝对路径、`..` 和指向克隆外的链接。"""
    spec = get_repo(repo_id)
    rel = (relative or "").replace("\\", "/").strip()
    if not rel or rel.startswith("/") or rel.startswith("~"):
        raise RepoPathError("路径越界")
    posix = PurePosixPath(rel)
    windows = PureWindowsPath(rel)
    parts = posix.parts
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or ".." in parts
    ):
        raise RepoPathError("路径越界")
    root = repo_dir(spec.repo_id).resolve()
    actual_repos = (resolve_install_dir().resolve() / "data" / "repos").resolve()
    if not root.is_relative_to(actual_repos):
        raise RepoPathError("路径越界")
    path = (root / rel).resolve()
    if not path.is_relative_to(root):
        raise RepoPathError("路径越界")
    if not path.is_file():
        raise RepoFileNotFound("文件不存在")
    return path


def read_repo_bytes(repo_id: str, relative: str) -> bytes:
    return resolve_repo_file(repo_id, relative).read_bytes()


def read_repo_text(repo_id: str, relative: str) -> str:
    return resolve_repo_file(repo_id, relative).read_text(encoding="utf-8")


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def _default_run(args: list[str]) -> GitResult:
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=_git_env(),
            bufsize=4096,
        )
    except FileNotFoundError as exc:
        raise RepoError("未找到 git") from exc

    timed_out = threading.Event()

    def _kill_if_timed_out() -> None:
        if proc.poll() is None:
            timed_out.set()
            try:
                proc.kill()
            except OSError:
                pass

    timer = threading.Timer(_CLONE_TIMEOUT_SEC, _kill_if_timed_out)
    timer.daemon = True
    timer.start()
    output = bytearray()
    progress_line = bytearray()
    try:
        if proc.stdout is not None:
            while True:
                chunk = proc.stdout.read1(4096)
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > 64 * 1024:
                    del output[: len(output) - 64 * 1024]
                for byte in chunk:
                    if byte in (10, 13):
                        if progress_line:
                            message = progress_line.decode("utf-8", errors="replace")
                            logger.info("git: %s", message[:1000])
                            progress_line.clear()
                    elif len(progress_line) < 4096:
                        progress_line.append(byte)
        if progress_line:
            logger.info(
                "git: %s",
                progress_line.decode("utf-8", errors="replace")[:1000],
            )
        returncode = proc.wait()
    finally:
        timer.cancel()
        if proc.stdout is not None:
            proc.stdout.close()

    if timed_out.is_set():
        raise RepoError("git 超时")
    combined_output = output.decode("utf-8", errors="replace")
    return GitResult(returncode, combined_output, "")


def _trim(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= _ERROR_LIMIT:
        return flat or "git 失败"
    return flat[:_ERROR_LIMIT]


def _check(result: GitResult) -> None:
    if result.returncode != 0:
        raise RepoError(_trim(result.stderr or result.stdout))


def _head(dest: Path, run) -> str | None:
    if not (dest / ".git").is_dir():
        return None
    result = run(["git", "-C", str(dest), "rev-parse", "HEAD"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _retry_remove_readonly(func, path: str, exc_info: tuple) -> None:
    """Windows marks Git pack files read-only; clear that bit before unlinking."""
    error = exc_info[1]
    if not isinstance(error, PermissionError) or os.path.islink(path):
        raise error

    mode = os.stat(path, follow_symlinks=False).st_mode
    os.chmod(path, mode | stat.S_IWRITE)
    func(path)


def _remove_staging(staging: Path) -> None:
    try:
        shutil.rmtree(staging, onerror=_retry_remove_readonly)
    except Exception:
        logger.warning(
            "failed to remove upstream repo staging directory path=%s",
            staging,
            exc_info=True,
        )
        raise


def _clone(dest: Path, spec: UpstreamRepo, run) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_name(dest.name + ".clone")
    if staging.exists():
        _remove_staging(staging)
    try:
        _check(
            run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    spec.branch,
                    "--single-branch",
                    "--progress",
                    spec.url,
                    str(staging),
                ]
            )
        )
        if not (staging / ".git").is_dir():
            raise RepoError("克隆结果不是 git 目录")
        staging.rename(dest)
    except Exception:
        if staging.exists():
            try:
                _remove_staging(staging)
            except Exception:
                # Keep the clone error as the task result; cleanup failure is logged above.
                pass
        raise


def _update(dest: Path, spec: UpstreamRepo, run) -> None:
    old_commit = _head(dest, run)
    _check(
        run(
            [
                "git",
                "-C",
                str(dest),
                "fetch",
                "--depth",
                "1",
                "--progress",
                "origin",
                spec.branch,
            ]
        )
    )
    result = run(["git", "-C", str(dest), "reset", "--hard", f"origin/{spec.branch}"])
    if result.returncode == 0:
        return
    if old_commit:
        rollback = run(["git", "-C", str(dest), "reset", "--hard", old_commit])
        if rollback.returncode != 0:
            logger.error(
                "upstream repo rollback failed: %s (%s)",
                dest.name,
                _trim(rollback.stderr or rollback.stdout),
            )
    raise RepoError(_trim(result.stderr or result.stdout))


def _sync_one(spec: UpstreamRepo, run) -> dict[str, object]:
    dest_path = repos_root() / spec.repo_id
    try:
        dest = repo_dir(spec.repo_id)
        if (dest / ".git").is_dir():
            _update(dest, spec, run)
        elif dest.exists():
            raise RepoError("目录已存在但不是 git 克隆")
        else:
            _clone(dest, spec, run)
        commit = _head(dest, run)
        return {"repo_id": spec.repo_id, "ok": True, "commit": commit, "error": None}
    except (RepoError, OSError) as exc:
        message = exc.message if isinstance(exc, RepoError) else _trim(str(exc))
        try:
            commit = (
                _head(dest_path, run)
                if dest_path.exists() and not _is_link(dest_path)
                else None
            )
        except RepoError:
            commit = None
        return {
            "repo_id": spec.repo_id,
            "ok": False,
            "commit": commit,
            "error": message,
        }


def sync_repo(repo_id: str, *, run=None) -> dict[str, object]:
    spec = get_repo(repo_id)
    runner = run or _default_run
    with _LOCK:
        return _sync_one(spec, runner)


def sync_all(*, run=None) -> list[dict[str, object]]:
    runner = run or _default_run
    with _LOCK:
        return [_sync_one(spec, runner) for spec in REPOS]


def ensure_repo(repo_id: str, *, run=None) -> Path:
    """仅读取已同步仓库；缺仓时由统一同步任务处理。"""
    _ = run  # 保留旧调用签名；请求路径不执行 Git。
    spec = get_repo(repo_id)
    with _LOCK:
        dest = repo_dir(spec.repo_id)
        if (dest / ".git").is_dir():
            return dest
        raise RepoNotSyncedError(spec.repo_id)


def upstream_repos_sync_job() -> None:
    rows = sync_all()
    parts: list[str] = []
    failed: list[str] = []
    for row in rows:
        repo_id = str(row["repo_id"])
        if row["ok"]:
            commit = str(row["commit"] or "")[:12]
            parts.append(f"{repo_id} {commit}")
        else:
            parts.append(f"{repo_id} failed")
            failed.append(f"{repo_id}: {row['error']}")
    logger.info("upstream repos sync: %s", "; ".join(parts))
    if failed:
        logger.warning("upstream repos sync failed: %s", "; ".join(failed))
        raise RepoError("; ".join(failed))


def upstream_repo_sync_job(repo_id: str, *, git_runner=None) -> None:
    """同步单个登记仓库，便于任务管理按游戏展示对应仓库链接。"""
    from app.core.database import SessionLocal
    from app.services.job_run_progress import create_or_reuse_job_run, write_job_run

    job_key = REPO_SYNC_JOB_IDS[repo_id]
    db = SessionLocal()
    try:
        run = create_or_reuse_job_run(
            db,
            job_key,
            message="正在同步外部仓库",
            stats={"phase": "check", "repo_id": repo_id},
        )
        db.commit()
        run_id = int(run.id)
    finally:
        db.close()

    write_job_run(
        run_id,
        job_key,
        message="正在拉取仓库更新",
        stats={"phase": "sync", "repo_id": repo_id},
    )
    row = sync_repo(repo_id, run=git_runner)
    if row["ok"]:
        commit = str(row["commit"] or "")
        summary = f"仓库已同步到 {commit[:12]}" if commit else "仓库已同步"
        write_job_run(
            run_id,
            job_key,
            status="ok",
            message=summary,
            stats={
                "phase": "done",
                "repo_id": repo_id,
                "commit": commit,
                "result": {"summary": summary, "repository": repo_id, "commit": commit},
            },
            finished=True,
        )
        logger.info("upstream repo sync: %s %s", repo_id, commit[:12])
        return

    error = str(row["error"] or "git 失败")
    write_job_run(
        run_id,
        job_key,
        status="error",
        message=f"{repo_id}: {error}",
        stats={
            "phase": "error",
            "repo_id": repo_id,
            "commit": str(row["commit"] or ""),
            "result": {
                "repository": repo_id,
                "commit": str(row["commit"] or ""),
                "summary": f"同步失败：{error}",
            },
        },
        finished=True,
    )
    logger.warning("upstream repo sync failed: %s: %s", repo_id, error)
    raise RepoError(f"{repo_id}: {error}")
