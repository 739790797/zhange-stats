"""TexTeller 公式识别：权重在 var/data/texteller，可定时对照 Hugging Face 更新。"""

from __future__ import annotations

import io
import logging
import os
import ssl
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.services.articles.errors import ArticleError

Image.MAX_IMAGE_PIXELS = 20_000_000

logger = logging.getLogger("zhange.articles.texteller")

TEXTTELLER_REPO = "OleehyO/TexTeller"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
REVISION_NAME = "REVISION"
MAX_RECOGNIZE_BYTES = 2 * 1024 * 1024
ALLOW_PATTERNS = (
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "merges.txt",
    "encoder_model.onnx",
    "decoder_model.onnx",
    "decoder_with_past_model.onnx",
    "decoder_model_merged.onnx",
)

_SYNC_LOCK = threading.Lock()
_RUNTIME_LOCK = threading.Lock()
_model = None
_tokenizer = None

FetchRemote = Callable[[], str]
DownloadModels = Callable[[str, Path], None]
ProgressFn = Callable[[str, dict[str, Any]], None]


def resolve_hf_endpoint(raw: str | None) -> str:
    text = (raw or "").strip().rstrip("/")
    return text or DEFAULT_HF_ENDPOINT


def hf_endpoint() -> str:
    return resolve_hf_endpoint(str(getattr(get_settings(), "HF_ENDPOINT", "") or ""))


def apply_hf_endpoint() -> str:
    endpoint = hf_endpoint()
    os.environ["HF_ENDPOINT"] = endpoint
    return endpoint


def texteller_dir() -> Path:
    path = get_settings().data_dir_path / "texteller"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_local_revision(root: Path | None = None) -> str:
    path = (root or texteller_dir()) / REVISION_NAME
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def should_refresh(local: str, remote: str) -> bool:
    return bool(remote) and remote != (local or "")


def models_ready(root: Path | None = None) -> bool:
    folder = root or texteller_dir()
    if not read_local_revision(folder):
        return False
    if not (folder / "config.json").is_file():
        return False
    return (folder / "encoder_model.onnx").is_file() or (
        folder / "model.safetensors"
    ).is_file()


def parse_texteller_latex(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("$$") and text.endswith("$$"):
        text = text[2:-2].strip()
    elif text.startswith("\\[") and text.endswith("\\]"):
        text = text[2:-2].strip()
    elif text.startswith("\\(") and text.endswith("\\)"):
        text = text[2:-2].strip()
    elif text.startswith("$") and text.endswith("$"):
        text = text[1:-1].strip()
    if "\0" in text:
        text = text.replace("\0", "")
    return text.strip()[:2000]


def texteller_available() -> bool:
    try:
        import texteller  # noqa: F401
    except ImportError:
        return False
    return True


def reset_runtime() -> None:
    global _model, _tokenizer
    with _RUNTIME_LOCK:
        _model = None
        _tokenizer = None
    from app.services.articles.texteller_onnx import reset_onnx_runtime

    reset_onnx_runtime()


def parse_tqdm_filename(desc: str) -> str:
    text = (desc or "").strip().strip("'\"")
    lowered = text.lower()
    for prefix in ("downloading ", "fetching ", "download "):
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    token = text.split()[0].rstrip(":") if text else ""
    return Path(token.replace("\\", "/")).name


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
        return "正在读取 Hugging Face 版本…"
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
        return "本地模型已是最新，无需下载"
    if phase == "done":
        return "模型已更新"
    return "正在同步模型…"


def allowed_weight_files(siblings: list[Any]) -> list[tuple[str, int]]:
    wanted = set(ALLOW_PATTERNS)
    rows: list[tuple[str, int]] = []
    for sib in siblings:
        if isinstance(sib, dict):
            name = str(sib.get("rfilename") or "")
            size = int(sib.get("size") or 0)
        else:
            name = str(getattr(sib, "rfilename", "") or "")
            try:
                size = int(getattr(sib, "size", 0) or 0)
            except (TypeError, ValueError):
                size = 0
        if name in wanted:
            rows.append((name, max(0, size)))
    rows.sort(key=lambda row: (row[1], row[0]))
    return rows


def _short_err(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    return text.replace("\n", " ")[:180]


def _hf_http(*, read_sec: float | None = 30.0) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(connect=20.0, read=read_sec, write=60.0, pool=20.0),
        follow_redirects=True,
        verify=ssl.create_default_context(),
        headers={"User-Agent": "zhange-stats-texteller"},
    )


def hf_model_api_url(endpoint: str, revision: str | None = None) -> str:
    root = f"{endpoint.rstrip('/')}/api/models/{TEXTTELLER_REPO}"
    if revision:
        return f"{root}/revision/{revision}"
    return root


def hf_file_url(endpoint: str, revision: str, name: str) -> str:
    return f"{endpoint.rstrip('/')}/{TEXTTELLER_REPO}/resolve/{revision}/{name}"


def hf_get_json(url: str) -> dict[str, Any]:
    with _hf_http() as client:
        resp = client.get(url)
    if resp.status_code >= 400:
        raise ArticleError(502, f"模型接口 HTTP {resp.status_code}")
    data = resp.json()
    if not isinstance(data, dict):
        raise ArticleError(502, "模型接口返回异常")
    return data


def fetch_remote_meta(revision: str | None = None) -> tuple[str, list[tuple[str, int]]]:
    endpoint = apply_hf_endpoint()
    try:
        data = hf_get_json(hf_model_api_url(endpoint, revision))
    except ArticleError:
        raise
    except Exception as exc:
        logger.exception("texteller revision fetch failed endpoint=%s", endpoint)
        raise ArticleError(
            502,
            f"无法读取 TexTeller 模型版本（{endpoint}）：{_short_err(exc)}",
        ) from exc
    sha = str(data.get("sha") or revision or "")
    if not sha:
        raise ArticleError(502, f"无法读取 TexTeller 模型版本（{endpoint}）")
    return sha, allowed_weight_files(data.get("siblings") or [])


def fetch_remote_revision() -> str:
    return fetch_remote_meta()[0]


def download_models(
    revision: str,
    dest: Path,
    progress: ProgressFn | None = None,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    endpoint = apply_hf_endpoint()
    try:
        _sha, files = fetch_remote_meta(revision)
        if not files:
            raise ArticleError(502, "镜像上没有可用的 TexTeller 权重")
        total_bytes = sum(size for _, size in files)
        done_bytes = 0
        with _hf_http(read_sec=None) as client:
            for index, (name, size) in enumerate(files, start=1):
                current_n = 0

                def on_bytes(n: int, *, _name=name, _index=index) -> None:
                    nonlocal current_n
                    current_n = max(0, n)
                    if not progress:
                        return
                    progress(
                        format_sync_message(
                            "download",
                            file=_name,
                            index=_index,
                            total=len(files),
                        ),
                        {
                            "phase": "download",
                            "percent": compute_download_percent(
                                done_bytes=done_bytes,
                                current_bytes=current_n,
                                total_bytes=total_bytes,
                                files_done=_index - 1,
                                files_total=len(files),
                            ),
                            "file": _name,
                            "bytes": done_bytes + current_n,
                            "total_bytes": total_bytes,
                            "files_done": _index - 1,
                            "files_total": len(files),
                        },
                    )

                on_bytes(0)
                url = hf_file_url(endpoint, revision, name)
                target = dest / name
                part = dest / f"{name}.part"
                with client.stream("GET", url) as resp:
                    if resp.status_code >= 400:
                        raise ArticleError(
                            502,
                            f"下载 {name} 失败（HTTP {resp.status_code}）",
                        )
                    with part.open("wb") as handle:
                        for chunk in resp.iter_bytes(64 * 1024):
                            handle.write(chunk)
                            on_bytes(current_n + len(chunk))
                part.replace(target)
                done_bytes += size or current_n
                on_bytes(size or current_n)
    except ArticleError:
        raise
    except Exception as exc:
        logger.exception("texteller download failed")
        raise ArticleError(502, f"下载 TexTeller 模型失败：{_short_err(exc)}") from exc


def sync_texteller_models(
    *,
    force: bool = False,
    dest: Path | None = None,
    fetch_remote: FetchRemote | None = None,
    download: DownloadModels | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, str | bool]:
    folder = dest or texteller_dir()
    folder.mkdir(parents=True, exist_ok=True)
    fetch = fetch_remote or fetch_remote_revision

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
        local = read_local_revision(folder)
        remote = fetch()
        if not force and models_ready(folder) and not should_refresh(local, remote):
            emit("skip", percent=100, updated=False, revision=local)
            return {"updated": False, "revision": local}
        if not remote:
            raise ArticleError(502, "无法读取 TexTeller 模型版本")
        if download is None:
            download_models(remote, folder, progress=progress)
        else:
            download(remote, folder)
        (folder / REVISION_NAME).write_text(remote, encoding="utf-8")
        reset_runtime()
        logger.info("texteller model ready revision=%s", remote)
        emit("done", percent=100, updated=True, revision=remote)
        return {"updated": True, "revision": remote}
    finally:
        _SYNC_LOCK.release()


def ensure_texteller_models() -> None:
    if models_ready():
        return
    sync_texteller_models(force=True)


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
        logger.exception("texteller job_run write failed")
        db.rollback()
    finally:
        db.close()


def model_sync_job() -> None:
    from app.core.database import SessionLocal
    from app.core.timeutil import now_naive
    from app.models.job_run import JobRun

    db = SessionLocal()
    run = JobRun(
        job_key="texteller_model_sync",
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
        out = sync_texteller_models(force=False, progress=progress)
        if out.get("updated"):
            _write_job_run(
                run_id,
                status="ok",
                message=format_sync_message("done"),
                stats={
                    "phase": "done",
                    "percent": 100,
                    "updated": True,
                    "revision": out.get("revision"),
                },
                finished=True,
            )
        else:
            _write_job_run(
                run_id,
                status="ok",
                message=format_sync_message("skip"),
                stats={
                    "phase": "skip",
                    "percent": 100,
                    "updated": False,
                    "revision": out.get("revision"),
                },
                finished=True,
            )
    except ArticleError as exc:
        _write_job_run(
            run_id,
            status="error",
            message=exc.message[:500],
            stats={"phase": "error", "percent": 0},
            finished=True,
        )
    except Exception as exc:
        logger.exception("texteller model sync job failed")
        _write_job_run(
            run_id,
            status="error",
            message=str(exc)[:500],
            stats={"phase": "error", "percent": 0},
            finished=True,
        )


def _open_rgb_image(raw: bytes) -> Image.Image:
    if not raw:
        raise ArticleError(400, "文件为空")
    if len(raw) > MAX_RECOGNIZE_BYTES:
        raise ArticleError(400, "识别图片不能超过 2MB")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ArticleError(400, "无法识别该图片") from exc
    return image.convert("RGB")


def recognize_image_bytes(raw: bytes) -> str:
    if not models_ready():
        raise ArticleError(
            503,
            "公式识别模型尚未就绪，请到任务配置运行「公式识别模型更新」",
        )
    image = _open_rgb_image(raw)
    try:
        from app.services.articles.texteller_onnx import recognize_pil

        latex = parse_texteller_latex(recognize_pil(image, texteller_dir()))
    except ArticleError:
        raise
    except Exception as exc:
        logger.exception("texteller recognize failed")
        raise ArticleError(500, "公式识别失败") from exc
    if not latex:
        raise ArticleError(422, "没有识别到公式")
    return latex
