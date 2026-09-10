"""OCR 权重：任务配置定期/手动更新，识别路径不再现场拉大包。

Paddle 档位由系统配置「文字识别」决定；EasyOCR 权重从 GitHub Release 预拉。
交叉验证仍要不同架构族，不把 PP-OCRv5 / v6 两档都当成独立票。
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.http_client import HttpRequestError, http_stream
from app.services.ocr.paddle_profiles import (
    DEFAULT_PADDLE_PROFILE,
    normalize_paddle_profile,
    paddle_rapidocr_enums,
)
from app.services.ocr.types import OcrError

logger = logging.getLogger("zhange.ocr")

REVISION_NAME = "ocr_REVISION"
LEGACY_REVISION_NAME = "key_ocr_REVISION"
MODELS_NOT_READY_MSG = (
    "识别模型未就绪，请到任务配置运行「文字识别模型」，或在系统管理「文字识别」查看引擎状态"
)
JOB_ID = "ocr_model_sync"
_DOWNLOAD_READ_SEC = 300
_DOWNLOAD_CONNECT_SEC = 20
_UA = "zhange-stats-ocr"

_SYNC_LOCK = threading.Lock()

ProgressFn = Callable[[str, dict[str, Any]], None]
FetchRemote = Callable[[], str]


@dataclass(frozen=True)
class WeightSpec:
    name: str
    url: str
    folder: str
    sha256: str = ""
    md5: str = ""


def rapidocr_model_dir(root: Path | None = None) -> Path:
    if root is not None:
        return root / "rapidocr"
    return get_settings().models_dir_path / "rapidocr"


def easyocr_model_dir(root: Path | None = None) -> Path:
    if root is not None:
        return root / "easyocr"
    return get_settings().models_dir_path / "easyocr"


def revision_path(root: Path | None = None) -> Path:
    base = root if root is not None else get_settings().models_dir_path
    return base / REVISION_NAME


def read_local_revision(root: Path | None = None) -> str:
    path = revision_path(root)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    if root is None:
        for folder in (get_settings().data_dir_path, get_settings().models_dir_path):
            for name in (REVISION_NAME, LEGACY_REVISION_NAME):
                legacy = folder / name
                if legacy.is_file():
                    return legacy.read_text(encoding="utf-8").strip()
        return ""
    legacy = root / LEGACY_REVISION_NAME
    if legacy.is_file():
        return legacy.read_text(encoding="utf-8").strip()
    return ""


def should_refresh(local: str, remote: str) -> bool:
    return bool(remote) and remote != (local or "")


def _short_err(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text.replace("\n", " ")[:180]


def paddle_weight_specs(profile: str | None = None) -> list[WeightSpec]:
    try:
        from rapidocr.inference_engine.base import FileInfo, InferSession
        from rapidocr.utils.typings import EngineType, TaskType
    except ImportError:
        return []
    try:
        enums = paddle_rapidocr_enums(profile or DEFAULT_PADDLE_PROFILE)
    except Exception:
        return []
    out: list[WeightSpec] = []
    pairs = (
        (TaskType.DET, enums["det_lang"]),
        (TaskType.REC, enums["rec_lang"]),
    )
    for task, lang in pairs:
        info = InferSession.get_model_url(
            FileInfo(
                engine_type=EngineType.ONNXRUNTIME,
                ocr_version=enums["ocr_version"],
                task_type=task,
                lang_type=lang,
                model_type=enums["model_type"],
            )
        )
        url = str(info["model_dir"])
        name = Path(urlparse(url).path).name
        if not name:
            continue
        out.append(
            WeightSpec(
                name=name,
                url=url,
                folder="rapidocr",
                sha256=str(info.get("SHA256") or ""),
            )
        )
    return out


def easyocr_weight_specs() -> list[WeightSpec]:
    try:
        import easyocr.config as cfg
    except ImportError:
        return []
    wanted = {
        "craft": getattr(cfg, "detection_models", {}),
        "zh_sim_g2": getattr(cfg, "recognition_models", {}).get("gen2", {}),
        "english_g2": getattr(cfg, "recognition_models", {}).get("gen2", {}),
    }
    rows: list[WeightSpec] = []
    craft = wanted["craft"].get("craft") if isinstance(wanted["craft"], dict) else None
    if isinstance(craft, dict) and craft.get("filename") and craft.get("url"):
        rows.append(
            WeightSpec(
                name=str(craft["filename"]),
                url=str(craft["url"]),
                folder="easyocr",
                md5=str(craft.get("md5sum") or ""),
            )
        )
    rec = wanted["zh_sim_g2"]
    for key in ("zh_sim_g2", "english_g2"):
        item = rec.get(key) if isinstance(rec, dict) else None
        if not isinstance(item, dict):
            continue
        name = str(item.get("filename") or "")
        url = str(item.get("url") or "")
        if not name or not url:
            continue
        rows.append(
            WeightSpec(
                name=name,
                url=url,
                folder="easyocr",
                md5=str(item.get("md5sum") or ""),
            )
        )
    return rows


def all_weight_specs(profile: str | None = None) -> list[WeightSpec]:
    return [*paddle_weight_specs(profile), *easyocr_weight_specs()]


def expected_revision(specs: Sequence[WeightSpec] | None = None, profile: str | None = None) -> str:
    chosen = normalize_paddle_profile(profile)
    rows = list(specs) if specs is not None else all_weight_specs(chosen)
    if not rows:
        return ""
    parts = [chosen]
    for spec in rows:
        digest = spec.sha256 or spec.md5 or spec.name
        parts.append(f"{spec.folder}/{spec.name}:{digest[:16]}")
    return "|".join(parts)


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _file_md5(path: Path) -> str:
    hasher = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _checksum_ok(path: Path, spec: WeightSpec) -> bool:
    if not path.is_file():
        return False
    if spec.sha256:
        return _file_sha256(path).lower() == spec.sha256.lower()
    if spec.md5:
        return _file_md5(path).lower() == spec.md5.lower()
    return path.stat().st_size > 0


def _specs_ready(folder: Path, specs: Sequence[WeightSpec]) -> bool:
    if not specs:
        return False
    return all(_checksum_ok(folder / spec.name, spec) for spec in specs)


def paddle_models_ready(root: Path | None = None, profile: str | None = None) -> bool:
    return _specs_ready(rapidocr_model_dir(root), paddle_weight_specs(profile))


def easyocr_models_ready(root: Path | None = None) -> bool:
    return _specs_ready(easyocr_model_dir(root), easyocr_weight_specs())


def models_ready(root: Path | None = None, profile: str | None = None) -> bool:
    return paddle_models_ready(root, profile) or easyocr_models_ready(root)


def compute_download_percent(
    *,
    done_bytes: int,
    current_bytes: int,
    total_bytes: int,
    files_done: int,
    files_total: int,
) -> int:
    if total_bytes > 0:
        return max(0, min(99, int((done_bytes + current_bytes) * 100 / total_bytes)))
    if files_total > 0:
        return max(0, min(99, int(files_done * 100 / files_total)))
    return 0


def format_sync_message(phase: str, **kwargs: Any) -> str:
    if phase == "check":
        return "正在核对识别模型版本…"
    if phase == "wait":
        return "已有同步在进行，等待其完成…"
    if phase == "download":
        name = str(kwargs.get("file") or "模型文件")
        index = kwargs.get("index")
        total = kwargs.get("total")
        if index and total:
            return f"正在下载 {name}（{index}/{total}）"
        return f"正在下载 {name}"
    if phase == "skip":
        return "本地识别模型已是最新，无需下载"
    if phase == "done":
        return "识别模型已更新"
    return "正在同步识别模型…"


def _safe_zip_member(names: Sequence[str], filename: str) -> str:
    match = next((item for item in names if Path(item).name == filename), None)
    if match is None:
        match = next((item for item in names if item.lower().endswith(".pth")), None)
    if not match:
        raise OcrError(f"压缩包里没有 {filename}", 502)
    parts = Path(match).parts
    if Path(match).is_absolute() or ".." in parts:
        raise OcrError(f"压缩包路径不合法：{filename}", 502)
    return match


def download_weight(
    spec: WeightSpec,
    dest: Path,
    *,
    on_bytes: Callable[[int], None] | None = None,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / spec.name
    if _checksum_ok(target, spec):
        if on_bytes:
            on_bytes(target.stat().st_size)
        return
    part = dest / f"{spec.name}.part"
    url_path = urlparse(spec.url).path.lower()
    is_zip = url_path.endswith(".zip")
    try:
        with http_stream(
            "GET",
            spec.url,
            headers={"User-Agent": _UA},
            timeout=_DOWNLOAD_READ_SEC,
            connect=_DOWNLOAD_CONNECT_SEC,
        ) as resp:
            if resp.status_code >= 400:
                raise OcrError(
                    f"下载 {spec.name} 失败（HTTP {resp.status_code}）",
                    502,
                )
            written = 0
            with part.open("wb") as handle:
                for chunk in resp.iter_bytes(64 * 1024):
                    handle.write(chunk)
                    written += len(chunk)
                    if on_bytes:
                        on_bytes(written)
        if is_zip:
            with zipfile.ZipFile(part) as archive:
                member = _safe_zip_member(archive.namelist(), spec.name)
                target.write_bytes(archive.read(member))
            part.unlink(missing_ok=True)
        else:
            part.replace(target)
        if spec.sha256 or spec.md5:
            if not _checksum_ok(target, spec):
                target.unlink(missing_ok=True)
                raise OcrError(f"{spec.name} 校验失败，请重试", 502)
    except OcrError:
        part.unlink(missing_ok=True)
        raise
    except HttpRequestError as exc:
        part.unlink(missing_ok=True)
        raise OcrError(
            f"下载识别模型失败：{_short_err(exc)}",
            502,
        ) from exc
    except Exception as exc:
        part.unlink(missing_ok=True)
        logger.exception("ocr weight download failed name=%s", spec.name)
        raise OcrError(
            f"下载识别模型失败：{_short_err(exc)}",
            502,
        ) from exc


def _download_all(
    specs: Sequence[WeightSpec],
    root: Path,
    progress: ProgressFn | None,
) -> None:
    total_bytes = 0
    done_bytes = 0
    count = len(specs)

    def emit_download(name: str, index: int, current: int) -> None:
        if progress is None:
            return
        progress(
            format_sync_message("download", file=name, index=index, total=count),
            {
                "phase": "download",
                "percent": compute_download_percent(
                    done_bytes=done_bytes,
                    current_bytes=current,
                    total_bytes=total_bytes,
                    files_done=index - 1,
                    files_total=count,
                ),
                "file": name,
                "bytes": done_bytes + current,
                "total_bytes": total_bytes,
                "files_done": index - 1,
                "files_total": count,
            },
        )

    for index, spec in enumerate(specs, start=1):
        folder = root / spec.folder
        current_n = 0

        def on_bytes(n: int, *, _name=spec.name, _index=index) -> None:
            nonlocal current_n
            current_n = max(0, n)
            emit_download(_name, _index, current_n)

        emit_download(spec.name, index, 0)
        download_weight(spec, folder, on_bytes=on_bytes)
        done_bytes += current_n
        emit_download(spec.name, index, current_n)


def sync_ocr_models(
    *,
    force: bool = False,
    dest: Path | None = None,
    fetch_remote: FetchRemote | None = None,
    download: Callable[[WeightSpec, Path], None] | None = None,
    specs: Sequence[WeightSpec] | None = None,
    profile: str | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, str | bool]:
    root = dest if dest is not None else get_settings().models_dir_path
    root.mkdir(parents=True, exist_ok=True)
    chosen = normalize_paddle_profile(profile)
    rows = list(specs) if specs is not None else all_weight_specs(chosen)
    fetch = fetch_remote or (lambda: expected_revision(rows, chosen))

    def emit(phase: str, **kwargs: Any) -> None:
        if progress is None:
            return
        stats = {"phase": phase, **kwargs}
        stats.setdefault("percent", 0)
        progress(format_sync_message(phase, **kwargs), stats)

    emit("check", percent=0)
    acquired = _SYNC_LOCK.acquire(blocking=False)
    if not acquired:
        emit("wait", percent=0)
        _SYNC_LOCK.acquire()
    try:
        local = read_local_revision(root)
        remote = fetch()
        ready = bool(rows) and all(
            _checksum_ok(root / spec.folder / spec.name, spec) for spec in rows
        )
        if not force and ready and not should_refresh(local, remote):
            emit("skip", percent=100, updated=False, revision=local)
            return {"updated": False, "revision": local}
        if not remote:
            raise OcrError("无法读取识别模型版本", 502)
        if not rows:
            raise OcrError("服务器未安装识别引擎（rapidocr 或 easyocr）", 503)
        if download is None:
            groups = (
                [item for item in rows if item.folder == "rapidocr"],
                [item for item in rows if item.folder == "easyocr"],
            )
            for group in groups:
                if not group:
                    continue
                try:
                    _download_all(group, root, progress)
                except OcrError:
                    logger.exception("ocr weights failed folder=%s", group[0].folder)
            paddle_ok = _specs_ready(
                root / "rapidocr",
                [item for item in rows if item.folder == "rapidocr"],
            )
            easy_ok = _specs_ready(
                root / "easyocr",
                [item for item in rows if item.folder == "easyocr"],
            )
            if not paddle_ok and not easy_ok:
                raise OcrError("下载识别模型失败", 502)
            wanted_paddle = any(item.folder == "rapidocr" for item in rows)
            wanted_easy = any(item.folder == "easyocr" for item in rows)
            families_complete = (not wanted_paddle or paddle_ok) and (
                not wanted_easy or easy_ok
            )
        else:
            for spec in rows:
                download(spec, root / spec.folder)
            families_complete = True
        if families_complete:
            revision_path(root).write_text(remote, encoding="utf-8")
        from app.services.ocr.engines import reset_runtime

        reset_runtime()
        logger.info("ocr models ready revision=%s profile=%s", remote, chosen)
        emit("done", percent=100, updated=True, revision=remote)
        return {"updated": True, "revision": remote}
    finally:
        _SYNC_LOCK.release()


sync_key_ocr_models = sync_ocr_models


def _write_job_run(
    run_id: int,
    *,
    status: str | None = None,
    message: str | None = None,
    stats: dict[str, Any] | None = None,
    finished: bool = False,
) -> None:
    from app.core.database import SessionLocal
    from app.core.timeutil import now_naive
    from app.models.job_run import JobRun

    db = SessionLocal()
    try:
        row = db.get(JobRun, run_id)
        if row is None:
            return
        if message is not None:
            row.message = message[:500]
        if stats is not None:
            row.stats = stats
        if status is not None:
            row.status = status
        if finished:
            row.finished_at = now_naive()
        db.commit()
    except Exception:
        logger.exception("ocr job_run write failed")
        db.rollback()
    finally:
        db.close()


def model_sync_job() -> None:
    from app.core.database import SessionLocal
    from app.core.timeutil import now_naive
    from app.models.job_run import JobRun

    db = SessionLocal()
    run = JobRun(
        job_key=JOB_ID,
        status="running",
        message=format_sync_message("check"),
        started_at=now_naive(),
        stats={"phase": "check", "percent": 0},
    )
    db.add(run)
    db.commit()
    run_id = int(run.id)
    db.close()

    last_at = 0.0
    last_sig = ""

    def progress(message: str, stats: dict[str, Any]) -> None:
        nonlocal last_at, last_sig
        now = time.monotonic()
        sig = f"{stats.get('phase')}|{stats.get('file')}|{int(stats.get('percent') or 0)}"
        force = str(stats.get("phase") or "") in {"wait", "skip", "done", "check", "error"}
        if not force and now - last_at < 0.45 and sig == last_sig:
            return
        last_at = now
        last_sig = sig
        _write_job_run(run_id, message=message, stats=stats)

    try:
        from app.services.ocr.config import load_ocr_config

        cfg_db = SessionLocal()
        try:
            profile = load_ocr_config(cfg_db).get("paddle_profile")
        finally:
            cfg_db.close()
        out = sync_ocr_models(force=False, progress=progress, profile=profile)
        phase = "done" if out.get("updated") else "skip"
        _write_job_run(
            run_id,
            status="ok",
            message=format_sync_message(phase),
            stats={
                "phase": phase,
                "percent": 100,
                "updated": bool(out.get("updated")),
                "revision": out.get("revision"),
            },
            finished=True,
        )
    except OcrError as exc:
        _write_job_run(
            run_id,
            status="error",
            message=exc.message[:500],
            stats={"phase": "error", "percent": 0},
            finished=True,
        )
    except Exception as exc:
        logger.exception("ocr model sync job failed")
        _write_job_run(
            run_id,
            status="error",
            message=str(exc)[:500],
            stats={"phase": "error", "percent": 0},
            finished=True,
        )
