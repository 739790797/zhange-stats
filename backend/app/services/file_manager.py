"""本站磁盘占用与目录浏览：只走白名单根，不跟任意用户路径读盘。"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from app.core.config import get_settings
from app.core.paths import resolve_install_dir, resolve_runtime_path
from app.core.timeutil import BEIJING

FileKind = Literal["generated", "dependency", "cache", "download"]

KIND_LABELS: dict[FileKind, str] = {
    "generated": "产生",
    "dependency": "依赖",
    "cache": "缓存",
    "download": "下载",
}

BUSINESS_LABELS: dict[str, str] = {
    "ocr": "文字识别",
    "articles": "战鸽酒馆",
    "uploads": "头像上传",
    "logs": "应用日志",
    "update": "系统更新",
    "runtime": "运行时",
    "python": "Python 环境",
    "frontend": "前端资源",
    "backup": "站点备份",
    "external": "外部缓存",
    "leftover": "未分类",
}

SENSITIVE_NAMES = frozenset(
    {
        ".secret_key",
        ".env",
        "credentials.json",
        "id_rsa",
        "id_ecdsa",
        "id_ed25519",
    }
)
SENSITIVE_DIR_NAMES = frozenset({".git"})
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")

_SIZE_CACHE: dict[str, tuple[float, int, int]] = {}
_SIZE_CACHE_LOCK = threading.Lock()
_SIZE_CACHE_TTL_SEC = 45.0


class FileManagerError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ExtraRoot:
    id: str
    label: str
    path: Path
    business: str
    kind: FileKind
    description: str = ""
    optional: bool = True


@dataclass(frozen=True)
class FileManagerContext:
    install_dir: Path
    data_dir: Path
    upload_dir: Path
    var_dir: Path
    venv_dir: Path
    node_modules_dir: Path
    static_dir: Path | None
    backup_dir: Path | None
    extra: tuple[ExtraRoot, ...] = ()


@dataclass(frozen=True)
class FileBucket:
    id: str
    label: str
    description: str
    business: str
    kind: FileKind
    path: Path
    optional: bool = False
    exclude: tuple[Path, ...] = ()


@dataclass(frozen=True)
class MeasuredBucket:
    id: str
    label: str
    description: str
    business: str
    business_label: str
    kind: FileKind
    kind_label: str
    path: str
    exists: bool
    optional: bool
    size_bytes: int
    file_count: int
    browse_root_id: str | None
    browse_path: str


@dataclass(frozen=True)
class BrowseRoot:
    id: str
    label: str
    path: Path
    exists: bool


@dataclass(frozen=True)
class VolumeUsage:
    id: str
    label: str
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int


@dataclass(frozen=True)
class KindTotal:
    kind: FileKind
    label: str
    size_bytes: int
    file_count: int


@dataclass(frozen=True)
class BusinessTotal:
    business: str
    label: str
    size_bytes: int
    file_count: int


@dataclass
class FileSummary:
    measured_at: str
    total_bytes: int
    total_files: int
    kind_totals: list[KindTotal] = field(default_factory=list)
    business_totals: list[BusinessTotal] = field(default_factory=list)
    volumes: list[VolumeUsage] = field(default_factory=list)
    buckets: list[MeasuredBucket] = field(default_factory=list)
    roots: list[BrowseRoot] = field(default_factory=list)


@dataclass(frozen=True)
class BrowseEntry:
    name: str
    is_dir: bool
    size: int
    modified_at: str | None
    sensitive: bool
    downloadable: bool


@dataclass(frozen=True)
class BrowseListing:
    root_id: str
    root_label: str
    path: str
    abs_path: str
    entries: list[BrowseEntry]


def clear_size_cache() -> None:
    with _SIZE_CACHE_LOCK:
        _SIZE_CACHE.clear()


def is_sensitive_name(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    lower = text.lower()
    if lower in SENSITIVE_NAMES or lower in SENSITIVE_DIR_NAMES:
        return True
    if lower.startswith(".env.") and lower != ".env.example":
        return True
    return any(lower.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)


def rel_is_sensitive(rel: str) -> bool:
    try:
        posix = normalize_rel(rel)
    except FileManagerError:
        return True
    parts = [part for part in posix.split("/") if part]
    if any(is_sensitive_name(part) for part in parts):
        return True
    lower = posix.lower()
    padded = f"/{lower}/"
    if "/mariadb/data/" in padded or lower == "mariadb/data" or lower.endswith("/mariadb/data"):
        return True
    if lower == "mariadb/provision.json" or lower.endswith("/mariadb/provision.json"):
        return True
    name = parts[-1].lower() if parts else ""
    if name.endswith(".sql"):
        return True
    if name.startswith("zhange-") and name.endswith(".tar.gz"):
        return True
    return False


def normalize_rel(rel: str) -> str:
    text = (rel or "").replace("\\", "/").strip()
    while text.startswith("/"):
        text = text[1:]
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == ".." or "\x00" in part:
            raise FileManagerError("路径不合法")
        if os.path.isabs(part) or os.path.splitdrive(part)[0]:
            raise FileManagerError("路径不合法")
        if os.name == "nt" and ":" in part:
            raise FileManagerError("路径不合法")
        parts.append(part)
    return "/".join(parts)


def _normkey(path: Path) -> str:
    try:
        text = str(path.resolve())
    except OSError:
        text = str(path)
    return os.path.normcase(os.path.normpath(text))


def native_path(path: Path) -> str:
    try:
        return os.path.normpath(str(path.resolve()))
    except OSError:
        return os.path.normpath(str(path))


def same_path(left: Path, right: Path) -> bool:
    return _normkey(left) == _normkey(right)


def is_under(child: Path, parent: Path) -> bool:
    child_n = _normkey(child)
    parent_n = _normkey(parent)
    if child_n == parent_n:
        return True
    try:
        common = os.path.commonpath([child_n, parent_n])
    except ValueError:
        return False
    return os.path.normcase(os.path.normpath(common)) == parent_n


def rel_posix(child: Path, parent: Path) -> str | None:
    if not is_under(child, parent):
        return None
    try:
        rest = os.path.relpath(str(child.resolve()), str(parent.resolve()))
    except (OSError, ValueError):
        return None
    if rest in {os.curdir, ""}:
        return ""
    return rest.replace("\\", "/")


def resolve_in_root(root: Path, rel: str) -> Path:
    try:
        root_resolved = root.resolve()
    except OSError as exc:
        raise FileManagerError("路径不合法") from exc
    if not root_resolved.exists():
        raise FileManagerError("目录不存在", status_code=404)
    rel_n = normalize_rel(rel)
    parts = [p for p in rel_n.split("/") if p]
    candidate = root_resolved.joinpath(*parts) if parts else root_resolved
    try:
        target = candidate.resolve()
    except OSError as exc:
        raise FileManagerError("路径不合法") from exc
    if not is_under(target, root_resolved):
        raise FileManagerError("路径不合法")
    return target


def walk_size(path: Path, *, exclude: tuple[Path, ...] = ()) -> tuple[int, int]:
    """Return (bytes, file_count). Skip dir symlinks; do not follow file symlinks."""
    try:
        resolved = path.resolve()
    except OSError:
        return 0, 0
    if not resolved.exists():
        return 0, 0
    if resolved.is_file() and not resolved.is_symlink():
        try:
            return int(resolved.stat().st_size), 1
        except OSError:
            return 0, 0
    if not resolved.is_dir():
        return 0, 0

    excluded = tuple(p.resolve() for p in exclude if p.exists() or p.is_symlink())
    total = 0
    files = 0
    stack = [resolved]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        entry_path = Path(entry.path)
                        if excluded and any(
                            same_path(entry_path, item) or is_under(entry_path, item)
                            for item in excluded
                        ):
                            continue
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry_path)
                            continue
                        if entry.is_file(follow_symlinks=False):
                            total += int(entry.stat(follow_symlinks=False).st_size)
                            files += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return total, files


def cached_walk_size(path: Path, *, exclude: tuple[Path, ...] = ()) -> tuple[int, int]:
    key_path = _normkey(path)
    exclude_key = "|".join(sorted(_normkey(p) for p in exclude))
    cache_key = f"{key_path}::{exclude_key}"
    now = time.monotonic()
    with _SIZE_CACHE_LOCK:
        hit = _SIZE_CACHE.get(cache_key)
        if hit is not None and now - hit[0] < _SIZE_CACHE_TTL_SEC:
            return hit[1], hit[2]
    size, count = walk_size(path, exclude=exclude)
    with _SIZE_CACHE_LOCK:
        _SIZE_CACHE[cache_key] = (now, size, count)
    return size, count


def _mtime_beijing(path: Path) -> str | None:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, BEIJING).strftime("%Y-%m-%d %H:%M:%S")


def _home_cache(name: str) -> Path:
    return Path.home() / ".cache" / name


def _detect_extra_roots(*, data_dir: Path, var_dir: Path) -> tuple[ExtraRoot, ...]:
    rows: list[ExtraRoot] = []
    hf_raw = (os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE") or "").strip()
    hf = Path(hf_raw).expanduser() if hf_raw else _home_cache("huggingface")
    torch_raw = (os.environ.get("TORCH_HOME") or "").strip()
    torch = Path(torch_raw).expanduser() if torch_raw else _home_cache("torch")
    candidates = (
        ExtraRoot(
            id="hf_cache",
            label="Hugging Face 缓存",
            path=hf,
            business="external",
            kind="cache",
            description="HF_HOME / 默认 ~/.cache/huggingface，公式识别等可能写入",
        ),
        ExtraRoot(
            id="torch_cache",
            label="Torch 缓存",
            path=torch,
            business="external",
            kind="cache",
            description="TORCH_HOME / 默认 ~/.cache/torch",
        ),
        ExtraRoot(
            id="easyocr_home",
            label="EasyOCR 用户目录",
            path=Path.home() / ".EasyOCR",
            business="ocr",
            kind="cache",
            description="引擎默认家目录；本站权重应在 DATA_DIR/easyocr",
        ),
        ExtraRoot(
            id="paddleocr_home",
            label="PaddleOCR 用户目录",
            path=Path.home() / ".paddleocr",
            business="ocr",
            kind="cache",
            description="引擎默认家目录；本站权重应在 DATA_DIR/rapidocr",
        ),
    )
    for row in candidates:
        try:
            resolved = row.path.expanduser()
        except OSError:
            continue
        if is_under(resolved, data_dir) or is_under(resolved, var_dir):
            continue
        rows.append(
            ExtraRoot(
                id=row.id,
                label=row.label,
                path=resolved,
                business=row.business,
                kind=row.kind,
                description=row.description,
                optional=True,
            )
        )
    return tuple(rows)


def _backup_dir(install: Path) -> Path:
    raw = (os.environ.get("ZHANGE_BACKUP_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    local = install / "var" / "backups"
    legacy = Path("/var/backups/zhange")
    if os.name != "nt" and legacy.is_dir() and not local.is_dir():
        return legacy
    return local


def context_from_settings() -> FileManagerContext:
    settings = get_settings()
    install = resolve_install_dir(configured=settings.APP_INSTALL_DIR)
    data_dir = settings.data_dir_path
    upload_dir = settings.upload_dir_path
    var_dir = (install / "var").resolve()
    static: Path | None = None
    if (settings.STATIC_DIR or "").strip():
        static = resolve_runtime_path(
            settings.STATIC_DIR, configured_install=settings.APP_INSTALL_DIR
        )
    return FileManagerContext(
        install_dir=install,
        data_dir=data_dir,
        upload_dir=upload_dir,
        var_dir=var_dir,
        venv_dir=(install / "backend" / ".venv").resolve(),
        node_modules_dir=(install / "frontend" / "node_modules").resolve(),
        static_dir=static,
        backup_dir=_backup_dir(install),
        extra=_detect_extra_roots(data_dir=data_dir, var_dir=var_dir),
    )


def _bucket(
    *,
    id: str,
    label: str,
    description: str,
    business: str,
    kind: FileKind,
    path: Path,
    optional: bool = False,
    exclude: tuple[Path, ...] = (),
) -> FileBucket:
    return FileBucket(
        id=id,
        label=label,
        description=description,
        business=business,
        kind=kind,
        path=path,
        optional=optional,
        exclude=exclude,
    )


def catalog_buckets(ctx: FileManagerContext) -> list[FileBucket]:
    data = ctx.data_dir
    uploads = ctx.upload_dir
    var_dir = ctx.var_dir
    classified_data = (
        data / "rapidocr",
        data / "easyocr",
        data / "texteller",
        data / "logs",
        data / "update-tmp",
        data / "maa",
    )
    classified_uploads = (uploads / "avatars", uploads / "articles")
    var_children: list[Path] = [
        var_dir / "cache",
        var_dir / "dev",
        var_dir / "tmp",
        var_dir / "mariadb",
    ]
    if is_under(data, var_dir):
        var_children.append(data)
    if is_under(uploads, var_dir) and not same_path(uploads, data):
        var_children.append(uploads)

    rows: list[FileBucket] = [
        _bucket(
            id="ocr_rapidocr",
            label="熊猫 OCR 权重",
            description="RapidOCR / Paddle 模型，任务配置「文字识别模型」预拉",
            business="ocr",
            kind="download",
            path=data / "rapidocr",
        ),
        _bucket(
            id="ocr_easyocr",
            label="EasyOCR 权重",
            description="EasyOCR 模型，任务配置「文字识别模型」预拉",
            business="ocr",
            kind="download",
            path=data / "easyocr",
        ),
        _bucket(
            id="articles_texteller",
            label="公式识别权重",
            description="TexTeller ONNX，任务配置「公式识别模型」预拉",
            business="articles",
            kind="download",
            path=data / "texteller",
        ),
        _bucket(
            id="articles_uploads",
            label="酒馆配图与附件",
            description="文章配图 / 附件，挂载 /uploads/articles",
            business="articles",
            kind="generated",
            path=uploads / "articles",
        ),
        _bucket(
            id="uploads_avatars",
            label="用户头像",
            description="本地裁剪后的 JPEG 头像",
            business="uploads",
            kind="generated",
            path=uploads / "avatars",
        ),
        _bucket(
            id="app_logs",
            label="应用日志",
            description="DATA_DIR/logs 下 JSONL 滚动日志",
            business="logs",
            kind="generated",
            path=data / "logs",
        ),
        _bucket(
            id="update_tmp",
            label="系统更新临时包",
            description="管理端一键更新下载的 zip / static / 回滚快照",
            business="update",
            kind="cache",
            path=data / "update-tmp",
            optional=True,
        ),
        _bucket(
            id="legacy_maa",
            label="历史 MAA 数据",
            description="已下线能力残留目录，可核对后手工清理",
            business="leftover",
            kind="generated",
            path=data / "maa",
            optional=True,
        ),
        _bucket(
            id="runtime_cache",
            label="开发与构建缓存",
            description="var/cache：pytest / Vite / PYTHONPYCACHEPREFIX",
            business="runtime",
            kind="cache",
            path=var_dir / "cache",
            optional=True,
        ),
        _bucket(
            id="runtime_dev",
            label="本地开发进程文件",
            description="var/dev：run/restart 的 pid / 日志",
            business="runtime",
            kind="generated",
            path=var_dir / "dev",
            optional=True,
        ),
        _bucket(
            id="runtime_tmp",
            label="运行时临时目录",
            description="var/tmp",
            business="runtime",
            kind="cache",
            path=var_dir / "tmp",
            optional=True,
        ),
        _bucket(
            id="runtime_mariadb",
            label="本机 MariaDB",
            description="Windows 便携实例：var/mariadb（发行包 + 数据目录）",
            business="runtime",
            kind="dependency",
            path=var_dir / "mariadb",
            optional=True,
        ),
        _bucket(
            id="data_leftover",
            label="数据目录其余文件",
            description="DATA_DIR 中未归入业务桶的文件（含密钥戳，不可下载）",
            business="leftover",
            kind="generated",
            path=data,
            exclude=classified_data,
        ),
        _bucket(
            id="uploads_leftover",
            label="上传目录其余文件",
            description="UPLOAD_DIR 中未归入头像 / 酒馆的文件",
            business="leftover",
            kind="generated",
            path=uploads,
            exclude=classified_uploads,
        ),
        _bucket(
            id="var_leftover",
            label="var 其余文件",
            description="安装根 var/ 中未归入 data / uploads / cache / mariadb 的内容",
            business="leftover",
            kind="generated",
            path=var_dir,
            exclude=tuple(var_children),
            optional=True,
        ),
        _bucket(
            id="python_venv",
            label="Python 虚拟环境",
            description="backend/.venv（OCR / torch 等依赖主要在这里）",
            business="python",
            kind="dependency",
            path=ctx.venv_dir,
            optional=True,
        ),
        _bucket(
            id="frontend_node_modules",
            label="前端 node_modules",
            description="本地开发依赖；生产 LXC 通常不保留",
            business="frontend",
            kind="dependency",
            path=ctx.node_modules_dir,
            optional=True,
        ),
    ]
    if ctx.static_dir is not None:
        rows.append(
            _bucket(
                id="frontend_static",
                label="前端静态资源",
                description="生产 STATIC_DIR（Release 预构建 static）",
                business="frontend",
                kind="generated",
                path=ctx.static_dir,
                optional=True,
            )
        )
    if ctx.backup_dir is not None:
        rows.append(
            _bucket(
                id="site_backup",
                label="站点备份",
                description="本安装树 var/backups，或 ZHANGE_BACKUP_DIR",
                business="backup",
                kind="generated",
                path=ctx.backup_dir,
                optional=True,
            )
        )
    for extra in ctx.extra:
        rows.append(
            _bucket(
                id=extra.id,
                label=extra.label,
                description=extra.description,
                business=extra.business,
                kind=extra.kind,
                path=extra.path,
                optional=extra.optional,
            )
        )
    return rows


def browse_roots(ctx: FileManagerContext) -> list[BrowseRoot]:
    roots: list[BrowseRoot] = []
    seen: list[Path] = []

    def add(id: str, label: str, path: Path, *, require_exists: bool = True) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if require_exists and not resolved.exists():
            return
        if any(same_path(resolved, item) or is_under(resolved, item) for item in seen):
            return
        seen.append(resolved)
        roots.append(BrowseRoot(id=id, label=label, path=resolved, exists=resolved.exists()))

    add("install", "安装根", ctx.install_dir, require_exists=False)
    add("var", "运行时 var/", ctx.var_dir)
    add("data", "数据目录", ctx.data_dir, require_exists=False)
    add("uploads", "上传目录", ctx.upload_dir, require_exists=False)
    add("python_venv", "Python 虚拟环境", ctx.venv_dir)
    add("frontend_node_modules", "前端 node_modules", ctx.node_modules_dir)
    if ctx.static_dir is not None:
        add("frontend_static", "前端静态资源", ctx.static_dir)
    if ctx.backup_dir is not None:
        add("site_backup", "站点备份", ctx.backup_dir)
    for extra in ctx.extra:
        add(extra.id, extra.label, extra.path)
    return roots


def _attach_browse(
    bucket: FileBucket, roots: list[BrowseRoot]
) -> tuple[str | None, str]:
    best: tuple[int, str, str] | None = None
    try:
        target = bucket.path.resolve()
    except OSError:
        return None, ""
    for root in roots:
        rel = rel_posix(target, root.path)
        if rel is None:
            continue
        score = len(_normkey(root.path))
        if best is None or score > best[0]:
            best = (score, root.id, rel)
    if best is None:
        return None, ""
    return best[1], best[2]


def _volume_key(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if os.name == "nt":
        drive = resolved.drive or resolved.anchor
        return (drive or str(resolved)).upper()
    try:
        return f"dev:{resolved.stat().st_dev}"
    except OSError:
        return str(resolved.anchor or resolved)


def _volumes(ctx: FileManagerContext, roots: list[BrowseRoot]) -> list[VolumeUsage]:
    samples: list[tuple[str, str, Path]] = [
        ("install", "安装根", ctx.install_dir),
        ("data", "数据目录", ctx.data_dir),
        ("uploads", "上传目录", ctx.upload_dir),
    ]
    for root in roots:
        samples.append((root.id, root.label, root.path))
    used_keys: set[str] = set()
    out: list[VolumeUsage] = []
    for vid, label, path in samples:
        try:
            resolved = path.resolve()
            if not resolved.exists():
                resolved = resolved.parent if resolved.parent.exists() else ctx.install_dir
            usage = shutil.disk_usage(resolved)
        except OSError:
            continue
        key = _volume_key(resolved)
        if key in used_keys:
            continue
        used_keys.add(key)
        out.append(
            VolumeUsage(
                id=f"vol_{vid}",
                label=f"{label}所在磁盘",
                path=native_path(resolved),
                total_bytes=int(usage.total),
                used_bytes=int(usage.used),
                free_bytes=int(usage.free),
            )
        )
    return out


def measure_bucket(bucket: FileBucket) -> tuple[int, int, bool]:
    exists = bucket.path.exists()
    if not exists:
        return 0, 0, False
    size, count = cached_walk_size(bucket.path, exclude=bucket.exclude)
    return size, count, True


def build_summary(ctx: FileManagerContext | None = None) -> FileSummary:
    ctx = ctx or context_from_settings()
    roots = browse_roots(ctx)
    measured: list[MeasuredBucket] = []
    for bucket in catalog_buckets(ctx):
        size, count, exists = measure_bucket(bucket)
        if bucket.optional and not exists:
            continue
        if (
            bucket.id in {"data_leftover", "uploads_leftover", "var_leftover"}
            and size <= 0
            and not exists
        ):
            continue
        if bucket.id == "var_leftover" and size <= 0:
            continue
        if bucket.id in {"data_leftover", "uploads_leftover"} and size <= 0:
            continue
        browse_root_id, browse_path = _attach_browse(bucket, roots)
        measured.append(
            MeasuredBucket(
                id=bucket.id,
                label=bucket.label,
                description=bucket.description,
                business=bucket.business,
                business_label=BUSINESS_LABELS.get(bucket.business, bucket.business),
                kind=bucket.kind,
                kind_label=KIND_LABELS[bucket.kind],
                path=native_path(bucket.path),
                exists=exists,
                optional=bucket.optional,
                size_bytes=size,
                file_count=count,
                browse_root_id=browse_root_id,
                browse_path=browse_path,
            )
        )

    kind_map: dict[FileKind, list[int]] = {
        "generated": [0, 0],
        "dependency": [0, 0],
        "cache": [0, 0],
        "download": [0, 0],
    }
    business_map: dict[str, list[int]] = {}
    total_bytes = 0
    total_files = 0
    for row in measured:
        kind_map[row.kind][0] += row.size_bytes
        kind_map[row.kind][1] += row.file_count
        biz = business_map.setdefault(row.business, [0, 0])
        biz[0] += row.size_bytes
        biz[1] += row.file_count
        total_bytes += row.size_bytes
        total_files += row.file_count

    kind_totals = [
        KindTotal(
            kind=kind,
            label=KIND_LABELS[kind],
            size_bytes=vals[0],
            file_count=vals[1],
        )
        for kind, vals in kind_map.items()
    ]
    business_totals = [
        BusinessTotal(
            business=key,
            label=BUSINESS_LABELS.get(key, key),
            size_bytes=vals[0],
            file_count=vals[1],
        )
        for key, vals in sorted(business_map.items(), key=lambda item: -item[1][0])
    ]
    return FileSummary(
        measured_at=datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S"),
        total_bytes=total_bytes,
        total_files=total_files,
        kind_totals=kind_totals,
        business_totals=business_totals,
        volumes=_volumes(ctx, roots),
        buckets=measured,
        roots=roots,
    )


def _root_by_id(ctx: FileManagerContext, root_id: str) -> BrowseRoot:
    for root in browse_roots(ctx):
        if root.id == root_id:
            return root
    raise FileManagerError("未知目录根", status_code=404)


def list_directory(
    root_id: str,
    rel: str = "",
    *,
    ctx: FileManagerContext | None = None,
) -> BrowseListing:
    ctx = ctx or context_from_settings()
    root = _root_by_id(ctx, root_id)
    rel_n = normalize_rel(rel)
    if rel_is_sensitive(rel_n):
        raise FileManagerError("敏感路径不可浏览", status_code=403)
    target = resolve_in_root(root.path, rel_n)
    if not target.exists():
        raise FileManagerError("路径不存在", status_code=404)
    if not target.is_dir():
        raise FileManagerError("不是目录")
    entries: list[BrowseEntry] = []
    try:
        with os.scandir(target) as it:
            scanned = list(it)
    except OSError as exc:
        raise FileManagerError("无法读取目录", status_code=500) from exc
    for entry in scanned:
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
            is_file = entry.is_file(follow_symlinks=False)
            if entry.is_symlink():
                continue
            size = 0
            if is_file:
                size = int(entry.stat(follow_symlinks=False).st_size)
            child_rel = f"{rel_n}/{entry.name}" if rel_n else entry.name
            sensitive = is_sensitive_name(entry.name) or rel_is_sensitive(child_rel)
            entries.append(
                BrowseEntry(
                    name=entry.name,
                    is_dir=is_dir,
                    size=size,
                    modified_at=_mtime_beijing(Path(entry.path)),
                    sensitive=sensitive,
                    downloadable=is_file and not sensitive,
                )
            )
        except OSError:
            continue
    entries.sort(key=lambda row: (not row.is_dir, row.name.lower()))
    return BrowseListing(
        root_id=root.id,
        root_label=root.label,
        path=rel_n,
        abs_path=native_path(target),
        entries=entries,
    )


def resolve_download(
    root_id: str,
    rel: str,
    *,
    ctx: FileManagerContext | None = None,
) -> Path:
    ctx = ctx or context_from_settings()
    root = _root_by_id(ctx, root_id)
    rel_n = normalize_rel(rel)
    if not rel_n:
        raise FileManagerError("请指定文件")
    if rel_is_sensitive(rel_n):
        raise FileManagerError("敏感文件不可下载", status_code=403)
    target = resolve_in_root(root.path, rel_n)
    if is_sensitive_name(target.name):
        raise FileManagerError("敏感文件不可下载", status_code=403)
    if not target.exists() or not target.is_file() or target.is_symlink():
        raise FileManagerError("文件不存在", status_code=404)
    return target
