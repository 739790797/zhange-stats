"""Docker Compose based self-update (admin WebUI)."""

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
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("zhange.update")

_VERSION_RE = re.compile(
    r"^v?(?P<ver>\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.-]+)?)$",
    re.IGNORECASE,
)


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
    data["update_enabled"] = bool(get_settings().UPDATE_ENABLED)
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


def _github_json(url: str, token: str = "") -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "zhange-stats-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_release_tag() -> str | None:
    settings = get_settings()
    repo = settings.UPDATE_REPO.strip()
    if not repo:
        return None
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        data = _github_json(url, settings.UPDATE_GITHUB_TOKEN)
        tag = str(data.get("tag_name") or "")
        return _normalize_version(tag) or None
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("GitHub latest release failed: %s", exc)
            raise
    # 无正式 Release 时回退到 tags
    tags_url = f"https://api.github.com/repos/{repo}/tags?per_page=20"
    tags = _github_json(tags_url, settings.UPDATE_GITHUB_TOKEN)
    if not isinstance(tags, list):
        return None
    for item in tags:
        name = _normalize_version(str(item.get("name") or ""))
        if name:
            return name
    return None


def check_for_update() -> dict[str, Any]:
    settings = get_settings()
    current = get_current_version()
    latest = fetch_latest_release_tag()
    has_update = bool(latest and _compare_version(latest, current) > 0)
    return {
        "current_version": current,
        "latest_version": latest,
        "has_update": has_update,
        "update_enabled": bool(settings.UPDATE_ENABLED),
        "image": settings.UPDATE_IMAGE,
        "repo": settings.UPDATE_REPO,
    }


def _run_compose(args: list[str]) -> None:
    settings = get_settings()
    cmd = [
        "docker",
        "compose",
        "-f",
        settings.UPDATE_COMPOSE_FILE,
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
        _set_status(
            state="pulling",
            message=f"正在拉取镜像 {image_ref} …",
            target_version=tag,
            error=None,
        )
        # 先 pull 具体 tag，再让 compose 用 env 重建
        pull = subprocess.run(
            ["docker", "pull", image_ref],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if pull.returncode != 0:
            # 回退：compose pull（依赖 .env 中 APP_TAG）
            logger.warning("docker pull failed, fallback to compose pull: %s", pull.stderr)
            _run_compose(["pull", service])
        else:
            # 把 latest 也指到同镜像，方便 compose 默认 APP_TAG=latest
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
    if not settings.UPDATE_ENABLED:
        raise RuntimeError("未启用在线更新（UPDATE_ENABLED=false 或未挂载 docker.sock）")

    target = _normalize_version(version or "") or fetch_latest_release_tag() or "latest"
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
