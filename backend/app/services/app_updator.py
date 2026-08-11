"""AstrBot-style self-update: GitHub Release zip + static asset + pip + restart."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Relative to install root — only these are overwritten from source zip.
SOURCE_WHITELIST: tuple[str, ...] = (
    "VERSION",
    "backend/app",
    "backend/alembic",
    "backend/requirements.txt",
    "backend/requirements-dev.txt",
    "backend/scripts",
    "scripts",
    "deploy",
    "AGENTS.md",
    "README.md",
)

PROTECTED_PREFIXES: tuple[str, ...] = (
    ".env",
    "data/",
    "uploads/",
    "backend/.venv/",
    "frontend/node_modules/",
    "static/",  # replaced only via static asset, not source zip
)

_state_lock = threading.Lock()
_progress: dict[str, Any] = {
    "busy": False,
    "phase": "",
    "message": "",
    "error": "",
    "target_version": "",
}

# Status / 侧栏红点轮询会打 GitHub；默认 15 分钟缓存（手动「检查更新」force 刷新）
CHECK_CACHE_TTL_SEC = 15 * 60
_check_cache_lock = threading.Lock()
_check_cache: dict[str, Any] = {
    "expires_at": 0.0,
    "latest": None,
    "releases": None,
    "fetched": False,
}


class _UpdateLock:
    """Thread mutex + optional POSIX file lock under DATA_DIR/update.lock."""

    def __init__(self) -> None:
        self._thread = threading.Lock()
        self._fd: Any = None

    def acquire(self, *, blocking: bool = False) -> bool:
        if not self._thread.acquire(blocking=blocking):
            return False
        try:
            settings = get_settings()
            install = resolve_install_dir()
            data = Path(settings.DATA_DIR).expanduser()
            if not data.is_absolute():
                data = (install / data).resolve()
            data.mkdir(parents=True, exist_ok=True)
            lock_path = data / "update.lock"
            try:
                fd = open(lock_path, "a+", encoding="utf-8")  # noqa: SIM115
            except PermissionError as e:
                self._thread.release()
                raise PermissionError(_writable_hint(lock_path)) from e
            try:
                if sys.platform != "win32":
                    import fcntl

                    flags = fcntl.LOCK_EX
                    if not blocking:
                        flags |= fcntl.LOCK_NB
                    fcntl.flock(fd.fileno(), flags)
            except OSError:
                fd.close()
                self._thread.release()
                return False
            self._fd = fd
            fd.seek(0)
            fd.truncate()
            fd.write(f"pid={os.getpid()}\n")
            fd.flush()
            return True
        except PermissionError:
            raise
        except Exception:
            if self._fd is not None:
                try:
                    self._fd.close()
                except Exception:
                    pass
                self._fd = None
            self._thread.release()
            raise

    def release(self) -> None:
        try:
            if self._fd is not None:
                if sys.platform != "win32":
                    try:
                        import fcntl

                        fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                try:
                    self._fd.close()
                except Exception:
                    pass
                self._fd = None
        finally:
            if self._thread.locked():
                self._thread.release()


_lock = _UpdateLock()


@dataclass
class ReleaseInfo:
    tag_name: str
    name: str
    body: str
    published_at: str
    zipball_url: str
    static_asset_url: str | None = None
    static_asset_name: str | None = None


@dataclass
class UpdateResult:
    ok: bool
    message: str
    version: str = ""
    reboot: bool = False


@dataclass
class UpdateStatus:
    current_version: str
    install_dir: str
    update_allowed: bool
    update_blocked_reason: str = ""
    has_new_version: bool = False
    latest_version: str = ""
    latest_body: str = ""
    latest_published_at: str = ""
    busy: bool = False
    phase: str = ""
    message: str = ""
    error: str = ""
    restart_strategy: str = ""


def _set_progress(**kwargs: Any) -> None:
    with _state_lock:
        _progress.update(kwargs)


def get_progress() -> dict[str, Any]:
    with _state_lock:
        return dict(_progress)


def compare_version(v1: str, v2: str) -> int:
    """Semver-ish compare. Returns >0 if v1>v2, 0 if equal, <0 if v1<v2."""

    def parts(v: str) -> list[int]:
        s = (v or "").strip().lstrip("vV")
        nums: list[int] = []
        for chunk in re.split(r"[^\d]+", s):
            if chunk.isdigit():
                nums.append(int(chunk))
        return nums or [0]

    a, b = parts(v1), parts(v2)
    n = max(len(a), len(b))
    a.extend([0] * (n - len(a)))
    b.extend([0] * (n - len(b)))
    for x, y in zip(a, b, strict=True):
        if x != y:
            return (x > y) - (x < y)
    return 0


def resolve_install_dir() -> Path:
    settings = get_settings()
    raw = (settings.APP_INSTALL_DIR or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    # Prefer repo root that contains VERSION next to backend/
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[3],  # .../zhange-stats from backend/app/services/
        Path.cwd().parent if Path.cwd().name == "backend" else Path.cwd(),
        Path.cwd(),
    ):
        if (candidate / "VERSION").is_file() and (candidate / "backend").is_dir():
            return candidate.resolve()
    return Path.cwd().resolve()


def _writable_hint(path: Path) -> str:
    return (
        f"安装路径不可写：{path}。"
        "请确保安装树属主为运行服务的用户（如 zhange），"
        f"例如：chown -R zhange:zhange {path if path.is_dir() else path.parent}"
    )


def _check_install_writable(install: Path) -> tuple[bool, str]:
    """Ensure service user can overwrite whitelist paths / update lock."""
    settings = get_settings()
    data = Path(settings.DATA_DIR).expanduser()
    if not data.is_absolute():
        data = (install / data).resolve()
    candidates = [
        install / "VERSION",
        install / "backend" / "app",
        install / "static",
        data,
        data / "update.lock",
    ]
    for path in candidates:
        if not path.exists():
            # parent must be writable so we can create it
            parent = path.parent if path.name == "update.lock" else path
            if path.name == "update.lock":
                parent = data
            if parent.exists() and not os.access(parent, os.W_OK):
                return False, _writable_hint(parent)
            continue
        if not os.access(path, os.W_OK):
            return False, _writable_hint(path)
    return True, ""


def update_allowed() -> tuple[bool, str]:
    settings = get_settings()
    if not settings.allow_in_app_update:
        return False, "当前环境不允许应用内更新（仅 production 默认开启，或设置 ALLOW_IN_APP_UPDATE=true）"
    install = resolve_install_dir()
    if not (install / "VERSION").is_file():
        return False, f"安装根无效：未找到 VERSION（APP_INSTALL_DIR={install}）"
    if not (install / "backend" / "app").is_dir():
        return False, f"安装根无效：缺少 backend/app（APP_INSTALL_DIR={install}）"
    ok, reason = _check_install_writable(install)
    if not ok:
        return False, reason
    return True, ""


def _proxy_url(url: str, proxy: str | None) -> str:
    if not proxy:
        return url
    p = proxy.rstrip("/")
    if url.startswith("https://") or url.startswith("http://"):
        return f"{p}/{url}"
    return urljoin(p + "/", url)


def _releases_api_url() -> str:
    settings = get_settings()
    base = (settings.UPDATE_GITHUB_API or "https://api.github.com").rstrip("/")
    repo = (settings.UPDATE_GITHUB_REPO or "739790797/zhange-stats").strip()
    return f"{base}/repos/{repo}/releases"


def _static_asset_name(version: str) -> str:
    ver = version.lstrip("vV")
    return f"zhange-stats-{ver}-static.tar.gz"


async def fetch_releases(limit: int = 20, proxy: str | None = None) -> list[ReleaseInfo]:
    settings = get_settings()
    url = _proxy_url(_releases_api_url(), proxy)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"zhange-stats/{settings.APP_VERSION}",
    }
    token = ""
    try:
        from app.services.integrations_config import get_github_token

        token = (get_github_token() or "").strip()
    except Exception:  # noqa: BLE001
        token = (settings.UPDATE_GITHUB_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("GitHub Releases 响应格式异常")

    out: list[ReleaseInfo] = []
    for item in data[:limit]:
        tag = str(item.get("tag_name") or "")
        assets = item.get("assets") or []
        static_url = None
        static_name = None
        want = _static_asset_name(tag)
        for asset in assets:
            name = str(asset.get("name") or "")
            if name == want or name.endswith("-static.tar.gz"):
                static_url = asset.get("browser_download_url")
                static_name = name
                if name == want:
                    break
        out.append(
            ReleaseInfo(
                tag_name=tag,
                name=str(item.get("name") or tag),
                body=str(item.get("body") or ""),
                published_at=str(item.get("published_at") or ""),
                zipball_url=str(item.get("zipball_url") or ""),
                static_asset_url=static_url,
                static_asset_name=static_name,
            )
        )
    return out


def invalidate_check_cache() -> None:
    with _check_cache_lock:
        _check_cache["expires_at"] = 0.0
        _check_cache["latest"] = None
        _check_cache["releases"] = None
        _check_cache["fetched"] = False


def _read_check_cache() -> tuple[ReleaseInfo | None, list[ReleaseInfo]] | None:
    with _check_cache_lock:
        if not _check_cache.get("fetched"):
            return None
        if time.monotonic() >= float(_check_cache.get("expires_at") or 0):
            return None
        latest = _check_cache.get("latest")
        releases = _check_cache.get("releases")
        if not isinstance(releases, list):
            return None
        return latest, releases


def _write_check_cache(latest: ReleaseInfo | None, releases: list[ReleaseInfo]) -> None:
    with _check_cache_lock:
        _check_cache["latest"] = latest
        _check_cache["releases"] = list(releases)
        _check_cache["fetched"] = True
        _check_cache["expires_at"] = time.monotonic() + CHECK_CACHE_TTL_SEC


async def check_update(
    proxy: str | None = None,
    *,
    force: bool = False,
) -> tuple[ReleaseInfo | None, list[ReleaseInfo]]:
    # 带 proxy 的检查不走共享缓存（避免污染直连结果）
    if not force and not (proxy or "").strip():
        cached = _read_check_cache()
        if cached is not None:
            return cached

    settings = get_settings()
    releases = await fetch_releases(proxy=proxy)
    current = settings.APP_VERSION
    latest: ReleaseInfo | None = None
    for rel in releases:
        if compare_version(rel.tag_name, current) > 0:
            latest = rel
            break
    if not (proxy or "").strip():
        _write_check_cache(latest, releases)
    return latest, releases


def detect_restart_strategy() -> str:
    """Post-update restart: AstrBot-style in-process ``os.execv`` only."""
    return "exec"


def _build_reboot_argv(executable: str) -> list[str]:
    """Rebuild argv for os.execv so the same uvicorn/app entry comes back up."""
    argv0 = Path(sys.argv[0]).name.lower() if sys.argv else ""
    # ``python -m uvicorn ...`` → argv is already python-friendly
    if argv0 in {"python", "python3", "python.exe", "pythonw.exe"}:
        return [executable, *sys.argv[1:]]
    # Console script e.g. ``.../bin/uvicorn app.main:app ...``
    return [executable, *sys.argv]


def trigger_restart(*, delay_sec: float = 1.5) -> None:
    """AstrBot-style reboot: replace *this* process image after a short delay.

    Must only be called from the running app (uvicorn) process — never from a
    one-shot CLI, or exec would restart the wrong program.
    """

    def _run() -> None:
        time.sleep(delay_sec)
        strategy = detect_restart_strategy()
        logger.warning("self-update restart via %s", strategy)
        try:
            executable = sys.executable
            argv = _build_reboot_argv(executable)
            logger.warning("self-update execv executable=%s argv=%s", executable, argv)
            os.execv(executable, argv)
        except Exception:
            logger.exception("重启失败，请手动 systemctl restart zhange-stats")

    threading.Thread(target=_run, name="zhange-self-update-restart", daemon=True).start()


def build_status(
    *,
    latest: ReleaseInfo | None = None,
    releases_checked: bool = False,
) -> UpdateStatus:
    settings = get_settings()
    allowed, reason = update_allowed()
    progress = get_progress()
    install = str(resolve_install_dir())
    has_new = False
    latest_version = ""
    latest_body = ""
    latest_published = ""
    if latest is not None:
        latest_version = latest.tag_name.lstrip("vV")
        latest_body = latest.body
        latest_published = latest.published_at
        has_new = compare_version(latest.tag_name, settings.APP_VERSION) > 0
    elif not releases_checked:
        pass
    return UpdateStatus(
        current_version=settings.APP_VERSION,
        install_dir=install,
        update_allowed=allowed,
        update_blocked_reason=reason,
        has_new_version=has_new,
        latest_version=latest_version,
        latest_body=latest_body,
        latest_published_at=latest_published,
        busy=bool(progress.get("busy")),
        phase=str(progress.get("phase") or ""),
        message=str(progress.get("message") or ""),
        error=str(progress.get("error") or ""),
        restart_strategy=detect_restart_strategy(),
    )


async def _download(url: str, dest: Path, proxy: str | None = None) -> None:
    """Download URL to dest.

    Do **not** forward Authorization across redirects to codeload/objects CDN —
    GitHub rejects that and zipball/asset downloads fail.
    """
    final = _proxy_url(url, proxy)
    settings = get_settings()
    base_headers = {"User-Agent": f"zhange-stats/{settings.APP_VERSION}"}
    token = ""
    try:
        from app.services.integrations_config import get_github_token

        token = (get_github_token() or "").strip()
    except Exception:  # noqa: BLE001
        token = (settings.UPDATE_GITHUB_TOKEN or "").strip()

    dest.parent.mkdir(parents=True, exist_ok=True)

    def _headers_for(u: str) -> dict[str, str]:
        h = dict(base_headers)
        if not token:
            return h
        # Token only on GitHub API / release asset hosts — never on codeload CDN
        host = ""
        try:
            from urllib.parse import urlparse

            host = (urlparse(u).hostname or "").lower()
        except Exception:  # noqa: BLE001
            host = ""
        if host in {"api.github.com", "github.com", "www.github.com"}:
            h["Authorization"] = f"Bearer {token}"
            if "/releases/download/" in u:
                h["Accept"] = "application/octet-stream"
        return h

    async with httpx.AsyncClient(timeout=300.0, follow_redirects=False) as client:
        current = final
        for _ in range(12):
            resp = await client.send(
                client.build_request("GET", current, headers=_headers_for(current)),
                stream=True,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                loc = resp.headers.get("location") or ""
                await resp.aclose()
                if not loc:
                    raise RuntimeError(f"下载重定向缺少 Location（HTTP {resp.status_code}）")
                current = urljoin(current, loc)
                continue
            try:
                resp.raise_for_status()
                with dest.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
            finally:
                await resp.aclose()
            return
        raise RuntimeError("下载重定向次数过多")


def _resolve_target_release(
    releases: list[ReleaseInfo],
    version: str,
    current_version: str,
) -> ReleaseInfo | UpdateResult:
    """Return target ReleaseInfo, or UpdateResult on soft failure."""
    if not releases:
        return UpdateResult(ok=False, message="未获取到任何 GitHub Release")
    ver = (version or "latest").strip()
    if ver in ("", "latest"):
        target = releases[0]
        if compare_version(target.tag_name, current_version) <= 0:
            return UpdateResult(
                ok=False,
                message=f"当前已经是最新版本（{current_version}）",
                version=current_version,
            )
        return target
    want = ver if ver.startswith("v") else f"v{ver}"
    for rel in releases:
        if rel.tag_name == want or rel.tag_name.lstrip("vV") == ver.lstrip("vV"):
            return rel
    return UpdateResult(ok=False, message=f"未找到版本 {ver}")


def _is_protected(rel_posix: str) -> bool:
    r = rel_posix.lstrip("./")
    for p in PROTECTED_PREFIXES:
        if p.endswith("/"):
            if r == p.rstrip("/") or r.startswith(p):
                return True
        elif r == p:
            return True
    return False


def _path_allowed_from_whitelist(rel_posix: str) -> bool:
    r = rel_posix.lstrip("./")
    if _is_protected(r):
        return False
    for w in SOURCE_WHITELIST:
        if r == w or r.startswith(w.rstrip("/") + "/"):
            return True
    return False


def apply_source_zip(zip_path: Path, install_dir: Path) -> list[str]:
    """Extract zipball to temp, then copy only SOURCE_WHITELIST into install_dir."""
    applied: list[str] = []
    with tempfile.TemporaryDirectory(prefix="zhange-src-") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path)
        # GitHub zipball: single top-level directory
        children = [p for p in tmp_path.iterdir() if p.name not in (".", "..")]
        src_root = children[0] if len(children) == 1 and children[0].is_dir() else tmp_path

        for rel in SOURCE_WHITELIST:
            if not _path_allowed_from_whitelist(rel):
                continue
            src = src_root / rel
            dest = install_dir / rel
            if not src.exists():
                logger.debug("whitelist miss (not in zip): %s", rel)
                continue
            if src.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dest)
                applied.append(rel.rstrip("/") + "/")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                applied.append(rel)
    return applied


def apply_static_tar(tar_path: Path, static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    # Clear existing static contents but keep directory
    for child in static_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        # Python 3.12+ filter; use data filter when available
        if hasattr(tarfile, "data_filter"):
            tf.extractall(static_dir, filter=tarfile.data_filter)
        else:
            tf.extractall(static_dir)


def pip_install_requirements(install_dir: Path) -> None:
    backend = install_dir / "backend"
    req = backend / "requirements.txt"
    if not req.is_file():
        raise RuntimeError("缺少 backend/requirements.txt")
    candidates = [
        backend / ".venv" / "bin" / "python",
        backend / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    python = next((p for p in candidates if p.is_file()), None)
    if python is None:
        raise RuntimeError("找不到 Python（请先 scripts/install.sh 创建 backend/.venv）")
    cmd = [str(python), "-m", "pip", "install", "-r", str(req)]
    logger.info("pip install: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(backend))


async def _apply_update_core(
    *,
    target: ReleaseInfo,
    proxy: str | None,
    reboot: bool,
    install_dir: Path,
) -> UpdateResult:
    """Download + apply + pip. Caller holds update lock."""
    settings = get_settings()
    tmp_root = Path(settings.DATA_DIR).expanduser()
    if not tmp_root.is_absolute():
        tmp_root = (install_dir / tmp_root).resolve()
    else:
        tmp_root = tmp_root.resolve()
    work = tmp_root / "update-tmp"

    _set_progress(
        busy=True,
        phase="download",
        message=f"下载 {target.tag_name}…",
        target_version=target.tag_name,
        error="",
    )

    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    zip_path = work / "source.zip"
    if not target.zipball_url:
        return UpdateResult(ok=False, message="该 Release 缺少 zipball_url")
    await _download(target.zipball_url, zip_path, proxy=proxy)

    static_path = work / "static.tar.gz"
    if target.static_asset_url:
        await _download(target.static_asset_url, static_path, proxy=proxy)
    else:
        repo = (settings.UPDATE_GITHUB_REPO or "739790797/zhange-stats").strip()
        asset = _static_asset_name(target.tag_name)
        tag = target.tag_name if target.tag_name.startswith("v") else f"v{target.tag_name}"
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
        try:
            await _download(url, static_path, proxy=proxy)
        except Exception as e:
            logger.warning("下载 static 资产失败: %s", e)
            static_path = Path("")

    _set_progress(busy=True, phase="apply", message="覆盖代码（白名单）…")
    applied = await asyncio.to_thread(apply_source_zip, zip_path, install_dir)
    logger.info("applied source paths: %s", applied)

    static_dir = (
        Path(settings.STATIC_DIR).expanduser()
        if settings.STATIC_DIR
        else install_dir / "static"
    )
    if not static_dir.is_absolute():
        static_dir = (install_dir / static_dir).resolve()
    if static_path and static_path.is_file():
        _set_progress(busy=True, phase="static", message="解压前端 static…")
        await asyncio.to_thread(apply_static_tar, static_path, static_dir)
    else:
        logger.warning("跳过 static 更新（无资产）")

    _set_progress(busy=True, phase="pip", message="安装 Python 依赖…")
    await asyncio.to_thread(pip_install_requirements, install_dir)

    new_ver = (install_dir / "VERSION").read_text(encoding="utf-8").strip()
    invalidate_check_cache()
    _set_progress(busy=True, phase="done", message=f"已更新到 {new_ver}", error="")

    if reboot:
        _set_progress(busy=True, phase="restart", message="即将重启…")
        trigger_restart(delay_sec=1.5)
        return UpdateResult(
            ok=True,
            message=f"更新成功（{new_ver}），即将重启以加载新代码",
            version=new_ver,
            reboot=True,
        )
    return UpdateResult(
        ok=True,
        message=f"更新成功（{new_ver}），请手动重启服务",
        version=new_ver,
        reboot=False,
    )


async def apply_update(
    *,
    version: str = "latest",
    proxy: str | None = None,
    reboot: bool = True,
) -> UpdateResult:
    """Blocking self-update（测试 / 同进程调用）。管理端请用 enqueue_update。"""
    allowed, reason = update_allowed()
    if not allowed:
        return UpdateResult(ok=False, message=reason)

    try:
        got_lock = _lock.acquire(blocking=False)
    except PermissionError as e:
        return UpdateResult(ok=False, message=str(e))
    if not got_lock:
        return UpdateResult(ok=False, message="已有更新任务进行中")

    install_dir = resolve_install_dir()
    settings = get_settings()

    try:
        _set_progress(busy=True, phase="check", message="检查版本…", error="", target_version="")
        releases = await fetch_releases(proxy=proxy)
        resolved = _resolve_target_release(releases, version, settings.APP_VERSION)
        if isinstance(resolved, UpdateResult):
            return resolved
        return await _apply_update_core(
            target=resolved,
            proxy=proxy,
            reboot=reboot,
            install_dir=install_dir,
        )
    except PermissionError as e:
        logger.exception("self-update permission denied")
        msg = str(e) if "不可写" in str(e) else _writable_hint(install_dir)
        _set_progress(phase="error", message="更新失败", error=msg)
        return UpdateResult(ok=False, message=f"更新失败: {msg}")
    except Exception as e:
        logger.exception("self-update failed")
        _set_progress(phase="error", message="更新失败", error=str(e))
        return UpdateResult(ok=False, message=f"更新失败: {e}")
    finally:
        prog = get_progress()
        if prog.get("phase") != "restart":
            _set_progress(busy=False)
        _lock.release()


async def enqueue_update(
    *,
    version: str = "latest",
    proxy: str | None = None,
    reboot: bool = True,
) -> UpdateResult:
    """管理端一键更新（AstrBot 式）：预检后立刻返回，后台落盘，成功后进程内 exec 重启。"""
    allowed, reason = update_allowed()
    if not allowed:
        return UpdateResult(ok=False, message=reason)

    try:
        got_lock = _lock.acquire(blocking=False)
    except PermissionError as e:
        return UpdateResult(ok=False, message=str(e))
    if not got_lock:
        return UpdateResult(ok=False, message="已有更新任务进行中")

    install_dir = resolve_install_dir()
    settings = get_settings()

    try:
        _set_progress(busy=True, phase="check", message="检查版本…", error="", target_version="")
        releases = await fetch_releases(proxy=proxy)
        resolved = _resolve_target_release(releases, version, settings.APP_VERSION)
        if isinstance(resolved, UpdateResult):
            _set_progress(busy=False, phase="", message="")
            _lock.release()
            return resolved
    except Exception as e:
        logger.exception("self-update preflight failed")
        _set_progress(busy=False, phase="error", message="更新失败", error=str(e))
        _lock.release()
        return UpdateResult(ok=False, message=f"更新失败: {e}")

    target = resolved
    target_ver = target.tag_name.lstrip("vV")
    _set_progress(
        busy=True,
        phase="queued",
        message=f"已开始更新到 {target.tag_name}",
        target_version=target.tag_name,
        error="",
    )

    async def _job() -> None:
        try:
            await _apply_update_core(
                target=target,
                proxy=proxy,
                reboot=reboot,
                install_dir=install_dir,
            )
        except PermissionError as e:
            logger.exception("self-update background permission denied")
            msg = str(e) if "不可写" in str(e) else _writable_hint(install_dir)
            _set_progress(phase="error", message="更新失败", error=msg, busy=False)
        except Exception as e:
            logger.exception("self-update background failed")
            _set_progress(phase="error", message="更新失败", error=str(e), busy=False)
        finally:
            prog = get_progress()
            if prog.get("phase") != "restart":
                _set_progress(busy=False)
            _lock.release()

    asyncio.create_task(_job())
    return UpdateResult(
        ok=True,
        message=f"已开始更新到 {target.tag_name}，完成后将自动重启",
        version=target_ver,
        reboot=reboot,
    )
