"""官方简体中文：只读游戏目录 Language/zh-CN，按令牌核对 wiki 图鉴。"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.database import SessionLocal
from app.core.timeutil import now_naive
from app.models.guide_raw import GuideRaw
from app.models.job_run import JobRun
from app.services.guide_raw.lock import SyncBusy, SyncGate
from app.services.guide_raw.pipeline import GuideRawPipeline, RawSpec
from app.services.job_runs_prune import fail_job_run
from app.services.ror2.catalog import Ror2WikiError
from app.services.ror2.schemas import Ror2CatalogOut, Ror2ItemOut
from app.services.scheduler_config import load_scheduler_config

log = logging.getLogger("zhange.ror2")

JOB_KEY = "ror2_lang_sync"
_LOG_KEY = "ror2-lang"
_MAX_FILE_BYTES = 8 * 1024 * 1024
_NAME = "_NAME"
_DESC = "_DESC"
_PICKUP = "_PICKUP"
_PATH_RE = re.compile(r'"path"\s+"((?:\\.|[^"\\])*)"')
_DLC_RE = re.compile(r"^DLC(\d+)", re.IGNORECASE)

LANG_GATE = SyncGate("雨中冒险2语言文件正在同步")


class Ror2LangError(Exception):
    pass


def resolve_lang_dir(configured: str | None = None) -> Path:
    """配置优先；空则在 Steam 库里找 Language/zh-CN。"""
    raw = (configured if configured is not None else _configured_dir()).strip()
    if raw:
        return ensure_lang_dir(Path(raw))
    found = discover_steam_lang_dir()
    if found is None:
        raise Ror2LangError(
            "没有找到 Language/zh-CN。把游戏更新后的该目录写到任务配置 ror2_lang_sync.lang_dir"
        )
    return found


def ensure_lang_dir(path: Path) -> Path:
    if path.is_symlink():
        raise Ror2LangError("语言目录不能是符号链接")
    resolved = path.resolve()
    if resolved.name.lower() != "zh-cn":
        raise Ror2LangError("语言目录必须是 zh-CN")
    if not resolved.is_dir():
        raise Ror2LangError(f"没有找到语言目录：{resolved}")
    return resolved


def locate_lang_dir(executable: Path) -> Path:
    """先认 steamcmd 旁边的库，再认 Linux 上安装根或主目录里的 Steam 库。"""
    from app.services.ror2.steamcmd import lang_dir_from_steamcmd

    parent = executable.resolve().parent
    roots = [parent] if not parent.is_symlink() else []
    roots.extend(_posix_steam_roots())
    found = _pick_lang_dir(_lang_dirs_under(roots))
    if found is not None:
        return found
    return lang_dir_from_steamcmd(executable)


def discover_steam_lang_dir() -> Path | None:
    roots = list(steam_libraries())
    roots.extend(_posix_steam_roots())
    return _pick_lang_dir(_lang_dirs_under(roots))


def steam_libraries() -> list[Path]:
    libraries: list[Path] = []
    for vdf in _library_manifests():
        try:
            text = vdf.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _PATH_RE.finditer(text):
            folder = Path(match.group(1).replace("\\\\", "\\"))
            if folder.is_dir():
                libraries.append(folder)
    return libraries


def lang_file_sort_key(name: str) -> tuple[int, int, str]:
    """底稿在前，DLC 按编号在后。DLC10 排在 DLC4 后面，后读的键覆盖先读的。"""
    stem = Path(name).stem
    match = _DLC_RE.match(stem)
    if match:
        return (1, int(match.group(1)), name.lower())
    base_rank = 0 if name.lower() == "output.json" else 1
    return (0, base_rank, name.lower())


def lang_files(directory: Path) -> list[Path]:
    """目录里每个带令牌的 JSON 都算一份。没有令牌的（语言元数据等）跳过。坏 JSON 中止。"""
    chosen: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".json":
            continue
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise Ror2LangError(f"{path.name} 超过 {_MAX_FILE_BYTES} 字节")
        body = path.read_text(encoding="utf-8-sig")
        if string_table(body, path.name):
            chosen.append(path)
    chosen.sort(key=lambda path: lang_file_sort_key(path.name))
    if not chosen:
        raise Ror2LangError("zh-CN 里没有本地化令牌文件")
    return chosen


def string_table(body: str, name: str) -> dict[str, str]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise Ror2LangError(f"{name} 不是 JSON") from exc
    if not isinstance(payload, dict):
        raise Ror2LangError(f"{name} 不是 JSON 对象")
    nested = payload.get("strings", payload.get("Strings"))
    source = nested if isinstance(nested, dict) else payload
    table = {
        key: value
        for key, value in source.items()
        if isinstance(key, str) and isinstance(value, str) and "_" in key and key.upper() == key
    }
    return table


def merge_string_tables(tables: list[dict[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for table in tables:
        merged.update(table)
    return merged


def coverage_report(catalog: Ror2CatalogOut, strings: dict[str, str]) -> str:
    lines = [
        _group_line("items", catalog.items, strings),
        _group_line("equipment", catalog.equipment, strings),
        (
            f"survivors {len(catalog.survivors)}，"
            "wiki 模块没有 LocalizationInternalName，不能按令牌映射"
        ),
    ]
    return "\n".join(lines)


def sync_lang(db: Session, directory: Path) -> str:
    """把 zh-CN 里的 JSON 落入 guide_raws，并对照已落库的 wiki 令牌。"""
    from app.services.ror2.wiki import PIPELINE as wiki_pipeline
    from app.services.ror2.wiki import get_catalog

    folder = ensure_lang_dir(directory)
    files = lang_files(folder)
    specs = tuple(_spec(folder, path) for path in files)
    pipeline = GuideRawPipeline("ror2", specs, gate=LANG_GATE)
    results = pipeline.sync(db)
    failed = [row for row in results if not row["ok"]]
    if failed:
        detail = "；".join(f"{row['resource']}：{row['error']}" for row in failed)
        log_until_change(log, _LOG_KEY, "雨中冒险2语言文件同步未完成：%s", detail)
        raise Ror2LangError(detail)
    clear_log_until_change(_LOG_KEY)
    if wiki_pipeline.missing(db):
        raise Ror2WikiError("wiki 图鉴还没有落库，无法核对令牌")
    catalog = get_catalog(db)
    strings = merge_string_tables(
        [string_table(text, resource) for resource, text in pipeline.load_texts(db).items()]
    )
    removed = _drop_stale(db, {spec.resource for spec in specs})
    changed = [str(row["resource"]) for row in results if row["changed"]]
    names = "、".join(path.name for path in files)
    head = f"读取 {names}。语言文件已落库：" + ("、".join(changed) if changed else "内容未变")
    if removed:
        head += "。已去掉：" + "、".join(removed)
    report = head + "\n" + coverage_report(catalog, strings)
    log.info("雨中冒险2语言文件已核对\n%s", report)
    return report


def sync_job() -> None:
    db = SessionLocal()
    job = JobRun(job_key=JOB_KEY, status="running", started_at=now_naive())
    db.add(job)
    db.commit()
    run_id = job.id
    try:
        try:
            with LANG_GATE.exclusive():
                report = sync_lang(db, _lang_dir_for_job())
        except SyncBusy:
            job.status = "ok"
            job.message = "已有同步在跑"
            job.finished_at = now_naive()
            db.commit()
            return
        job.status = "ok"
        job.message = report
        job.finished_at = now_naive()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.exception("雨中冒险2语言文件同步失败")
        fail_job_run(db, run_id, str(exc))
    finally:
        db.close()


def _drop_stale(db: Session, current: set[str]) -> list[str]:
    """目录里已经没有的 zh-CN 文件，从 guide_raws 去掉，避免旧 DLC 文件继续参与覆盖。"""
    rows = (
        db.query(GuideRaw)
        .filter(GuideRaw.game == "ror2", GuideRaw.resource.like("zh-CN/%"))
        .all()
    )
    removed = [row.resource for row in rows if row.resource not in current]
    for row in rows:
        if row.resource in removed:
            db.delete(row)
    if removed:
        db.commit()
    return removed


def _spec(folder: Path, path: Path) -> RawSpec:
    def fetch(path: Path = path) -> str:
        if path.stat().st_size > _MAX_FILE_BYTES:
            raise Ror2LangError(f"{path.name} 超过 {_MAX_FILE_BYTES} 字节")
        return path.read_text(encoding="utf-8-sig")

    def accept(body: str, name: str = path.name) -> None:
        string_table(body, name)

    return RawSpec(
        resource=f"zh-CN/{path.name}",
        source=str(folder),
        fetch=fetch,
        accept=accept,
    )


def _group_line(kind: str, rows: list[Ror2ItemOut], strings: dict[str, str]) -> str:
    tokens = [row.internal_name for row in rows if row.internal_name]
    no_token = [row.name for row in rows if not row.internal_name]
    total = len(tokens)

    def hits(suffix: str) -> int:
        return sum(1 for token in tokens if f"{token}{suffix}" in strings)

    line = (
        f"{kind} 有令牌 {total}/{len(rows)}，"
        f"NAME {hits(_NAME)}/{total}，"
        f"DESC {hits(_DESC)}/{total}，"
        f"PICKUP {hits(_PICKUP)}/{total}"
    )
    missing = [token for token in tokens if f"{token}{_NAME}" not in strings]
    if missing:
        shown = "、".join(missing[:20])
        extra = f" 等 {len(missing)} 个" if len(missing) > 20 else ""
        line += f"；缺 NAME：{shown}{extra}"
    if no_token:
        line += "；wiki 无令牌：" + "、".join(no_token)
    return line


def _lang_dir_for_job() -> Path:
    """配了 SteamCMD 就先 app_update，再读已经装好的 zh-CN。否则沿用原来的目录。"""
    from app.services.integrations_config import load_integrations
    from app.services.ror2.steamcmd import SteamCmdError, run_ror2_update, steamcmd_ready

    cfg = load_integrations()
    if not steamcmd_ready(cfg):
        return resolve_lang_dir()
    try:
        executable = run_ror2_update(cfg)
        folder = locate_lang_dir(executable)
    except SteamCmdError as exc:
        raise Ror2LangError(str(exc)) from exc
    return ensure_lang_dir(folder)


def _posix_steam_roots() -> list[Path]:
    """Linux SteamCMD 的默认库。服务用户的家目录是安装根时，库就在安装根的 Steam/。"""
    from app.core.paths import resolve_install_dir

    home = Path.home()
    folders = (
        resolve_install_dir() / "Steam",
        home / "Steam",
        home / ".local" / "share" / "Steam",
        home / ".steam" / "steam",
    )
    roots: list[Path] = []
    for folder in folders:
        try:
            if folder.is_symlink() or not folder.is_dir():
                continue
        except OSError:
            continue
        roots.append(folder)
    return roots


def _lang_dirs_under(roots: list[Path]) -> list[Path]:
    from app.services.ror2.steamcmd import LANG_DIR_PARTS

    ordered: list[Path] = []
    seen: set[Path] = set()
    libraries: list[Path] = []
    for root in roots:
        libraries.append(root)
        libraries.extend(_libraries_under(root))
    for library in libraries:
        candidate = (library / "steamapps" / "common" / "Risk of Rain 2").joinpath(*LANG_DIR_PARTS)
        try:
            key = candidate.resolve()
        except OSError:
            key = candidate
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def _libraries_under(root: Path) -> list[Path]:
    found: list[Path] = []
    for relative in ("steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"):
        path = root / relative
        try:
            if path.is_symlink() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _PATH_RE.finditer(text):
            folder = Path(match.group(1).replace("\\\\", "\\"))
            try:
                if folder.is_symlink() or not folder.is_dir():
                    continue
            except OSError:
                continue
            found.append(folder)
    return found


def _pick_lang_dir(candidates: list[Path]) -> Path | None:
    usable = [path for path in candidates if _usable_lang_dir(path)]
    for path in usable:
        try:
            has_json = any(
                item.is_file() and not item.is_symlink() and item.suffix.lower() == ".json"
                for item in path.iterdir()
            )
        except OSError:
            continue
        if has_json:
            return path.resolve()
    if not usable:
        return None
    return usable[0].resolve()


def _usable_lang_dir(path: Path) -> bool:
    try:
        return not path.is_symlink() and path.is_dir() and path.name.lower() == "zh-cn"
    except OSError:
        return False


def _configured_dir() -> str:
    cfg = load_scheduler_config(None).get(JOB_KEY) or {}
    return str(cfg.get("lang_dir") or "")


def _library_manifests() -> list[Path]:
    roots: list[Path] = []
    steam = _steam_root()
    if steam is not None:
        roots.append(steam)
    program_files = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles") or ""
    if program_files:
        roots.append(Path(program_files) / "Steam")
    manifests: list[Path] = []
    for root in roots:
        for relative in ("steamapps/libraryfolders.vdf", "config/libraryfolders.vdf"):
            path = root / relative
            if path.is_file():
                manifests.append(path)
    return manifests


def _steam_root() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
    except OSError:
        return None
    path = Path(str(value))
    return path if path.is_dir() else None
