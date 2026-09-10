"""本站磁盘占用与目录浏览：只扫安装根，不跟任意用户路径读盘。"""

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

MAX_EDIT_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_ENTRY_NAME = 255
MAX_DELETE_NAMES = 200

TEXT_SUFFIXES = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".json",
        ".jsonl",
        ".json5",
        ".yml",
        ".yaml",
        ".toml",
        ".xml",
        ".csv",
        ".log",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
        ".py",
        ".pyi",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".css",
        ".scss",
        ".less",
        ".html",
        ".htm",
        ".sh",
        ".bash",
        ".ps1",
        ".bat",
        ".cmd",
        ".service",
        ".lock",
        ".example",
        ".gitignore",
        ".dockerignore",
        ".editorconfig",
        ".mdc",
        ".svg",
    }
)
TEXT_BASENAMES = frozenset(
    {
        "version",
        "license",
        "makefile",
        "dockerfile",
        "procfile",
        "gemfile",
        "jenkinsfile",
        "agents.md",
        "readme",
        "readme.md",
        ".gitignore",
        ".dockerignore",
        ".editorconfig",
        ".nvmrc",
        ".python-version",
    }
)
_WIN_RESERVED = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
)

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
SENSITIVE_DIR_NAMES = frozenset({".git", "config"})
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
class FileManagerContext:
    install_dir: Path
    data_dir: Path
    upload_dir: Path
    data_root: Path
    models_dir: Path
    venv_dir: Path
    node_modules_dir: Path
    static_dir: Path | None
    backup_dir: Path | None


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
    editable: bool = False


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


def _backup_dir(install: Path) -> Path:
    raw = (os.environ.get("ZHANGE_BACKUP_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    local = install / "data" / "backups"
    legacy = Path("/var/backups/zhange")
    if os.name != "nt" and legacy.is_dir() and not local.is_dir():
        return legacy
    return local


def context_from_settings() -> FileManagerContext:
    settings = get_settings()
    install = resolve_install_dir(configured=settings.APP_INSTALL_DIR)
    data_dir = settings.data_dir_path
    upload_dir = settings.upload_dir_path
    data_root = (install / "data").resolve()
    models_dir = settings.models_dir_path
    static: Path | None = None
    if (settings.STATIC_DIR or "").strip():
        static = resolve_runtime_path(
            settings.STATIC_DIR, configured_install=settings.APP_INSTALL_DIR
        )
    return FileManagerContext(
        install_dir=install,
        data_dir=data_dir,
        upload_dir=upload_dir,
        data_root=data_root,
        models_dir=models_dir,
        venv_dir=(install / "backend" / ".venv").resolve(),
        node_modules_dir=(install / "frontend" / "node_modules").resolve(),
        static_dir=static,
        backup_dir=_backup_dir(install),
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
    data_root = ctx.data_root
    models = ctx.models_dir
    classified_data = (
        data / "logs",
        data / "update-tmp",
        data / "maa",
    )
    classified_uploads = (uploads / "avatars", uploads / "articles")
    data_children: list[Path] = [
        data_root / "cache",
        data_root / "run",
        data_root / "tmp",
        data_root / "mariadb",
        data_root / "models",
        data_root / "backups",
    ]
    if is_under(data, data_root):
        data_children.append(data)
    if is_under(uploads, data_root) and not same_path(uploads, data):
        data_children.append(uploads)

    rows: list[FileBucket] = [
        _bucket(
            id="ocr_rapidocr",
            label="熊猫 OCR 权重",
            description="RapidOCR / Paddle 模型，任务配置「文字识别模型」预拉",
            business="ocr",
            kind="download",
            path=models / "rapidocr",
        ),
        _bucket(
            id="ocr_easyocr",
            label="EasyOCR 权重",
            description="EasyOCR 模型，任务配置「文字识别模型」预拉",
            business="ocr",
            kind="download",
            path=models / "easyocr",
        ),
        _bucket(
            id="articles_texteller",
            label="公式识别权重",
            description="TexTeller ONNX，任务配置「公式识别模型」预拉",
            business="articles",
            kind="download",
            path=models / "texteller",
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
            description="data/cache：pytest / Vite / pip / HF / Torch / PYTHONPYCACHEPREFIX",
            business="runtime",
            kind="cache",
            path=data_root / "cache",
            optional=True,
        ),
        _bucket(
            id="runtime_dev",
            label="本地开发进程文件",
            description="data/run：run/restart 的 pid / 日志",
            business="runtime",
            kind="generated",
            path=data_root / "run",
            optional=True,
        ),
        _bucket(
            id="runtime_tmp",
            label="运行时临时目录",
            description="data/tmp",
            business="runtime",
            kind="cache",
            path=data_root / "tmp",
            optional=True,
        ),
        _bucket(
            id="runtime_mariadb",
            label="本机 MariaDB",
            description="Windows 便携实例：data/mariadb（发行包 + 数据目录）",
            business="runtime",
            kind="dependency",
            path=data_root / "mariadb",
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
            id="data_root_leftover",
            label="data 其余文件",
            description="安装根 data/ 中未归入 runtime / uploads / models / cache / mariadb 的内容",
            business="leftover",
            kind="generated",
            path=data_root,
            exclude=tuple(data_children),
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
                description="本安装树 data/backups，或 ZHANGE_BACKUP_DIR（仅安装根内计入）",
                business="backup",
                kind="generated",
                path=ctx.backup_dir,
                optional=True,
            )
        )
    return [row for row in rows if is_under(row.path, ctx.install_dir)]


def browse_roots(ctx: FileManagerContext) -> list[BrowseRoot]:
    try:
        resolved = ctx.install_dir.resolve()
    except OSError:
        resolved = ctx.install_dir
    return [
        BrowseRoot(
            id="install",
            label="安装根",
            path=resolved,
            exists=resolved.exists(),
        )
    ]


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
        leftover_ids = {"data_leftover", "uploads_leftover", "data_root_leftover"}
        if bucket.id in leftover_ids and size <= 0:
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
                    editable=is_file
                    and not sensitive
                    and looks_like_text_name(entry.name, size),
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


@dataclass(frozen=True)
class MutateResult:
    root_id: str
    path: str
    name: str = ""
    kept_sensitive: bool = False
    content: str = ""


def looks_like_text_name(name: str, size: int) -> bool:
    if size > MAX_EDIT_BYTES:
        return False
    text = (name or "").strip()
    if not text:
        return False
    lower = text.lower()
    if lower in TEXT_BASENAMES:
        return True
    suffix = Path(text).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return True
    if lower.endswith(".example") and Path(text[: -len(".example")]).suffix.lower() in TEXT_SUFFIXES:
        return True
    if size <= 0:
        return False
    if size <= 64 * 1024 and "." not in text.lstrip("."):
        return True
    return False


def validate_entry_name(name: str, *, from_upload: bool = False) -> str:
    text = (name or "").replace("\\", "/").strip()
    if from_upload and "/" in text:
        text = text.rsplit("/", 1)[-1].strip()
    if not text or text in {".", ".."} or "\x00" in text:
        raise FileManagerError("文件名不合法")
    if "/" in text or os.path.isabs(text) or os.path.splitdrive(text)[0]:
        raise FileManagerError("文件名不合法")
    if os.name == "nt" and ":" in text:
        raise FileManagerError("文件名不合法")
    if len(text) > MAX_ENTRY_NAME:
        raise FileManagerError("文件名过长")
    stem = text.split(".", 1)[0].rstrip(".").lower()
    if os.name == "nt" and stem in _WIN_RESERVED:
        raise FileManagerError("文件名不合法")
    if text.endswith(" ") or text.endswith("."):
        raise FileManagerError("文件名不合法")
    return text


def child_rel(dir_rel: str, name: str) -> str:
    parent = normalize_rel(dir_rel)
    child = validate_entry_name(name)
    return f"{parent}/{child}" if parent else child


def _refuse_sensitive(rel: str, action: str) -> None:
    if rel_is_sensitive(rel):
        raise FileManagerError(f"敏感路径不可{action}", status_code=403)


def _io_error(_exc: OSError, fallback: str) -> FileManagerError:
    return FileManagerError(fallback, status_code=500)


def _root_and_dir(
    root_id: str,
    dir_rel: str,
    *,
    ctx: FileManagerContext,
) -> tuple[BrowseRoot, str, Path]:
    root = _root_by_id(ctx, root_id)
    rel_n = normalize_rel(dir_rel)
    _refuse_sensitive(rel_n, "操作")
    target = resolve_in_root(root.path, rel_n)
    if not target.exists() or not target.is_dir() or target.is_symlink():
        raise FileManagerError("目录不存在", status_code=404)
    return root, rel_n, target


def dir_contains_sensitive(path: Path, rel: str) -> bool:
    if rel_is_sensitive(rel):
        return True
    try:
        if not path.is_dir() or path.is_symlink():
            return False
    except OSError:
        return True
    stack = [(path, rel)]
    while stack:
        current, current_rel = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    child_rel_n = f"{current_rel}/{entry.name}" if current_rel else entry.name
                    if rel_is_sensitive(child_rel_n):
                        return True
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append((Path(entry.path), child_rel_n))
        except OSError:
            return True
    return False


def _new_child_path(parent: Path, parent_rel: str, name: str, *, action: str) -> tuple[str, Path]:
    child_name = validate_entry_name(name)
    rel = child_rel(parent_rel, child_name)
    _refuse_sensitive(rel, action)
    target = parent.joinpath(child_name)
    try:
        resolved = target.resolve()
    except OSError as exc:
        raise FileManagerError("路径不合法") from exc
    if not is_under(resolved, parent.resolve()):
        raise FileManagerError("路径不合法")
    if resolved.exists():
        raise FileManagerError("已存在同名文件或目录", status_code=409)
    return rel, resolved


def _decode_text(data: bytes) -> str:
    if b"\x00" in data:
        raise FileManagerError("不是可编辑的文本", status_code=415)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileManagerError("不是可编辑的文本", status_code=415) from exc


def _write_bytes(path: Path, data: bytes) -> None:
    try:
        path.write_bytes(data)
    except OSError as exc:
        raise _io_error(exc, "无法写入文件") from exc


def read_text(
    root_id: str,
    rel: str,
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    target = resolve_download(root_id, rel, ctx=ctx)
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise _io_error(exc, "无法读取文件") from exc
    if size > MAX_EDIT_BYTES:
        raise FileManagerError(
            f"文件超过 {MAX_EDIT_BYTES // (1024 * 1024)}MB，请下载后编辑",
            status_code=413,
        )
    try:
        data = target.read_bytes()
    except OSError as exc:
        raise _io_error(exc, "无法读取文件") from exc
    return MutateResult(
        root_id=root_id,
        path=normalize_rel(rel),
        name=target.name,
        content=_decode_text(data),
    )


def write_text(
    root_id: str,
    rel: str,
    content: str,
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    rel_n = normalize_rel(rel)
    if not rel_n:
        raise FileManagerError("请指定文件")
    _refuse_sensitive(rel_n, "修改")
    root = _root_by_id(ctx, root_id)
    target = resolve_in_root(root.path, rel_n)
    if is_sensitive_name(target.name):
        raise FileManagerError("敏感路径不可修改", status_code=403)
    if not target.exists() or not target.is_file() or target.is_symlink():
        raise FileManagerError("文件不存在", status_code=404)
    data = (content or "").encode("utf-8")
    if len(data) > MAX_EDIT_BYTES:
        raise FileManagerError(
            f"文件内容超过 {MAX_EDIT_BYTES // (1024 * 1024)}MB，请改为上传",
            status_code=413,
        )
    _write_bytes(target, data)
    clear_size_cache()
    return MutateResult(root_id=root_id, path=rel_n, name=target.name)


def create_folder(
    root_id: str,
    dir_rel: str,
    name: str,
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    root, parent_rel, parent = _root_and_dir(root_id, dir_rel, ctx=ctx)
    _, target = _new_child_path(parent, parent_rel, name, action="创建")
    try:
        target.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise FileManagerError("已存在同名文件或目录", status_code=409) from exc
    except OSError as exc:
        raise _io_error(exc, "无法创建目录") from exc
    clear_size_cache()
    return MutateResult(root_id=root.id, path=parent_rel, name=target.name)


def create_file(
    root_id: str,
    dir_rel: str,
    name: str,
    content: str = "",
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    root, parent_rel, parent = _root_and_dir(root_id, dir_rel, ctx=ctx)
    data = (content or "").encode("utf-8")
    if len(data) > MAX_EDIT_BYTES:
        raise FileManagerError(
            f"文件内容超过 {MAX_EDIT_BYTES // (1024 * 1024)}MB，请改为上传",
            status_code=413,
        )
    _, target = _new_child_path(parent, parent_rel, name, action="创建")
    _write_bytes(target, data)
    clear_size_cache()
    return MutateResult(root_id=root.id, path=parent_rel, name=target.name)


def upload_file(
    root_id: str,
    dir_rel: str,
    filename: str,
    data: bytes,
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileManagerError("上传不能超过 256MB", status_code=413)
    root, parent_rel, parent = _root_and_dir(root_id, dir_rel, ctx=ctx)
    child_name = validate_entry_name(filename, from_upload=True)
    rel = child_rel(parent_rel, child_name)
    _refuse_sensitive(rel, "上传")
    target = parent.joinpath(child_name)
    try:
        resolved = target.resolve()
    except OSError as exc:
        raise FileManagerError("路径不合法") from exc
    if not is_under(resolved, parent.resolve()):
        raise FileManagerError("路径不合法")
    if resolved.exists() and (resolved.is_dir() or resolved.is_symlink()):
        raise FileManagerError("已存在同名目录", status_code=409)
    if is_sensitive_name(resolved.name):
        raise FileManagerError("敏感路径不可上传", status_code=403)
    _write_bytes(resolved, data)
    clear_size_cache()
    return MutateResult(root_id=root.id, path=parent_rel, name=resolved.name)


def rename_entry(
    root_id: str,
    dir_rel: str,
    src: str,
    dest: str,
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    root, parent_rel, parent = _root_and_dir(root_id, dir_rel, ctx=ctx)
    src_name = validate_entry_name(src)
    dest_name = validate_entry_name(dest)
    if src_name == dest_name:
        return MutateResult(root_id=root.id, path=parent_rel, name=dest_name)
    src_rel = child_rel(parent_rel, src_name)
    dest_rel = child_rel(parent_rel, dest_name)
    _refuse_sensitive(src_rel, "重命名")
    _refuse_sensitive(dest_rel, "重命名")
    src_path = parent.joinpath(src_name)
    dest_path = parent.joinpath(dest_name)
    try:
        src_resolved = src_path.resolve()
        dest_resolved = dest_path.resolve()
        parent_resolved = parent.resolve()
    except OSError as exc:
        raise FileManagerError("路径不合法") from exc
    if not is_under(src_resolved, parent_resolved) or not is_under(dest_resolved, parent_resolved):
        raise FileManagerError("路径不合法")
    if not src_resolved.exists() or src_resolved.is_symlink():
        raise FileManagerError("文件不存在", status_code=404)
    if dest_resolved.exists():
        raise FileManagerError("已存在同名文件或目录", status_code=409)
    if src_resolved.is_dir() and dir_contains_sensitive(src_resolved, src_rel):
        raise FileManagerError("目录含敏感文件，不可重命名", status_code=403)
    try:
        src_resolved.rename(dest_resolved)
    except OSError as exc:
        raise _io_error(exc, "无法重命名") from exc
    clear_size_cache()
    return MutateResult(root_id=root.id, path=parent_rel, name=dest_name)


def _delete_tree(path: Path, rel: str) -> bool:
    """Delete path; skip sensitive descendants. True if path is gone."""
    if rel_is_sensitive(rel):
        return False
    try:
        if path.is_symlink():
            return False
        if path.is_file():
            path.unlink()
            return True
        if not path.is_dir():
            return False
    except OSError as exc:
        raise _io_error(exc, "无法删除") from exc
    remaining = False
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError as exc:
        raise _io_error(exc, "无法删除") from exc
    for entry in entries:
        child_rel_n = f"{rel}/{entry.name}" if rel else entry.name
        child = Path(entry.path)
        if rel_is_sensitive(child_rel_n) or entry.is_symlink():
            remaining = True
            continue
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
            is_file = entry.is_file(follow_symlinks=False)
        except OSError:
            remaining = True
            continue
        if is_dir:
            if not _delete_tree(child, child_rel_n):
                remaining = True
        elif is_file:
            try:
                child.unlink()
            except OSError as exc:
                raise _io_error(exc, "无法删除") from exc
        else:
            remaining = True
    if remaining:
        return False
    try:
        path.rmdir()
    except OSError:
        return False
    return True


def delete_entries(
    root_id: str,
    dir_rel: str,
    names: list[str],
    *,
    ctx: FileManagerContext | None = None,
) -> MutateResult:
    ctx = ctx or context_from_settings()
    if not names:
        raise FileManagerError("请选择要删除的文件")
    if len(names) > MAX_DELETE_NAMES:
        raise FileManagerError(f"一次最多删除 {MAX_DELETE_NAMES} 项")
    root, parent_rel, parent = _root_and_dir(root_id, dir_rel, ctx=ctx)
    kept_sensitive = False
    last_name = ""
    seen: set[str] = set()
    for raw in names:
        name = validate_entry_name(raw)
        if name in seen:
            continue
        seen.add(name)
        rel = child_rel(parent_rel, name)
        _refuse_sensitive(rel, "删除")
        target = parent.joinpath(name)
        try:
            resolved = target.resolve()
        except OSError as exc:
            raise FileManagerError("路径不合法") from exc
        if not is_under(resolved, parent.resolve()):
            raise FileManagerError("路径不合法")
        if not resolved.exists():
            raise FileManagerError(f"{name} 不存在", status_code=404)
        if resolved.is_symlink():
            raise FileManagerError("不支持删除该项目")
        gone = _delete_tree(resolved, rel)
        if not gone and resolved.exists():
            kept_sensitive = True
        last_name = name
    clear_size_cache()
    return MutateResult(
        root_id=root.id,
        path=parent_rel,
        name=last_name,
        kept_sensitive=kept_sensitive,
    )
