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
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import get_settings
from app.core.paths import resolve_install_dir as resolve_install_dir_from_env
from app.core.paths import resolve_runtime_path
from app.core.runtime_cache import pin_library_cache_env, runtime_tmp_dir

logger = logging.getLogger(__name__)

# GitHub zipball / CDN 在国内链路偶发掐流；整文件重试 + Range 续传。
_DOWNLOAD_ATTEMPTS = 5
_DOWNLOAD_RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})

# Relative to install root — only these are overwritten from source zip.
SOURCE_WHITELIST: tuple[str, ...] = (
    "VERSION",
    "backend/app",
    "backend/alembic",
    "backend/requirements.txt",
    "backend/requirements-dev.txt",
    "backend/scripts",
    "scripts",
    "AGENTS.md",
    "README.md",
)

PROTECTED_PREFIXES: tuple[str, ...] = (
    ".env",
    "config/",
    "var/",
    "data/",
    "uploads/",
    "backend/.venv/",
    "frontend/node_modules/",
    "static/",  # replaced only via static asset, not source zip
)

# 目录同步（增删改文件，保留 node_modules / dist 等运行时）。
MERGE_TREES: tuple[str, ...] = ("frontend",)
TREE_SKIP_NAMES: frozenset[str] = frozenset(
    {"node_modules", "dist", ".git", ".venv", "__pycache__"}
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
            data = resolve_runtime_path(
                settings.DATA_DIR,
                configured_install=getattr(settings, "APP_INSTALL_DIR", "") or "",
            )
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
    skipped: bool = False


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
    return resolve_install_dir_from_env(configured=(settings.APP_INSTALL_DIR or "").strip())


def _writable_hint(path: Path) -> str:
    return (
        f"安装路径不可写：{path}。"
        "请确保安装树属主为运行服务的用户（如 zhange），"
        f"例如：chown -R zhange:zhange {path if path.is_dir() else path.parent}"
    )


def _check_install_writable(install: Path) -> tuple[bool, str]:
    """Ensure service user can overwrite whitelist paths / update lock."""
    settings = get_settings()
    data = resolve_runtime_path(
        settings.DATA_DIR,
        configured_install=getattr(settings, "APP_INSTALL_DIR", "") or "",
    )
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


def update_allowed(*, host: bool = False) -> tuple[bool, str]:
    settings = get_settings()
    if not host and not settings.allow_in_app_update:
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


class IncompleteDownload(RuntimeError):
    """Stream ended before Content-Length / Content-Range total."""


def _download_retryable(exc: BaseException) -> bool:
    if isinstance(exc, IncompleteDownload):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code if exc.response is not None else 0
        return code in _DOWNLOAD_RETRY_STATUS
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    text = str(exc).lower()
    return any(
        s in text
        for s in (
            "incomplete",
            "peer closed",
            "connection reset",
            "connection aborted",
        )
    )


def _parse_content_range(value: str) -> tuple[int, int, int] | None:
    """Parse ``bytes start-end/total``. Unknown total (``*``) returns end+1."""
    match = re.match(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", (value or "").strip(), re.I)
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    total_s = match.group(3)
    total = end + 1 if total_s == "*" else int(total_s)
    return start, end, total


def _expected_total_bytes(
    *,
    status: int,
    headers: Any,
    resume_from: int,
) -> int | None:
    cr = headers.get("content-range") if headers is not None else None
    if cr:
        parsed = _parse_content_range(str(cr))
        if parsed:
            return parsed[2]
    cl = headers.get("content-length") if headers is not None else None
    if cl is not None and str(cl).isdigit():
        size = int(cl)
        if status == 206:
            return resume_from + size
        return size
    return None


def _check_download_size(path: Path, expected: int | None) -> None:
    got = path.stat().st_size if path.exists() else 0
    if got <= 0:
        raise IncompleteDownload("下载结果为空")
    if expected is not None and got != expected:
        raise IncompleteDownload(f"下载不完整（已收 {got} 字节，应为 {expected}）")


def _format_download_error(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        code = exc.response.status_code
        if code == 403:
            return (
                "GitHub API 拒绝（403，常见于未登录限流）。"
                "可在管理端「集成密钥」填写 GitHub Token 后重试，或稍后再试。"
            )
        if code == 404:
            return "未找到 GitHub Release（404）。请确认 UPDATE_GITHUB_REPO 与目标 tag。"
        return f"GitHub 请求失败（HTTP {code}）"
    text = str(exc).strip() or exc.__class__.__name__
    if text.startswith("从 GitHub 下载被中断"):
        return text
    looks_truncated = isinstance(exc, IncompleteDownload) or any(
        s in text.lower()
        for s in ("incomplete", "peer closed", "connection reset", "connection aborted")
    )
    if not looks_truncated:
        return text
    return (
        f"从 GitHub 下载被中断（{text}）。"
        "请再点一次「一键更新」，或在主机运行 scripts/linux/update.sh / scripts/win/update.ps1。"
    )


def _github_download_headers(url: str, *, token: str, user_agent: str) -> dict[str, str]:
    """Token only on GitHub API / github.com — never on codeload CDN."""
    headers = {"User-Agent": user_agent}
    if not token:
        return headers
    host = (urlparse(url).hostname or "").lower()
    if host in {"api.github.com", "github.com", "www.github.com"}:
        headers["Authorization"] = f"Bearer {token}"
        if "/releases/download/" in url:
            headers["Accept"] = "application/octet-stream"
    return headers


def _download_send_range(url: str, have: int) -> bool:
    """Range belongs on the file CDN, not GitHub API/html 302 hops."""
    if have <= 0:
        return False
    host = (urlparse(url).hostname or "").lower()
    return host not in {"api.github.com", "github.com", "www.github.com"}


async def _download_follow(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    *,
    token: str,
    user_agent: str,
) -> None:
    """Follow redirects then stream to dest. Resume with Range if dest is partial."""
    current = url
    for _ in range(12):
        have = dest.stat().st_size if dest.exists() else 0
        headers = _github_download_headers(current, token=token, user_agent=user_agent)
        if _download_send_range(current, have):
            headers["Range"] = f"bytes={have}-"
        resp = await client.send(
            client.build_request("GET", current, headers=headers),
            stream=True,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("location") or ""
            await resp.aclose()
            if not loc:
                raise RuntimeError(f"下载重定向缺少 Location（HTTP {resp.status_code}）")
            current = urljoin(current, loc)
            continue
        if resp.status_code == 416:
            await resp.aclose()
            dest.unlink(missing_ok=True)
            raise IncompleteDownload("服务器拒绝续传（HTTP 416），将整文件重试")
        expected: int | None = None
        try:
            resp.raise_for_status()
            if resp.status_code == 206:
                mode = "ab"
                resume_from = have
            else:
                mode = "wb"
                resume_from = 0
            expected = _expected_total_bytes(
                status=resp.status_code,
                headers=resp.headers,
                resume_from=resume_from,
            )
            with dest.open(mode) as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
        finally:
            await resp.aclose()
        _check_download_size(dest, expected)
        return
    raise RuntimeError("下载重定向次数过多")


async def _download(url: str, dest: Path, proxy: str | None = None) -> None:
    """Download URL to dest.

    Do **not** forward Authorization across redirects to codeload/objects CDN —
    GitHub rejects that and zipball/asset downloads fail.
    """
    final = _proxy_url(url, proxy)
    settings = get_settings()
    user_agent = f"zhange-stats/{settings.APP_VERSION}"
    token = ""
    try:
        from app.services.integrations_config import get_github_token

        token = (get_github_token() or "").strip()
    except Exception:  # noqa: BLE001
        token = (settings.UPDATE_GITHUB_TOKEN or "").strip()

    dest.parent.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(300.0, connect=30.0)
    last_exc: BaseException | None = None
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                http2=False,
            ) as client:
                await _download_follow(
                    client,
                    final,
                    dest,
                    token=token,
                    user_agent=user_agent,
                )
            return
        except Exception as exc:
            last_exc = exc
            if not _download_retryable(exc) or attempt >= _DOWNLOAD_ATTEMPTS:
                raise RuntimeError(_format_download_error(exc)) from exc
            logger.warning(
                "download attempt %s/%s failed: %s",
                attempt,
                _DOWNLOAD_ATTEMPTS,
                exc,
            )
            _set_progress(
                busy=True,
                phase="download",
                message=f"下载中断，正在重试（{attempt}/{_DOWNLOAD_ATTEMPTS}）…",
            )
            await asyncio.sleep(min(8.0, 1.5 * attempt))
    raise RuntimeError(_format_download_error(last_exc or RuntimeError("下载失败")))


def _resolve_target_release(
    releases: list[ReleaseInfo],
    version: str,
    current_version: str,
    *,
    force: bool = False,
) -> ReleaseInfo | UpdateResult:
    """Return target ReleaseInfo, or UpdateResult on soft failure."""
    if not releases:
        return UpdateResult(ok=False, message="未获取到任何 GitHub Release")
    ver = (version or "latest").strip()
    if ver in ("", "latest"):
        target = releases[0]
        if not force and compare_version(target.tag_name, current_version) <= 0:
            return UpdateResult(
                ok=False,
                message=f"当前已经是最新版本（{current_version}）",
                version=current_version,
                skipped=True,
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


def _path_allowed_from_whitelist(
    rel_posix: str,
    whitelist: tuple[str, ...] | None = None,
) -> bool:
    r = rel_posix.lstrip("./")
    if _is_protected(r):
        return False
    allowed = whitelist if whitelist is not None else SOURCE_WHITELIST
    for w in allowed:
        if r == w or r.startswith(w.rstrip("/") + "/"):
            return True
    return False


def parse_py_string_tuple(text: str, name: str) -> tuple[str, ...] | None:
    """Read ``NAME = ("a", "b")`` from a Python source snippet."""
    match = re.search(
        rf"{re.escape(name)}\s*(?::[^=]+)?=\s*\((.*?)\)",
        text,
        re.S,
    )
    if not match:
        return None
    found = re.findall(r"\"([^\"]*)\"|'([^']*)'", match.group(1))
    items = tuple(a or b for a, b in found if (a or b))
    return items or None


def _union_rel_paths(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for group in groups:
        for raw in group:
            rel = raw.replace("\\", "/").strip().lstrip("./")
            if not rel or rel in seen or _is_protected(rel):
                continue
            seen.append(rel)
    return tuple(seen)


def _ignore_tree_runtime(_directory: str, names: list[str]) -> set[str]:
    return {n for n in names if n in TREE_SKIP_NAMES}


def _sync_merge_tree(src: Path, dest: Path) -> None:
    """Add / overwrite / delete files under dest to match src; keep TREE_SKIP_NAMES."""
    dest.mkdir(parents=True, exist_ok=True)
    src_names = {p.name for p in src.iterdir()}
    for child in list(dest.iterdir()):
        if child.name in TREE_SKIP_NAMES:
            continue
        if child.name not in src_names:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
    for child in src.iterdir():
        if child.name in TREE_SKIP_NAMES:
            continue
        target = dest / child.name
        if child.is_dir():
            _sync_merge_tree(child, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


def load_update_paths_from_extracted(
    src_root: Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Prefer whitelist from the incoming zip so new paths apply in this round."""
    path = src_root / "backend" / "app" / "services" / "app_updator.py"
    parsed_source: tuple[str, ...] | None = None
    parsed_merge: tuple[str, ...] | None = None
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        parsed_source = parse_py_string_tuple(text, "SOURCE_WHITELIST")
        parsed_merge = parse_py_string_tuple(text, "MERGE_TREES")
    merge = _union_rel_paths(parsed_merge or (), MERGE_TREES)
    merge_set = {p.rstrip("/") for p in merge}
    whitelist = tuple(
        p
        for p in _union_rel_paths(parsed_source or (), SOURCE_WHITELIST)
        if p.rstrip("/") not in merge_set
    )
    return whitelist, merge


def remove_legacy_deploy_tree(install_dir: Path) -> bool:
    """systemd 单元已迁到 scripts/linux/；旧顶层 deploy/ 删掉避免残留。"""
    unit = install_dir / "scripts" / "linux" / "zhange-stats.service"
    leftover = install_dir / "deploy"
    if not unit.is_file() or not leftover.exists():
        return False
    if leftover.is_dir():
        shutil.rmtree(leftover)
    else:
        leftover.unlink()
    return True


def apply_source_zip(zip_path: Path, install_dir: Path) -> list[str]:
    """Extract zipball, then add/replace/delete whitelist paths in install_dir."""
    applied: list[str] = []
    with tempfile.TemporaryDirectory(
        prefix="zhange-src-", dir=str(runtime_tmp_dir(install_dir))
    ) as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path)
        # GitHub zipball: single top-level directory
        children = [p for p in tmp_path.iterdir() if p.name not in (".", "..")]
        src_root = children[0] if len(children) == 1 and children[0].is_dir() else tmp_path
        whitelist, merge = load_update_paths_from_extracted(src_root)

        for rel in whitelist:
            if not _path_allowed_from_whitelist(rel, whitelist):
                continue
            src = src_root / rel
            dest = install_dir / rel
            if not src.exists():
                if dest.is_file():
                    dest.unlink()
                    applied.append(f"-{rel}")
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

        for rel in merge:
            if _is_protected(rel):
                continue
            src = src_root / rel
            dest = install_dir / rel
            if not src.is_dir():
                continue
            _sync_merge_tree(src, dest)
            applied.append(rel.rstrip("/") + "/")
        if remove_legacy_deploy_tree(install_dir):
            applied.append("-deploy/")
    return applied


def snapshot_source_paths(install_dir: Path, backup_dir: Path) -> list[str]:
    """Copy current whitelist paths aside so a failed migrate can restore disk."""
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for rel in SOURCE_WHITELIST:
        src = install_dir / rel
        if not src.exists():
            continue
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        saved.append(rel)
    for rel in MERGE_TREES:
        src = install_dir / rel
        if not src.exists():
            continue
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, ignore=_ignore_tree_runtime)
        else:
            shutil.copy2(src, dest)
        saved.append(rel)
    return saved


def restore_source_paths(install_dir: Path, backup_dir: Path) -> None:
    """Restore whitelist paths from ``snapshot_source_paths`` backup."""
    if not backup_dir.is_dir():
        raise RuntimeError(f"回滚目录不存在: {backup_dir}")
    for rel in SOURCE_WHITELIST:
        dest = install_dir / rel
        src = backup_dir / rel
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
    for rel in MERGE_TREES:
        dest = install_dir / rel
        src = backup_dir / rel
        if src.is_dir():
            _sync_merge_tree(src, dest)
            continue
        if dest.exists() and dest.is_dir():
            for child in list(dest.iterdir()):
                if child.name in TREE_SKIP_NAMES:
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
        elif dest.is_file():
            dest.unlink(missing_ok=True)


def _resolve_venv_python(install_dir: Path) -> Path:
    backend = install_dir / "backend"
    candidates = [
        backend / ".venv" / "bin" / "python",
        backend / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    python = next((p for p in candidates if p.is_file()), None)
    if python is None:
        raise RuntimeError("找不到 Python（请先 scripts/linux/install.sh 创建 backend/.venv）")
    return python


def run_install_migrations(install_dir: Path) -> None:
    """Run Alembic with *on-disk* new code before ``os.execv`` (subprocess).

    Keeps a migrate failure from taking down the still-running old process.
    """
    backend = install_dir / "backend"
    python = _resolve_venv_python(install_dir)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend.resolve())
    # Fresh settings / engine in the child (avoid stale lru_cache from parent).
    cmd = [
        str(python),
        "-c",
        "from app.core.config import get_settings; get_settings.cache_clear(); "
        "from app.core.migrate import run_migrations; run_migrations()",
    ]
    logger.info("pre-restart migrate: %s (cwd=%s)", " ".join(cmd), backend)
    proc = subprocess.run(
        cmd,
        cwd=str(backend),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        if proc.stdout.strip():
            logger.info("pre-restart migrate stdout:\n%s", proc.stdout.strip())
        return
    detail = (proc.stderr or proc.stdout or "").strip() or f"exit={proc.returncode}"
    logger.error("pre-restart migrate failed:\n%s", detail)
    raise RuntimeError(
        "数据库迁移失败，已中止重启以免服务挂死。"
        f"详情: {detail[:2000]}"
    )


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


# EasyOCR 依赖 torch。PyPI 默认 Linux 轮是 CUDA（数 GB）。生产 LXC 无 GPU，必须先装 CPU 轮再 -r。
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def cpu_torch_pip_cmd(python: Path) -> list[str]:
    return [
        str(python),
        "-m",
        "pip",
        "install",
        "torch",
        "torchvision",
        "--index-url",
        TORCH_CPU_INDEX,
    ]


def torch_constraint_lines(freeze_text: str) -> list[str]:
    return [
        line
        for line in freeze_text.splitlines()
        if line.startswith(("torch==", "torchvision=="))
    ]


def _run_pip(cmd: list[str], *, cwd: Path, progress_prefix: str) -> None:
    logger.info("pip install: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    last = ""
    for raw in proc.stdout:
        line = raw.rstrip()
        if not line:
            continue
        last = line
        logger.info("pip: %s", line)
        shown = line[-160:] if len(line) > 160 else line
        _set_progress(busy=True, phase="pip", message=f"{progress_prefix}{shown}")
    rc = proc.wait()
    if rc != 0:
        tail = last[-400:] if last else f"exit={rc}"
        raise RuntimeError(f"pip 安装失败（exit={rc}）。{tail}")


def pip_install_requirements(install_dir: Path) -> None:
    pin_library_cache_env(install=install_dir)
    backend = install_dir / "backend"
    req = backend / "requirements.txt"
    if not req.is_file():
        raise RuntimeError("缺少 backend/requirements.txt")
    python = _resolve_venv_python(install_dir)
    # 先钉 CPU torch，避免随后 easyocr 把 CUDA 轮当升级装进来。
    _set_progress(busy=True, phase="pip", message="安装 CPU 版 PyTorch（避免拉取 CUDA）…")
    _run_pip(cpu_torch_pip_cmd(python), cwd=backend, progress_prefix="torch · ")
    freeze = subprocess.run(
        [str(python), "-m", "pip", "freeze"],
        check=True,
        cwd=str(backend),
        capture_output=True,
        text=True,
    )
    pins = torch_constraint_lines(freeze.stdout)
    extra: list[str] = []
    constraint: Path | None = None
    if pins:
        fd, name = tempfile.mkstemp(
            prefix="zhange-torch-cpu-",
            suffix=".txt",
            dir=str(runtime_tmp_dir(install_dir)),
        )
        os.close(fd)
        constraint = Path(name)
        constraint.write_text("\n".join(pins) + "\n", encoding="utf-8")
        extra = ["-c", str(constraint)]
    try:
        _set_progress(busy=True, phase="pip", message="安装 Python 依赖…")
        _run_pip(
            [str(python), "-m", "pip", "install", "-r", str(req), *extra],
            cwd=backend,
            progress_prefix="pip · ",
        )
    finally:
        if constraint is not None:
            constraint.unlink(missing_ok=True)
    # RapidOCR / EasyOCR 可能拉来带 GUI 的 opencv-python；LXC 只留 headless
    subprocess.run(
        [str(python), "-m", "pip", "uninstall", "-y", "opencv-python"],
        check=False,
        cwd=str(backend),
    )
    _run_pip(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            "opencv-python-headless>=4.8.0",
        ],
        cwd=backend,
        progress_prefix="opencv · ",
    )


_HOST_REPAIR_HINT = (
    "若库结构已半更新、管理端也无法再升，请在主机执行 "
    "scripts/linux/update.sh 或 scripts/win/update.ps1"
)


async def _apply_update_core(
    *,
    target: ReleaseInfo,
    proxy: str | None,
    reboot: bool,
    install_dir: Path,
) -> UpdateResult:
    """Download + apply + pip + pre-restart migrate. Caller holds update lock.

    Migrations run *before* ``os.execv``. On migrate failure the whitelist source
    tree is restored so the still-running process keeps serving the previous
    version (avoids Alembic crash → systemd restart → 502 loops).
    """
    settings = get_settings()
    tmp_root = resolve_runtime_path(
        settings.DATA_DIR,
        configured_install=getattr(settings, "APP_INSTALL_DIR", "") or "",
    )
    work = tmp_root / "update-tmp"
    rollback_dir = work / "rollback-src"

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

    _set_progress(busy=True, phase="snapshot", message="备份当前代码（迁移失败可回滚）…")
    await asyncio.to_thread(snapshot_source_paths, install_dir, rollback_dir)

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

    _set_progress(busy=True, phase="migrate", message="应用数据库迁移…")
    try:
        await asyncio.to_thread(run_install_migrations, install_dir)
    except Exception as exc:
        logger.exception("pre-restart migrate failed; restoring previous source")
        try:
            await asyncio.to_thread(restore_source_paths, install_dir, rollback_dir)
        except Exception:
            logger.exception("source rollback failed after migrate error")
            msg = (
                f"数据库迁移失败且代码回滚也失败: {exc}。"
                f"{_HOST_REPAIR_HINT}"
            )
            _set_progress(phase="error", message="更新失败", error=msg, busy=False)
            return UpdateResult(ok=False, message=msg)
        msg = f"{exc} 已回滚代码，当前进程继续运行。{_HOST_REPAIR_HINT}"
        _set_progress(phase="error", message="更新失败（已回滚）", error=msg, busy=False)
        return UpdateResult(ok=False, message=msg)

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
    host: bool = False,
    force: bool = False,
) -> UpdateResult:
    """Blocking self-update（测试 / 同进程 / 主机脚本）。管理端请用 enqueue_update。"""
    allowed, reason = update_allowed(host=host)
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
        resolved = _resolve_target_release(
            releases, version, settings.APP_VERSION, force=force
        )
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
        msg = _format_download_error(e)
        _set_progress(phase="error", message="更新失败", error=msg)
        return UpdateResult(ok=False, message=f"更新失败: {msg}")
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
        msg = _format_download_error(e)
        _set_progress(busy=False, phase="error", message="更新失败", error=msg)
        _lock.release()
        return UpdateResult(ok=False, message=f"更新失败: {msg}")

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
            _set_progress(
                phase="error",
                message="更新失败",
                error=_format_download_error(e),
                busy=False,
            )
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


def host_update_main(argv: list[str] | None = None) -> int:
    """主机 ``update.sh`` / ``update.ps1`` 入口。不 ``os.execv``；成功后由包装脚本重启。"""
    pin_library_cache_env()
    import argparse

    global _set_progress

    parser = argparse.ArgumentParser(
        description=(
            "从 GitHub Release 更新战鸽数据："
            "白名单目录整棵替换（增删改）、frontend 同步（保留 node_modules）、"
            "static、pip、Alembic。成功后由 update.sh / update.ps1 重启。"
        )
    )
    parser.add_argument("--version", default="latest", help="目标 tag，默认 latest")
    parser.add_argument("--check", action="store_true", help="只检查是否有新版本，不落盘")
    parser.add_argument("--force", action="store_true", help="即使已是该版本也重新落盘")
    parser.add_argument("--proxy", default="", help="GitHub 下载代理前缀")
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="不重启（由 update.sh / update.ps1 处理；直接调用本入口时无效）",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="[update] %(message)s")
    orig_set = _set_progress

    def hooked(**kwargs: Any) -> None:
        orig_set(**kwargs)
        err = str(kwargs.get("error") or "")
        msg = str(kwargs.get("message") or "")
        phase = str(kwargs.get("phase") or "")
        if err:
            print(f"[update] {err}", file=sys.stderr, flush=True)
        elif msg:
            label = f"{phase}: {msg}" if phase else msg
            print(f"[update] {label}", flush=True)

    _set_progress = hooked  # type: ignore[misc]

    async def _run() -> int:
        proxy = (args.proxy or "").strip() or None
        if args.check:
            latest, _releases = await check_update(proxy=proxy, force=True)
            settings = get_settings()
            latest_ver = latest.tag_name.lstrip("vV") if latest else ""
            has_new = bool(latest) and compare_version(latest.tag_name, settings.APP_VERSION) > 0
            print(f"CURRENT={settings.APP_VERSION}")
            print(f"LATEST={latest_ver or settings.APP_VERSION}")
            print(f"HAS_NEW={'1' if has_new else '0'}")
            return 0
        result = await apply_update(
            version=args.version,
            proxy=proxy,
            reboot=False,
            host=True,
            force=args.force,
        )
        if result.skipped:
            print(result.message)
            return 2
        if not result.ok:
            print(result.message, file=sys.stderr)
            return 1
        print(result.message)
        return 0

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except httpx.HTTPStatusError as exc:
        msg = _format_download_error(exc)
        logger.warning("host update http error: %s", msg)
        print(msg, file=sys.stderr)
        return 1
    except Exception as exc:
        logger.exception("host update failed")
        print(_format_download_error(exc), file=sys.stderr)
        return 1
    finally:
        _set_progress = orig_set  # type: ignore[misc]
