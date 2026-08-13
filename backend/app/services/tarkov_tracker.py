"""Tarkov Tracker.org token 绑定与进度摘要（只读拉取，不回写）。"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.timeutil import now_naive
from app.models.tarkov import TarkovTrackerBind
from app.models.user import User

TRACKER_API_BASE = "https://api.tarkovtracker.org"
USER_AGENT = "zhange-stats/1.0 (+https://github.com/739790797/zhange-stats)"
TOKEN_RE = re.compile(r"^(PVP|PVE|SZN)_([0-9a-fA-F]{18})$")
PREFIX_TO_MODE = {"PVP": "pvp", "PVE": "pve", "SZN": "seasonal"}
MODE_LABELS = {"pvp": "PVP", "pve": "PVE", "seasonal": "赛季"}
DOWNLOAD_TIMEOUT = 20


class TarkovTrackerError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_token(raw: str) -> str:
    return (raw or "").strip().replace(" ", "")


def parse_token(raw: str) -> tuple[str, str]:
    token = normalize_token(raw)
    match = TOKEN_RE.fullmatch(token)
    if not match:
        raise TarkovTrackerError(
            "Token 格式无效。请到 tarkovtracker.org 设置页创建，并用复制按钮拷贝（形如 PVP_…）"
        )
    prefix = match.group(1).upper()
    return token, PREFIX_TO_MODE[prefix]


def game_mode_label(mode: str) -> str:
    return MODE_LABELS.get((mode or "").strip().lower(), (mode or "").upper())


def _http_json(path: str, token: str) -> dict[str, Any]:
    url = f"{TRACKER_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:  # noqa: BLE001
            body = ""
        if exc.code == 401:
            raise TarkovTrackerError("Token 无效或已撤销", status_code=401) from exc
        if exc.code == 403:
            raise TarkovTrackerError(
                "Token 缺少「Get progression」权限，请在 Tarkov Tracker 重新创建",
                status_code=403,
            ) from exc
        if exc.code == 429:
            raise TarkovTrackerError(
                "Tarkov Tracker 请求过于频繁，请稍后再试",
                status_code=429,
            ) from exc
        detail = ""
        try:
            parsed = json.loads(body) if body else {}
            if isinstance(parsed, dict):
                detail = str(parsed.get("error") or parsed.get("message") or "")
        except json.JSONDecodeError:
            detail = ""
        msg = f"Tarkov Tracker 请求失败 HTTP {exc.code}"
        if detail:
            msg = f"{msg}：{detail}"
        raise TarkovTrackerError(msg, status_code=502) from exc
    except urllib.error.URLError as exc:
        raise TarkovTrackerError(f"无法连接 Tarkov Tracker: {exc}", status_code=502) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TarkovTrackerError("Tarkov Tracker 响应无法解析", status_code=502) from exc
    if not isinstance(payload, dict):
        raise TarkovTrackerError("Tarkov Tracker 响应格式无效", status_code=502)
    return payload


def inspect_token(token: str) -> dict[str, Any]:
    payload = _http_json("/token", token)
    perms = payload.get("permissions") if isinstance(payload.get("permissions"), list) else []
    perms_norm = [str(p).upper() for p in perms]
    if perms_norm and "GP" not in perms_norm:
        raise TarkovTrackerError(
            "Token 缺少「Get progression」权限，请在 Tarkov Tracker 勾选后重新创建"
        )
    mode = str(payload.get("gameMode") or "").strip().lower()
    return {"permissions": perms_norm, "game_mode": mode}


def _task_flags(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "complete": bool(row.get("complete")),
        "failed": bool(row.get("failed")),
        "invalid": bool(row.get("invalid")),
    }


def parse_progress(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        data = {}
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    tasks = data.get("tasksProgress") if isinstance(data.get("tasksProgress"), list) else []
    complete = 0
    failed = 0
    task_map: dict[str, dict[str, bool]] = {}
    for row in tasks:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("id") or "").strip()
        flags = _task_flags(row)
        if tid:
            task_map[tid] = flags
        if flags["failed"]:
            failed += 1
        elif flags["complete"]:
            complete += 1
    try:
        level = int(data.get("playerLevel") or 1)
    except (TypeError, ValueError):
        level = 1
    level = max(1, min(level, 79))
    try:
        edition = int(data.get("gameEdition") or 0)
    except (TypeError, ValueError):
        edition = 0
    mode = str(meta.get("gameMode") or "").strip().lower()
    faction = str(data.get("pmcFaction") or "").strip().upper()
    if faction not in {"USEC", "BEAR"}:
        faction = ""
    return {
        "display_name": str(data.get("displayName") or "").strip()[:64],
        "player_level": level,
        "pmc_faction": faction,
        "game_edition": max(0, edition),
        "tasks_complete": complete,
        "tasks_failed": failed,
        "game_mode": mode,
        "tasks": task_map,
    }


def fetch_progress(token: str) -> dict[str, Any]:
    return parse_progress(_http_json("/progress", token))


def get_bind(db: Session, user_id: int) -> TarkovTrackerBind | None:
    return (
        db.query(TarkovTrackerBind)
        .filter(TarkovTrackerBind.user_id == user_id)
        .one_or_none()
    )


def unbound_status() -> dict[str, Any]:
    return {
        "bound": False,
        "game_mode": "",
        "game_mode_label": "",
        "display_name": "",
        "player_level": 0,
        "pmc_faction": "",
        "tasks_complete": 0,
        "tasks_failed": 0,
        "token_suffix": "",
        "last_synced_at": None,
        "last_error": None,
    }


def bind_to_status(row: TarkovTrackerBind) -> dict[str, Any]:
    synced = row.last_synced_at.isoformat() if row.last_synced_at else None
    return {
        "bound": True,
        "game_mode": row.game_mode or "",
        "game_mode_label": game_mode_label(row.game_mode),
        "display_name": row.display_name or "",
        "player_level": int(row.player_level or 0),
        "pmc_faction": row.pmc_faction or "",
        "tasks_complete": int(row.tasks_complete or 0),
        "tasks_failed": int(row.tasks_failed or 0),
        "token_suffix": row.token_suffix or "",
        "last_synced_at": synced,
        "last_error": row.last_error,
    }


def get_status(db: Session, user: User) -> dict[str, Any]:
    row = get_bind(db, user.id)
    if row is None:
        return unbound_status()
    return bind_to_status(row)


def user_progress_snapshot(db: Session, user: User) -> tuple[bool, dict[str, Any] | None]:
    row = get_bind(db, user.id)
    if row is None:
        return False, None
    snap = load_progress_snapshot(row)
    if snap is not None:
        return True, snap
    if row.last_error:
        return True, None
    try:
        sync_progress(db, user)
    except TarkovTrackerError:
        return True, None
    row = get_bind(db, user.id)
    return True, load_progress_snapshot(row) if row else None


def dump_progress_json(progress: dict[str, Any]) -> str:
    tasks = progress.get("tasks") if isinstance(progress.get("tasks"), dict) else {}
    compact: dict[str, dict[str, bool]] = {}
    for key, value in tasks.items():
        tid = str(key or "").strip()
        if not tid:
            continue
        flags = value if isinstance(value, dict) else {}
        compact[tid] = {
            "complete": bool(flags.get("complete")),
            "failed": bool(flags.get("failed")),
            "invalid": bool(flags.get("invalid")),
        }
    return json.dumps(
        {
            "player_level": int(progress.get("player_level") or 1),
            "pmc_faction": str(progress.get("pmc_faction") or ""),
            "game_mode": str(progress.get("game_mode") or ""),
            "tasks": compact,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def load_progress_snapshot(row: TarkovTrackerBind) -> dict[str, Any] | None:
    raw = (row.progress_json or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    tasks_in = data.get("tasks") if isinstance(data.get("tasks"), dict) else {}
    tasks: dict[str, dict[str, bool]] = {}
    for key, value in tasks_in.items():
        tid = str(key or "").strip()
        if not tid:
            continue
        flags = value if isinstance(value, dict) else {}
        tasks[tid] = {
            "complete": bool(flags.get("complete")),
            "failed": bool(flags.get("failed")),
            "invalid": bool(flags.get("invalid")),
        }
    try:
        level = int(data.get("player_level") or row.player_level or 1)
    except (TypeError, ValueError):
        level = int(row.player_level or 1)
    return {
        "player_level": max(1, min(level, 79)),
        "pmc_faction": str(data.get("pmc_faction") or row.pmc_faction or "").strip().upper(),
        "game_mode": str(data.get("game_mode") or row.game_mode or ""),
        "tasks": tasks,
    }


def _apply_progress(row: TarkovTrackerBind, progress: dict[str, Any], *, game_mode: str) -> None:
    row.game_mode = progress.get("game_mode") or game_mode
    row.display_name = str(progress.get("display_name") or "")
    row.player_level = int(progress.get("player_level") or 1)
    row.pmc_faction = str(progress.get("pmc_faction") or "")
    row.game_edition = int(progress.get("game_edition") or 0)
    row.tasks_complete = int(progress.get("tasks_complete") or 0)
    row.tasks_failed = int(progress.get("tasks_failed") or 0)
    row.progress_json = dump_progress_json(progress)
    row.last_synced_at = now_naive()
    row.last_error = None


def bind_token(db: Session, user: User, raw_token: str) -> dict[str, Any]:
    token, mode_from_prefix = parse_token(raw_token)
    info = inspect_token(token)
    mode = info.get("game_mode") or mode_from_prefix
    progress = fetch_progress(token)
    now = now_naive()
    row = get_bind(db, user.id)
    if row is None:
        row = TarkovTrackerBind(user_id=user.id)
        db.add(row)
        row.bound_at = now
    row.token_enc = encrypt_secret(token)
    row.token_suffix = token[-4:]
    _apply_progress(row, progress, game_mode=mode)
    db.commit()
    db.refresh(row)
    return bind_to_status(row)


def sync_progress(db: Session, user: User) -> dict[str, Any]:
    row = get_bind(db, user.id)
    if row is None:
        raise TarkovTrackerError("尚未绑定 Tarkov Tracker token")
    token = decrypt_secret(row.token_enc)
    if not token:
        raise TarkovTrackerError("已保存的 token 无法解密，请重新绑定")
    try:
        progress = fetch_progress(token)
    except TarkovTrackerError as exc:
        row.last_error = exc.message
        db.commit()
        raise
    _apply_progress(row, progress, game_mode=row.game_mode)
    db.commit()
    db.refresh(row)
    return bind_to_status(row)


def unbind_token(db: Session, user: User) -> dict[str, Any]:
    row = get_bind(db, user.id)
    if row is not None:
        db.delete(row)
        db.commit()
    return unbound_status()
