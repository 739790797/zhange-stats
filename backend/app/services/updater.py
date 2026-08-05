"""Docker Compose based self-update (admin WebUI).

发版以仓库根目录 VERSION + main 推送为准（CI 打 VERSION / latest 镜像）。
检查更新优先读取 raw.githubusercontent.com 上的 VERSION，避免 GitHub API 限流。
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("zhange.update")

_VERSION_RE = re.compile(
    r"^v?(?P<ver>\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.-]+)?)$",
    re.IGNORECASE,
)
_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


@dataclass
class UpdateStatus:
    state: str = "idle"  # idle | checking | pulling | recreating | success | failed
    message: str = ""
    current_version: str = ""
    target_version: str = ""
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_lock = threading.Lock()
_status = UpdateStatus()
_worker: threading.Thread | None = None


def _normalize_version(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    match = _VERSION_RE.match(text)
    if not match:
        return text.lstrip("vV")
    return match.group("ver")


def get_current_version() -> str:
    settings = get_settings()
    return _normalize_version(settings.APP_VERSION)


def get_update_status() -> dict[str, Any]:
    with _lock:
        data = _status.to_dict()
    data["current_version"] = get_current_version()
    data["update_enabled"] = True
    return data


def _set_status(**kwargs: Any) -> None:
    with _lock:
        for key, value in kwargs.items():
            setattr(_status, key, value)


def _compare_version(a: str, b: str) -> int:
    """Return >0 if a>b, 0 if equal, <0 if a<b. Best-effort semver-ish."""

    def parts(v: str) -> list[Any]:
        core, _, pre = _normalize_version(v).partition("-")
        nums = []
        for chunk in core.split("."):
            nums.append(int(chunk) if chunk.isdigit() else chunk)
        return [nums, pre]

    pa, pb = parts(a), parts(b)
    if pa[0] > pb[0]:
        return 1
    if pa[0] < pb[0]:
        return -1
    # no prerelease > prerelease
    if not pa[1] and pb[1]:
        return 1
    if pa[1] and not pb[1]:
        return -1
    if pa[1] == pb[1]:
        return 0
    return 1 if pa[1] > pb[1] else -1


def _http_text(url: str, *, token: str = "", accept: str = "*/*", timeout: int = 20) -> str:
    headers = {
        "Accept": accept,
        "User-Agent": "zhange-stats-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _github_json(url: str, token: str = "") -> Any:
    return json.loads(
        _http_text(
            url,
            token=token,
            accept="application/vnd.github+json",
        )
    )


def _format_http_error(exc: urllib.error.HTTPError) -> str:
    if exc.code == 403:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            body = ""
        if "rate limit" in body.lower() or "rate limit" in str(exc).lower():
            return "GitHub API 限流，请稍后重试或配置 UPDATE_GITHUB_TOKEN"
        return f"GitHub API 拒绝访问 (HTTP 403)"
    if exc.code == 404:
        return "仓库或资源不存在 (HTTP 404)"
    return f"HTTP Error {exc.code}: {exc.reason}"


def _fetch_version_from_raw(repo: str) -> str | None:
    """Read VERSION on main — does not consume GitHub REST API quota."""
    url = f"https://raw.githubusercontent.com/{repo}/main/VERSION"
    text = _http_text(url, timeout=15).strip()
    return _normalize_version(text) or None


def _fetch_version_from_api(repo: str, token: str) -> str | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        data = _github_json(url, token)
        tag = str(data.get("tag_name") or "")
        ver = _normalize_version(tag)
        if ver:
            return ver
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    tags_url = f"https://api.github.com/repos/{repo}/tags?per_page=20"
    tags = _github_json(tags_url, token)
    if not isinstance(tags, list):
        return None
    for item in tags:
        name = _normalize_version(str(item.get("name") or ""))
        if name:
            return name
    return None


def fetch_latest_release_tag() -> tuple[str | None, str | None]:
    """Return (latest_version, soft_error). Soft errors do not block the check UI."""
    settings = get_settings()
    repo = settings.UPDATE_REPO.strip()
    if not repo:
        return None, "未配置 UPDATE_REPO"
    if not _REPO_RE.match(repo):
        raise RuntimeError("UPDATE_REPO 格式无效，应为 owner/name")

    token = settings.UPDATE_GITHUB_TOKEN.strip()
    errors: list[str] = []

    try:
        ver = _fetch_version_from_raw(repo)
        if ver:
            return ver, None
        errors.append("远程 VERSION 为空")
    except urllib.error.HTTPError as exc:
        msg = _format_http_error(exc)
        logger.warning("fetch VERSION via raw failed: %s", msg)
        errors.append(msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch VERSION via raw failed: %s", exc)
        errors.append(str(exc).strip() or exc.__class__.__name__)

    try:
        ver = _fetch_version_from_api(repo, token)
        if ver:
            return ver, None
        errors.append("未找到 Release / Tag")
    except urllib.error.HTTPError as exc:
        msg = _format_http_error(exc)
        logger.warning("GitHub API latest version failed: %s", msg)
        errors.append(msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub API latest version failed: %s", exc)
        errors.append(str(exc).strip() or exc.__class__.__name__)

    return None, "；".join(errors) if errors else "无法获取最新版本"


def check_for_update() -> dict[str, Any]:
    settings = get_settings()
    current = get_current_version()
    latest, check_error = fetch_latest_release_tag()
    has_update = bool(latest and current and _compare_version(latest, current) > 0)
    # 当前版本未知时，只要远端有版本就提示可更新（便于首次部署）
    if latest and not current:
        has_update = True
    return {
        "current_version": current,
        "latest_version": latest,
        "has_update": has_update,
        "update_enabled": True,
        "image": settings.UPDATE_IMAGE,
        "repo": settings.UPDATE_REPO,
        "check_error": check_error,
    }


def _ensure_update_runtime() -> str:
    """校验一键更新所需挂载，返回 compose 文件路径。"""
    settings = get_settings()
    compose_file = settings.UPDATE_COMPOSE_FILE.strip() or "/deploy/compose.yml"
    compose_path = Path(compose_file)
    if not compose_path.is_file():
        raise RuntimeError(
            f"找不到 {compose_file}。请将宿主机 compose.yml 挂载到该路径"
            "（见仓库 compose.yml 的 volumes），并在宿主机执行一次"
            " docker compose up -d 使挂载生效。"
        )
    # compose.yml 内 env_file: .env 相对 compose 文件目录解析为 /deploy/.env
    env_beside = compose_path.parent / ".env"
    if not env_beside.is_file():
        raise RuntimeError(
            f"找不到 {env_beside}。请将宿主机 .env 挂载为 /deploy/.env:ro"
            "（见仓库 compose.yml），在宿主机同步最新 compose.yml 后执行"
            " docker compose up -d，再在网页点更新。"
        )
    if not Path("/var/run/docker.sock").exists():
        raise RuntimeError(
            "找不到 /var/run/docker.sock。请在 app 服务挂载 Docker socket"
            "（见仓库 compose.yml），并重新 up -d。"
        )
    return compose_file


def _run_compose(args: list[str]) -> None:
    settings = get_settings()
    compose_file = _ensure_update_runtime()
    project_dir = str(Path(compose_file).parent)
    cmd = [
        "docker",
        "compose",
        "--project-directory",
        project_dir,
        "-f",
        compose_file,
        "-p",
        settings.UPDATE_COMPOSE_PROJECT,
        *args,
    ]
    logger.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or f"docker compose failed ({proc.returncode})")


def _update_worker(target_version: str) -> None:
    settings = get_settings()
    image = settings.UPDATE_IMAGE.strip()
    service = settings.UPDATE_COMPOSE_SERVICE.strip() or "app"
    tag = target_version if target_version else "latest"
    # compose 用 APP_TAG / APP_VERSION；pull 指定镜像 tag
    image_ref = f"{image}:{tag}" if ":" not in image.split("/")[-1] else image

    try:
        _ensure_update_runtime()
        _set_status(
            state="pulling",
            message=f"正在拉取镜像 {image_ref} …",
            target_version=tag,
            error=None,
        )
        # 生产以 Watchtower 跟踪 :latest 为主；手动更新优先 pull 版本号，再同步 latest
        pull = subprocess.run(
            ["docker", "pull", image_ref],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if pull.returncode != 0:
            logger.warning("docker pull failed, fallback to compose pull: %s", pull.stderr)
            _run_compose(["pull", service])
        else:
            if tag != "latest":
                subprocess.run(
                    ["docker", "tag", image_ref, f"{image}:latest"],
                    check=False,
                    capture_output=True,
                    text=True,
                )

        _set_status(state="recreating", message="正在重建应用容器…")
        _run_compose(["up", "-d", "--no-deps", "--force-recreate", service])
        _set_status(
            state="success",
            message="更新已触发，服务即将短暂中断后恢复。",
            finished_at=time.time(),
        )
    except Exception as exc:  # noqa: BLE001 — surface to UI
        logger.exception("Update failed")
        _set_status(
            state="failed",
            message="更新失败",
            error=str(exc),
            finished_at=time.time(),
        )


def start_update(version: str | None = None) -> dict[str, Any]:
    global _worker
    settings = get_settings()

    target = _normalize_version(version or "")
    if not target:
        latest, err = fetch_latest_release_tag()
        target = latest or "latest"
        if not latest and err:
            logger.warning("start_update fallback to latest: %s", err)
    if target != "latest" and not _VERSION_RE.match(target) and not _VERSION_RE.match(
        f"v{target}"
    ):
        raise RuntimeError("更新版本号无效")
    with _lock:
        if _worker and _worker.is_alive():
            raise RuntimeError("已有更新任务进行中")
        _status.state = "pulling"
        _status.message = "准备更新…"
        _status.current_version = get_current_version()
        _status.target_version = target
        _status.started_at = time.time()
        _status.finished_at = None
        _status.error = None
        _worker = threading.Thread(
            target=_update_worker,
            args=(target,),
            name="zhange-update",
            daemon=True,
        )
        _worker.start()

    return get_update_status()
