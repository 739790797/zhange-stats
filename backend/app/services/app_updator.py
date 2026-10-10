"""AstrBot-style self-update: GitHub Release source + static asset + pip + restart."""

from __future__ import annotations

import asyncio
import functools
import hashlib
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.core.config import get_settings
from app.core.file_config import database_is_configured
from app.core.paths import cleanup_legacy_install_tree
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
    "backend/constraints.txt",
    "backend/scripts",
    "scripts",
    "AGENTS.md",
    "README.md",
)

SHA256SUMS_NAME = "SHA256SUMS"
# 与 scripts/linux/_lib.sh、scripts/win/_lib.ps1 共用：内容为 requirements/constraints 的 sha256
PIP_STAMP_NAME = ".zhange-req.stamp"
PIP_STAMP_FILES: tuple[str, ...] = ("requirements.txt", "constraints.txt")
_GITHUB_HOSTS = frozenset({"api.github.com", "github.com", "www.github.com"})

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
# asyncio keeps only weak refs to tasks; hold the background update until it finishes.
_background_tasks: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    # GitHub 资产 ``digest``（``sha256:<hex>``）；旧 Release / 非 github.com 可能为空
    digest: str = ""


@dataclass
class ReleaseInfo:
    tag_name: str
    name: str
    body: str
    published_at: str
    zipball_url: str
    static_asset_url: str | None = None
    static_asset_name: str | None = None
    assets: dict[str, ReleaseAsset] = field(default_factory=dict)
    draft: bool = False
    prerelease: bool = False


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
        install,
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


def _github_api_base() -> str:
    settings = get_settings()
    return (settings.UPDATE_GITHUB_API or "https://api.github.com").rstrip("/")


def _releases_api_url() -> str:
    settings = get_settings()
    repo = (settings.UPDATE_GITHUB_REPO or "739790797/zhange-stats").strip()
    return f"{_github_api_base()}/repos/{repo}/releases"


def _static_asset_name(version: str) -> str:
    ver = version.lstrip("vV")
    return f"zhange-stats-{ver}-static.tar.gz"


def _source_asset_name(version: str) -> str:
    ver = version.lstrip("vV")
    return f"zhange-stats-{ver}-source.tar.gz"


def _github_token() -> str:
    try:
        from app.services.integrations_config import get_github_token

        return (get_github_token() or "").strip()
    except Exception:  # noqa: BLE001
        return (get_settings().UPDATE_GITHUB_TOKEN or "").strip()


def _token_allowed(url: str) -> bool:
    """Token goes to GitHub itself (or the operator's UPDATE_GITHUB_API), never a proxy."""
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host in _GITHUB_HOSTS:
        return True
    return host == (urlparse(_github_api_base()).hostname or "").lower()


def _proxy_fallback_ok(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code if exc.response is not None else 0
        return code in (403, 429) or code >= 500
    return isinstance(exc, (httpx.TransportError, ValueError))


async def _fetch_github_json(url: str, *, proxy: str | None = None) -> Any:
    """GET GitHub API JSON directly; the proxy is only a tokenless fallback."""
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"zhange-stats/{settings.APP_VERSION}",
    }
    token = _github_token()
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        direct_headers = dict(headers)
        if token and _token_allowed(url):
            direct_headers["Authorization"] = f"Bearer {token}"
        try:
            resp = await client.get(url, headers=direct_headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if not (proxy or "").strip() or not _proxy_fallback_ok(exc):
                raise
            logger.warning(
                "GitHub API direct request failed (%s); falling back to proxy without token — "
                "release metadata and digests then come from the proxy",
                exc,
            )
        resp = await client.get(_proxy_url(url, proxy), headers=headers)
        resp.raise_for_status()
        return resp.json()


def _parse_release(item: dict[str, Any]) -> ReleaseInfo:
    tag = str(item.get("tag_name") or "")
    assets: dict[str, ReleaseAsset] = {}
    for raw in item.get("assets") or []:
        name = str(raw.get("name") or "")
        url = str(raw.get("browser_download_url") or "")
        if name and url:
            assets[name] = ReleaseAsset(name=name, url=url, digest=str(raw.get("digest") or ""))
    static = assets.get(_static_asset_name(tag))
    return ReleaseInfo(
        tag_name=tag,
        name=str(item.get("name") or tag),
        body=str(item.get("body") or ""),
        published_at=str(item.get("published_at") or ""),
        zipball_url=str(item.get("zipball_url") or ""),
        static_asset_url=static.url if static else None,
        static_asset_name=static.name if static else None,
        assets=assets,
        draft=bool(item.get("draft")),
        prerelease=bool(item.get("prerelease")),
    )


async def fetch_releases(limit: int = 20, proxy: str | None = None) -> list[ReleaseInfo]:
    data = await _fetch_github_json(_releases_api_url(), proxy=proxy)
    if not isinstance(data, list):
        raise RuntimeError("GitHub Releases 响应格式异常")
    out = [
        rel
        for rel in (_parse_release(item) for item in data if isinstance(item, dict))
        if rel.tag_name and not rel.draft
    ]
    return out[:limit]


async def fetch_release_by_tag(version: str, proxy: str | None = None) -> ReleaseInfo:
    ver = (version or "").strip()
    tag = ver if ver.startswith("v") else f"v{ver}"
    data = await _fetch_github_json(
        f"{_releases_api_url()}/tags/{quote(tag, safe='')}", proxy=proxy
    )
    if not isinstance(data, dict) or not data.get("tag_name"):
        raise RuntimeError("GitHub Release 响应格式异常")
    rel = _parse_release(data)
    if rel.draft:
        raise RuntimeError(f"Release {tag} 仍是草稿")
    return rel


def latest_stable_release(releases: list[ReleaseInfo]) -> ReleaseInfo | None:
    """Highest semver among published, non-prerelease releases (API order is by date)."""
    stable = [r for r in releases if r.tag_name and not r.draft and not r.prerelease]
    if not stable:
        return None
    return max(
        stable,
        key=functools.cmp_to_key(lambda a, b: compare_version(a.tag_name, b.tag_name)),
    )


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
    newest = latest_stable_release(releases)
    latest = (
        newest
        if newest is not None and compare_version(newest.tag_name, settings.APP_VERSION) > 0
        else None
    )
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
    if host in _GITHUB_HOSTS:
        headers["Authorization"] = f"Bearer {token}"
        if "/releases/download/" in url:
            headers["Accept"] = "application/octet-stream"
    return headers


def _partial_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _download_send_range(url: str, have: int) -> bool:
    """Range belongs on the file CDN, not GitHub API/html 302 hops."""
    if have <= 0:
        return False
    host = (urlparse(url).hostname or "").lower()
    return host not in _GITHUB_HOSTS


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
        have = _partial_size(dest)
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
            await asyncio.to_thread(dest.unlink, missing_ok=True)
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
    token = _github_token()

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


class ChecksumMismatch(RuntimeError):
    """Downloaded bytes do not match the release sha256."""


def _normalize_sha256(digest: str) -> str:
    value = (digest or "").strip().lower()
    if value.startswith("sha256:"):
        value = value[len("sha256:") :]
    return value if re.fullmatch(r"[0-9a-f]{64}", value) else ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sha256sums(text: str) -> dict[str, str]:
    """``sha256sum`` output (``<hex>  <name>`` or ``<hex> *<name>``) → {name: hex}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(\S.*?)\s*$", line)
        if match:
            out[match.group(2).removeprefix("./")] = match.group(1).lower()
    return out


def expected_sha256(release: ReleaseInfo, name: str, sums: dict[str, str]) -> str:
    asset = release.assets.get(name)
    from_api = _normalize_sha256(asset.digest) if asset else ""
    listed = sums.get(name, "")
    if from_api and listed and from_api != listed:
        raise ChecksumMismatch(f"{name} 的 sha256 与 {SHA256SUMS_NAME} 不一致，已中止更新")
    return from_api or listed


async def _download_verified(
    url: str,
    dest: Path,
    *,
    sha256: str,
    label: str,
    proxy: str | None,
) -> None:
    want = _normalize_sha256(sha256)
    if not want:
        raise ChecksumMismatch(f"{label} 缺少 sha256 校验值，已拒绝安装")
    for attempt in (1, 2):
        await _download(url, dest, proxy=proxy)
        if await asyncio.to_thread(sha256_file, dest) == want:
            return
        await asyncio.to_thread(dest.unlink, missing_ok=True)
        logger.warning("sha256 mismatch for %s (attempt %s/2)", label, attempt)
    raise ChecksumMismatch(f"{label} 校验失败（sha256 不匹配），已中止更新")


async def download_release_files(
    target: ReleaseInfo,
    work: Path,
    *,
    proxy: str | None,
    need_source: bool = True,
) -> tuple[Path | None, Path]:
    """Download static (+ source) into ``work``; every release asset is sha256-checked."""
    await asyncio.to_thread(work.mkdir, parents=True, exist_ok=True)
    sums: dict[str, str] = {}
    sums_asset = target.assets.get(SHA256SUMS_NAME)
    if sums_asset is not None:
        sums_path = work / SHA256SUMS_NAME
        if _normalize_sha256(sums_asset.digest):
            await _download_verified(
                sums_asset.url,
                sums_path,
                sha256=sums_asset.digest,
                label=SHA256SUMS_NAME,
                proxy=proxy,
            )
        else:
            await _download(sums_asset.url, sums_path, proxy=proxy)
        sums = parse_sha256sums(
            await asyncio.to_thread(sums_path.read_text, encoding="utf-8", errors="replace")
        )

    static_name = _static_asset_name(target.tag_name)
    static_asset = target.assets.get(static_name)
    if static_asset is None:
        raise RuntimeError(f"Release {target.tag_name} 缺少前端资产 {static_name}")
    static_path = work / "static.tar.gz"
    _set_progress(busy=True, phase="download", message=f"下载 {static_name}…")
    await _download_verified(
        static_asset.url,
        static_path,
        sha256=expected_sha256(target, static_name, sums),
        label=static_name,
        proxy=proxy,
    )
    if not need_source:
        return None, static_path

    source_name = _source_asset_name(target.tag_name)
    source_asset = target.assets.get(source_name)
    if source_asset is not None:
        source_path = work / source_name
        _set_progress(busy=True, phase="download", message=f"下载 {source_name}…")
        await _download_verified(
            source_asset.url,
            source_path,
            sha256=expected_sha256(target, source_name, sums),
            label=source_name,
            proxy=proxy,
        )
        return source_path, static_path
    if not target.zipball_url:
        raise RuntimeError(f"Release {target.tag_name} 缺少源码包 {source_name} 与 zipball_url")
    logger.warning(
        "release %s has no %s asset; falling back to GitHub zipball (not checksum-verified)",
        target.tag_name,
        source_name,
    )
    _set_progress(busy=True, phase="download", message="该 Release 无源码包资产，回退 zipball（无法校验）…")
    zip_path = work / "source.zip"
    await _download(target.zipball_url, zip_path, proxy=proxy)
    return zip_path, static_path


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
        target = latest_stable_release(releases)
        if target is None:
            return UpdateResult(ok=False, message="未获取到任何正式版 GitHub Release")
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


def _extract_tar_safe(tar_path: Path, dest: Path) -> None:
    with tarfile.open(tar_path, "r:*") as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter=tarfile.data_filter)
            return
        members: list[tarfile.TarInfo] = []
        for member in tf.getmembers():
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise RuntimeError(f"归档包含不安全路径: {member.name}")
            if member.isfile() or member.isdir():
                members.append(member)
        tf.extractall(dest, members=members)


def extract_source_archive(archive: Path, dest: Path) -> Path:
    """Extract a GitHub zipball or ``git archive`` tarball; return the source root."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest)
    else:
        _extract_tar_safe(archive, dest)
    # zipball / ``git archive --prefix``: single top-level directory
    children = list(dest.iterdir())
    return children[0] if len(children) == 1 and children[0].is_dir() else dest


def apply_source_tree(
    src_root: Path,
    install_dir: Path,
    whitelist: tuple[str, ...],
    merge: tuple[str, ...],
) -> list[str]:
    """Add/replace/delete whitelist paths and sync merge trees from an extracted tree."""
    applied: list[str] = []
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
    for rel_leftover in cleanup_legacy_install_tree(install_dir):
        applied.append(f"-{rel_leftover}")
    return applied


def apply_source_zip(zip_path: Path, install_dir: Path) -> list[str]:
    """Extract a source archive, then add/replace/delete whitelist paths in install_dir."""
    with tempfile.TemporaryDirectory(
        prefix="zhange-src-", dir=str(runtime_tmp_dir(install_dir))
    ) as tmp:
        src_root = extract_source_archive(zip_path, Path(tmp) / "src")
        whitelist, merge = load_update_paths_from_extracted(src_root)
        return apply_source_tree(src_root, install_dir, whitelist, merge)


def snapshot_source_paths(
    install_dir: Path,
    backup_dir: Path,
    whitelist: tuple[str, ...] = SOURCE_WHITELIST,
    merge: tuple[str, ...] = MERGE_TREES,
) -> list[str]:
    """Copy the paths an update will touch aside so any later failure can restore disk.

    Pass the same ``whitelist`` / ``merge`` to ``restore_source_paths`` — paths
    absent at snapshot time are then deleted on restore.
    """
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for rel in whitelist:
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
    for rel in merge:
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


def restore_source_paths(
    install_dir: Path,
    backup_dir: Path,
    whitelist: tuple[str, ...] = SOURCE_WHITELIST,
    merge: tuple[str, ...] = MERGE_TREES,
) -> None:
    """Restore paths from a ``snapshot_source_paths`` backup taken with the same lists."""
    if not backup_dir.is_dir():
        raise RuntimeError(f"回滚目录不存在: {backup_dir}")
    for rel in whitelist:
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
    for rel in merge:
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
    No-op before the setup wizard has chosen a database (fresh install).
    """
    if not database_is_configured():
        logger.info("pre-restart migrate skipped: database not configured yet")
        return
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


def resolve_static_dir(install_dir: Path) -> Path:
    raw = (getattr(get_settings(), "STATIC_DIR", "") or "").strip()
    static_dir = Path(raw).expanduser() if raw else install_dir / "static"
    if not static_dir.is_absolute():
        static_dir = (install_dir / static_dir).resolve()
    return static_dir


def _sibling(path: Path, suffix: str) -> Path:
    return path.with_name(path.name + suffix)


def stage_static_tar(tar_path: Path, staged_dir: Path) -> None:
    """Extract the static asset next to the live dir (same filesystem → rename swap)."""
    if staged_dir.exists():
        shutil.rmtree(staged_dir)
    staged_dir.mkdir(parents=True)
    _extract_tar_safe(tar_path, staged_dir)
    if not (staged_dir / "index.html").is_file():
        shutil.rmtree(staged_dir, ignore_errors=True)
        raise RuntimeError("前端资产缺少 index.html，已中止")


def swap_static_dir(staged_dir: Path, static_dir: Path) -> None:
    """Put ``staged_dir`` in place of ``static_dir``; the old tree stays at ``<name>.prev``."""
    prev = _sibling(static_dir, ".prev")
    if prev.exists():
        shutil.rmtree(prev)
    if static_dir.exists():
        try:
            os.replace(static_dir, prev)
        except OSError:
            # Mount point, or (Windows) a file inside is open: copy in place instead.
            logger.warning("static dir rename failed; replacing contents in place", exc_info=True)
            shutil.copytree(static_dir, prev)
            for child in list(static_dir.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            shutil.copytree(staged_dir, static_dir, dirs_exist_ok=True)
            shutil.rmtree(staged_dir, ignore_errors=True)
            return
    try:
        os.replace(staged_dir, static_dir)
    except OSError:
        if prev.exists() and not static_dir.exists():
            os.replace(prev, static_dir)
        raise


def apply_static_tar(tar_path: Path, static_dir: Path) -> None:
    staged = _sibling(static_dir, ".new")
    stage_static_tar(tar_path, staged)
    swap_static_dir(staged, static_dir)


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


def requirements_stamp(backend_dir: Path) -> str:
    """``sha256sum``-format lines for requirements + constraints (host scripts write the same)."""
    lines = [
        f"{sha256_file(backend_dir / name)}  {name}"
        for name in PIP_STAMP_FILES
        if (backend_dir / name).is_file()
    ]
    return "".join(f"{line}\n" for line in lines)


def _pip_stamp_path(install_dir: Path) -> Path:
    return install_dir / "backend" / ".venv" / PIP_STAMP_NAME


def pip_stamp_matches(install_dir: Path, backend_dir: Path) -> bool:
    want = requirements_stamp(backend_dir)
    try:
        have = _pip_stamp_path(install_dir).read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(want) and have.split() == want.split()


def write_pip_stamp(install_dir: Path) -> None:
    path = _pip_stamp_path(install_dir)
    try:
        path.write_text(requirements_stamp(install_dir / "backend"), encoding="utf-8")
    except OSError as exc:
        logger.warning("could not write pip stamp %s: %s", path, exc)


def pip_install_requirements(install_dir: Path, source_backend: Path | None = None) -> None:
    """Install ``source_backend`` (default: the installed backend) requirements into the venv."""
    pin_library_cache_env(install=install_dir)
    backend = install_dir / "backend"
    src_backend = source_backend or backend
    req = src_backend / "requirements.txt"
    if not req.is_file():
        raise RuntimeError("缺少 backend/requirements.txt")
    lock = src_backend / "constraints.txt"
    pinned = ["-c", str(lock)] if lock.is_file() else []
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
            [str(python), "-m", "pip", "install", "-r", str(req), *extra, *pinned],
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
            *pinned,
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
    """Verify → stage → pip → apply → migrate → swap static. Caller holds update lock.

    The install tree is untouched until the release is checksum-verified, staged
    and its requirements installed. Any failure after the source apply restores
    the snapshot, so the still-running process keeps serving the previous
    version. Migrations run *before* ``os.execv`` (avoids Alembic crash →
    systemd restart → 502 loops); after they succeed there is no way back, so
    the static swap comes last and only warns on failure.
    """
    settings = get_settings()
    tmp_root = resolve_runtime_path(
        settings.DATA_DIR,
        configured_install=getattr(settings, "APP_INSTALL_DIR", "") or "",
    )
    work = tmp_root / "update-tmp"
    rollback_dir = work / "rollback-src"
    static_dir = resolve_static_dir(install_dir)
    staged_static = _sibling(static_dir, ".new")

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

    static_note = ""
    try:
        source_path, static_path = await download_release_files(target, work, proxy=proxy)
        if source_path is None:
            raise RuntimeError("未下载到源码包")

        _set_progress(busy=True, phase="stage", message="解压新版本…")
        src_root = await asyncio.to_thread(extract_source_archive, source_path, work / "src")
        if not (src_root / "VERSION").is_file() or not (src_root / "backend" / "app").is_dir():
            raise RuntimeError("源码包结构异常（缺少 VERSION 或 backend/app），已中止")
        await asyncio.to_thread(stage_static_tar, static_path, staged_static)

        src_backend = src_root / "backend"
        if await asyncio.to_thread(pip_stamp_matches, install_dir, src_backend):
            logger.info("requirements unchanged since last install; skipping pip")
        else:
            _set_progress(busy=True, phase="pip", message="安装 Python 依赖…")
            try:
                await asyncio.to_thread(pip_install_requirements, install_dir, src_backend)
            except Exception as exc:
                raise RuntimeError(f"{exc} 代码未改动，当前版本继续运行。") from exc

        whitelist, merge = load_update_paths_from_extracted(src_root)
        _set_progress(busy=True, phase="snapshot", message="备份当前代码（失败可回滚）…")
        await asyncio.to_thread(
            snapshot_source_paths, install_dir, rollback_dir, whitelist, merge
        )
        try:
            _set_progress(busy=True, phase="apply", message="覆盖代码（白名单）…")
            applied = await asyncio.to_thread(
                apply_source_tree, src_root, install_dir, whitelist, merge
            )
            logger.info("applied source paths: %s", applied)
            _set_progress(busy=True, phase="migrate", message="应用数据库迁移…")
            await asyncio.to_thread(run_install_migrations, install_dir)
        except Exception as exc:
            logger.exception("update apply/migrate failed; restoring previous source")
            try:
                await asyncio.to_thread(
                    restore_source_paths, install_dir, rollback_dir, whitelist, merge
                )
            except Exception:
                logger.exception("source rollback failed after update error")
                msg = f"更新失败且代码回滚也失败: {exc}。{_HOST_REPAIR_HINT}"
                _set_progress(phase="error", message="更新失败", error=msg, busy=False)
                return UpdateResult(ok=False, message=msg)
            msg = f"{exc} 已回滚代码，当前进程继续运行。{_HOST_REPAIR_HINT}"
            _set_progress(phase="error", message="更新失败（已回滚）", error=msg, busy=False)
            return UpdateResult(ok=False, message=msg)

        _set_progress(busy=True, phase="static", message="切换前端 static…")
        try:
            await asyncio.to_thread(swap_static_dir, staged_static, static_dir)
        except Exception as exc:
            logger.exception("static swap failed after migrate")
            static_note = f"；但前端 static 切换失败（{exc}），请在主机执行更新脚本加 --force"
        await asyncio.to_thread(write_pip_stamp, install_dir)
    finally:
        if staged_static.exists():
            shutil.rmtree(staged_static, ignore_errors=True)

    new_ver = (install_dir / "VERSION").read_text(encoding="utf-8").strip()
    invalidate_check_cache()
    _set_progress(busy=True, phase="done", message=f"已更新到 {new_ver}", error="")

    if reboot:
        _set_progress(busy=True, phase="restart", message="即将重启…")
        trigger_restart(delay_sec=1.5)
        return UpdateResult(
            ok=True,
            message=f"更新成功（{new_ver}），即将重启以加载新代码{static_note}",
            version=new_ver,
            reboot=True,
        )
    return UpdateResult(
        ok=True,
        message=f"更新成功（{new_ver}），请手动重启服务{static_note}",
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

    task = asyncio.create_task(_job())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return UpdateResult(
        ok=True,
        message=f"已开始更新到 {target.tag_name}，完成后将自动重启",
        version=target_ver,
        reboot=reboot,
    )


_STATIC_ONLY_HINT = (
    "可选做法：\n"
    "  1. 稍后重试，或经 GitHub 代理：update 脚本加 --static-only --proxy <代理前缀>"
    "（Windows：update.ps1 -StaticOnly -Proxy <代理前缀>）\n"
    "  2. 当前 VERSION 可能尚未发版：git fetch --tags 后检出已发布的 tag，再重跑 install\n"
    "  3. 本机构建：cd frontend && npm ci && npm run build，"
    "再把 frontend/dist/ 里的文件复制到安装根 static/"
)


async def install_static_only(*, proxy: str | None = None) -> UpdateResult:
    """Fresh install: put the checksum-verified static asset of local VERSION in place.

    Touches neither source nor database, so it works before the setup wizard.
    """
    install_dir = resolve_install_dir()
    version_file = install_dir / "VERSION"
    if not version_file.is_file():
        return UpdateResult(ok=False, message=f"安装根无效：未找到 VERSION（{install_dir}）")
    version = version_file.read_text(encoding="utf-8").strip()
    try:
        got_lock = _lock.acquire(blocking=False)
    except PermissionError as e:
        return UpdateResult(ok=False, message=str(e))
    if not got_lock:
        return UpdateResult(ok=False, message="已有更新任务进行中")
    try:
        release = await fetch_release_by_tag(version, proxy=proxy)
        static_dir = resolve_static_dir(install_dir)
        with tempfile.TemporaryDirectory(
            prefix="zhange-static-", dir=str(runtime_tmp_dir(install_dir))
        ) as tmp:
            _, static_path = await download_release_files(
                release, Path(tmp), proxy=proxy, need_source=False
            )
            await asyncio.to_thread(apply_static_tar, static_path, static_dir)
        return UpdateResult(
            ok=True,
            message=f"已安装前端 static（{release.tag_name}，sha256 已校验）：{static_dir}",
            version=version,
        )
    except Exception as exc:
        logger.warning("static-only install failed: %s", exc)
        return UpdateResult(
            ok=False,
            message=f"无法获取 v{version} 的前端资产：{_format_download_error(exc)}\n{_STATIC_ONLY_HINT}",
        )
    finally:
        _lock.release()


def host_update_main(argv: list[str] | None = None) -> int:
    """主机 ``update.sh`` / ``update.ps1`` 入口。不 ``os.execv``；成功后由包装脚本重启。"""
    pin_library_cache_env()
    import argparse

    global _set_progress

    parser = argparse.ArgumentParser(
        description=(
            "从 GitHub Release 更新战鸽数据：校验 sha256 → 暂存 → pip → "
            "白名单目录整棵替换（增删改）、frontend 同步（保留 node_modules）→ "
            "Alembic → 切换 static。成功后由 update.sh / update.ps1 重启。"
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
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="只下载并校验当前 VERSION 的前端 static（全新安装用；不改代码、不需要数据库、不重启）",
    )
    args = parser.parse_args(argv)
    if args.static_only and (args.version or "latest") != "latest":
        print("--static-only 只安装当前 VERSION 的前端，不能指定 --version", file=sys.stderr)
        return 1

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
        if args.static_only:
            static_result = await install_static_only(proxy=proxy)
            print(static_result.message, file=sys.stdout if static_result.ok else sys.stderr)
            return 0 if static_result.ok else 1
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
