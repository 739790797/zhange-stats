"""钥匙箱截图识别：540 方块切块 + 多引擎交叉验证 + 短名闭集匹配。

识价作者经验：通用 OCR 认格子 shortName；切块 360–640（最佳约 520–540）正方形；
i/l 等易混字做映射。引擎由系统配置「文字识别」按场景「塔科夫钥匙箱」挑选
（熊猫 OCR / EasyOCR）。权重走任务配置「文字识别模型」，识别时不再现场下载。
每族再跑反色补召回；多端校验开启时，模糊匹配须两个不同族同时读到，单族反色不算第二票。
不走单格最小方块，也不走钥匙胚图标匹配。
"""

from __future__ import annotations

import io
import re
import threading
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.ocr.boxes import box_to_xywh  # noqa: F401
from app.services.ocr.types import NamedEngine, OcrEngine, OcrError, OcrLine
from app.services.tarkov.search import compact_text, hit_rank

Image.MAX_IMAGE_PIXELS = 20_000_000

TILE_BEST = 540
TILE_ALT = 520
TILE_MIN = 360
TILE_MAX = 640
TILE_OVERLAP = 0.2
MAX_TILES = 8
MAX_RECOGNIZE_BYTES = 8 * 1024 * 1024
MAX_CONCURRENT_RECOGNIZE = 1
_RECOGNIZE_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_RECOGNIZE)
MIN_SOURCE_EDGE = 80
FUZZY_OK = 0.82
OVERLAY_MISS_CAP = 48

_USES_RE = re.compile(r"\d{1,2}\s*/\s*\d{1,2}")
_LATIN_TOKEN_RE = re.compile(r"^[0-9a-z]+$")
_TOKEN_SPLIT_RE = re.compile(r"[\s|/\\,;]+")
_LATIN_CODE_RE = re.compile(r"[A-Za-z]{1,5}[- .]?[A-Za-z0-9]{1,8}")
_PUNCT_RE = re.compile(
    r"[·•・．.。,，、:：;；!！?？\"'“”‘’（）()【】\[\]<>《》\-_—–−_/=\\|]+"
)
_SPACE_RE = re.compile(r"[\s\u3000]+")
_ELLIPSIS_RE = re.compile(r"…+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ROOM_GLYPH_RE = re.compile(r"[钥匙铂铀角旬钼钠是此十赤最妇到]")
_DORM_ONE_RE = re.compile(r"^1(\d{2})([钥匙铂铀角旬钼钠是此十赤最妇到].*)$")
_MARKED_ROOM_RE = re.compile(r"^(\d{3})(.+)$")
_ROOM_KEY_RE = re.compile(r"^(东|西)(\d{3})(?:钥匙)?$")
_TOKEN_ROOM_RE = re.compile(r"(?:东|西)(\d{3})")

_NOISE_RAW = (
    "钥匙",
    "钥匙箱",
    "钥匙柜",
    "钥匙工具",
    "文件箱",
    "文件",
    "搜索",
    "全部",
    "筛选",
    "已拥有",
    "未拥有",
    "耐久",
    "用途",
    "物品",
    "仓库",
    "装备",
    "key",
    "keys",
    "keytool",
    "docs",
    "docscase",
    "sicc",
)
_WEAK_RAW = ("key", "keys", "钥匙", "钥匙箱", "钥匙卡", "工厂", "卡", "管理员")

COLOR_CARD_REPAIR = {
    "傅卡": "黑卡",
    "墨卡": "黑卡",
    "嘿卡": "黑卡",
}

_CONFUSION_GROUPS = (
    ("i", "l", "1", "|"),
    ("o", "0"),
    ("s", "5"),
    ("b", "8"),
)


class TarkovKeyOcrError(OcrError):
    """钥匙箱识别错误（OcrError 子类，路由可统一 except OcrError）。"""


class RecognizeCancelled(Exception):
    """客户端断开或主动取消后，工作线程在下一刀切块前退出。"""


TileRecognizer = OcrEngine
NamedRecognizer = NamedEngine
ProgressFn = Callable[[str, dict[str, Any]], None]


def try_begin_recognize() -> bool:
    return _RECOGNIZE_SLOTS.acquire(blocking=False)


def end_recognize() -> None:
    _RECOGNIZE_SLOTS.release()


def _throw_if_cancelled(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise RecognizeCancelled()


@dataclass(frozen=True)
class TileGeom:
    x: int
    y: int
    w: int
    h: int
    square_side: int
    prepared_side: int


@dataclass(frozen=True)
class LocatedToken:
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class OcrToken:
    text: str
    engines: frozenset[str]


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    short_name: str
    icon_link: str
    name_key: str
    short_key: str
    compact_name: str
    compact_short: str
    short_aliases: tuple[str, ...]


@dataclass(frozen=True)
class KeyOcrMatch:
    id: str
    name: str
    short_name: str
    icon_link: str
    ocr_text: str
    confidence: str


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower()
    text = _SPACE_RE.sub("", text)
    text = _PUNCT_RE.sub("", text)
    return _ELLIPSIS_RE.sub("", text)


KEY_OCR_NOISE = {normalize_text(s) for s in _NOISE_RAW}
WEAK_SHORT = {normalize_text(s) for s in _WEAK_RAW}


def engine_family(name: str) -> str:
    raw = (name or "").strip()
    if raw.endswith("_inv"):
        return raw[:-4] or raw
    return raw or "direct"


def families_agreed(engines: frozenset[str] | set[str]) -> bool:
    """模糊匹配要两个模型族同时命中；paddle 与 paddle_inv 仍算一族。"""
    families = {
        engine_family(item)
        for item in engines
        if item and item != "direct"
    }
    return len(families) >= 2


def fuzzy_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    dist = _levenshtein(a, b)
    min_len = min(len(a), len(b))
    score = 1 - dist / max(len(a), len(b))
    if dist <= 1 and min_len >= 2:
        return max(score, 0.82)
    if dist <= 2 and min_len >= 3:
        return max(score, 0.78)
    if dist <= 3 and min_len >= 5:
        return max(score, 0.72)
    return score


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    curr = [0] * (len(b) + 1)
    for i, ca in enumerate(a, start=1):
        curr[0] = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[len(b)]


def repair_token(text: str) -> str:
    out = re.sub(r"\s+", " ", text or "").strip()
    out = re.sub(r"[|)\]]+$", "", out)
    out = re.sub(r"画(?=\d{3})", "西", out)
    out = re.sub(r"^w[il]?(\d{3})$", r"西\1", out, flags=re.I)
    out = re.sub(r"^空自$", "空白", out)
    out = re.sub(r"^[#＃]1sr$", "#11SR", out, flags=re.I)
    out = re.sub(r"^3区1sr$", "#11SR", out, flags=re.I)
    out = re.sub(r"^rbav{2,}o$", "RB-VO", out, flags=re.I)
    out = re.sub(r"^enak\s*13$", "Chek. 13", out, flags=re.I)
    out = re.sub(r"^管办$", "主管办", out)
    out = re.sub(r"^蛇卡$", "红卡", out)
    out = re.sub(r"^生锈.+$", "生锈钥匙", out)
    out = re.sub(r"^h(\d{3})$", r"西\1", out, flags=re.I)
    out = re.sub(r"^rbz?s?rh$", "RB-RH", out, flags=re.I)
    out = re.sub(r"^rb[- =]*pk(?:pm|r+)$", "RB-PKPM", out, flags=re.I)
    out = re.sub(r"^rb[- ]*rssp2$", "RB-PSP2", out, flags=re.I)
    out = re.sub(r"^管理员[铂铀角旬钼钠是匙]+$", "管理员钥匙", out)
    out = re.sub(r"^加油关$", "加油站", out)
    out = re.sub(r"^海关[物移][消流油]$", "海关物流", out)
    return COLOR_CARD_REPAIR.get(out, out)


def confuse_variants(text: str, *, limit: int = 12) -> list[str]:
    """i/l/1、0/O 等易混字映射；控制组合数，避免短码爆炸。"""
    seed = repair_token(text)
    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        key = normalize_text(value)
        if not key or key in seen or len(out) >= limit:
            return
        seen.add(key)
        out.append(value)

    add(seed)
    lower = seed
    for group in _CONFUSION_GROUPS:
        chars = set(group)
        if not any(ch.lower() in chars or ch in chars for ch in lower):
            continue
        for src in group:
            for dst in group:
                if src == dst:
                    continue
                add(lower.replace(src, dst).replace(src.upper(), dst))
                if len(out) >= limit:
                    return out
    return out


def choose_tile_size(width: int, height: int) -> int:
    longest = max(width, height)
    if longest <= TILE_MAX:
        return max(longest, TILE_MIN) if longest else TILE_BEST
    return TILE_BEST


def tile_rects(
    width: int,
    height: int,
    *,
    size: int | None = None,
    overlap: float = TILE_OVERLAP,
    max_tiles: int = MAX_TILES,
) -> list[tuple[int, int, int, int]]:
    """返回 (x, y, w, h) 切块。图已在 360–640 内则整图一块。"""
    if width <= 0 or height <= 0:
        return []
    longest = max(width, height)
    if longest <= TILE_MAX:
        return [(0, 0, width, height)]
    tile = size or choose_tile_size(width, height)
    tile = max(TILE_MIN, min(TILE_MAX, tile))
    for frac in (overlap, 0.1, 0.0):
        boxes = _grid_boxes(width, height, tile, frac)
        if len(boxes) <= max_tiles:
            return boxes
    bigger = min(TILE_MAX, max(tile, TILE_MAX))
    return _grid_boxes(width, height, bigger, 0.0)[:max_tiles]


def _grid_boxes(
    width: int, height: int, tile: int, overlap: float
) -> list[tuple[int, int, int, int]]:
    step = max(1, int(round(tile * (1 - overlap))))
    xs = _axis(width, tile, step)
    ys = _axis(height, tile, step)
    boxes: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for y in ys:
        for x in xs:
            w = min(tile, width - x)
            h = min(tile, height - y)
            box = (x, y, w, h)
            if box in seen or w < 24 or h < 24:
                continue
            seen.add(box)
            boxes.append(box)
    return boxes


def _axis(length: int, tile: int, step: int) -> list[int]:
    if length <= tile:
        return [0]
    xs = list(range(0, length - tile + 1, step))
    last = length - tile
    if not xs or xs[-1] != last:
        xs.append(max(0, last))
    return xs


def prepared_side_for(square_side: int, target: int = TILE_BEST) -> int:
    if square_side < TILE_MIN:
        return TILE_MIN
    if square_side > TILE_MAX:
        return TILE_MAX
    goal = TILE_ALT if abs(square_side - TILE_ALT) < abs(square_side - target) else target
    if abs(square_side - goal) <= 24:
        return square_side
    return goal


def tile_geom(
    box: tuple[int, int, int, int],
    *,
    target: int = TILE_BEST,
) -> TileGeom:
    x, y, w, h = box
    side = max(w, h)
    return TileGeom(x, y, w, h, side, prepared_side_for(side, target))


def map_tile_xywh(
    geom: TileGeom,
    x: float,
    y: float,
    w: float,
    h: float,
) -> tuple[float, float, float, float] | None:
    """把准备后方图上的框映射回原图。忽略贴成正方形时右侧/底部的黑边。"""
    if geom.prepared_side <= 0 or geom.square_side <= 0 or w < 1 or h < 1:
        return None
    scale = geom.prepared_side / geom.square_side
    sx = x / scale
    sy = y / scale
    sw = w / scale
    sh = h / scale
    if sx >= geom.w or sy >= geom.h:
        return None
    clip_x = max(0.0, sx)
    clip_y = max(0.0, sy)
    clip_w = min(sx + sw, float(geom.w)) - clip_x
    clip_h = min(sy + sh, float(geom.h)) - clip_y
    if clip_w < 2 or clip_h < 2:
        return None
    return (geom.x + clip_x, geom.y + clip_y, clip_w, clip_h)


def as_ocr_lines(raw: Any) -> list[OcrLine]:
    if not raw:
        return []
    out: list[OcrLine] = []
    for item in raw:
        if isinstance(item, OcrLine):
            text = item.text.strip()
            if text:
                out.append(item if text == item.text else OcrLine(text, item.x, item.y, item.w, item.h))
            continue
        text = str(item).strip()
        if text:
            out.append(OcrLine(text=text))
    return out


def prepare_tile(
    image: Image.Image,
    box: tuple[int, int, int, int],
    *,
    target: int = TILE_BEST,
) -> Image.Image:
    geom = tile_geom(box, target=target)
    crop = image.convert("RGB").crop((geom.x, geom.y, geom.x + geom.w, geom.y + geom.h))
    square = Image.new("RGB", (geom.square_side, geom.square_side), (0, 0, 0))
    square.paste(crop, (0, 0))
    if square.size[0] == geom.prepared_side:
        return square
    return square.resize(
        (geom.prepared_side, geom.prepared_side),
        Image.Resampling.BICUBIC,
    )


def flatten_key_catalog(packs: dict[str, Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    groups: list[Any] = []
    if isinstance(packs, dict):
        maps = packs.get("maps")
        if isinstance(maps, list):
            groups.extend(maps)
        groups.append({"keys": packs.get("unbound") or []})
    for group in groups:
        if not isinstance(group, dict):
            continue
        for key in group.get("keys") or []:
            if not isinstance(key, dict):
                continue
            ident = str(key.get("id") or "").strip()
            if not ident or ident in seen:
                continue
            seen.add(ident)
            out.append(
                {
                    "id": ident,
                    "name": str(key.get("name") or ""),
                    "short_name": str(key.get("short_name") or ""),
                    "icon_link": str(key.get("icon_link") or ""),
                }
            )
    return out


def parse_tokens(*texts: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        text = repair_token(raw)
        if not text or _is_noise(text):
            return
        key = normalize_text(text)
        if not key or len(key) < 2 or key in seen:
            return
        if _is_short_latin(key):
            return
        seen.add(key)
        out.append(text)

    for line in _collect_lines(*texts):
        add(line)
        for part in _TOKEN_SPLIT_RE.split(line):
            add(part)
        for match in _LATIN_CODE_RE.finditer(line):
            add(match.group(0))
    return out


def match_keys(
    tokens: list[OcrToken] | list[str],
    catalog: list[dict[str, str]],
    *,
    cross_check: bool = True,
) -> list[KeyOcrMatch]:
    entries = _catalog_entries(catalog)
    if not entries:
        return []
    unique: list[OcrToken] = []
    engines_by_key: dict[str, set[str]] = {}
    order: list[str] = []
    for item in tokens:
        if isinstance(item, OcrToken):
            repaired = repair_token(item.text)
            engines = set(item.engines)
        else:
            repaired = repair_token(item)
            engines = {"direct"}
        key = normalize_text(repaired)
        if not key or len(key) < 2 or _is_short_latin(key):
            continue
        if key not in engines_by_key:
            engines_by_key[key] = set()
            order.append(repaired)
        engines_by_key[key].update(engines)
    for text in order:
        unique.append(
            OcrToken(text=text, engines=frozenset(engines_by_key[normalize_text(text)]))
        )

    matches: list[KeyOcrMatch] = []
    used: set[str] = set()

    def push(entry: CatalogEntry, ocr_text: str, confidence: str) -> None:
        if entry.id in used:
            return
        used.add(entry.id)
        matches.append(
            KeyOcrMatch(
                id=entry.id,
                name=entry.name,
                short_name=entry.short_name,
                icon_link=entry.icon_link,
                ocr_text=ocr_text,
                confidence=confidence,
            )
        )

    for token in unique:
        agreed = (not cross_check) or families_agreed(token.engines)
        needles = confuse_variants(token.text)
        exact_short: list[CatalogEntry] = []
        seen_ids: set[str] = set()
        for needle_text in needles:
            needle = normalize_text(needle_text)
            compact = compact_text(needle_text)
            if not needle or needle in WEAK_SHORT:
                continue
            for entry in entries:
                if entry.id in seen_ids:
                    continue
                if _alias_hits(entry, needle, compact):
                    exact_short.append(entry)
                    seen_ids.add(entry.id)
        if len(exact_short) == 1:
            push(exact_short[0], token.text, "exact")
            continue
        if len(exact_short) > 1:
            continue
        if _is_numeric(token.text):
            continue
        if _is_misread_dorm_one(token.text, entries, used):
            continue

        needle = normalize_text(token.text)
        compact = compact_text(token.text)
        exact_name = [
            entry
            for entry in entries
            if entry.name_key == needle or entry.compact_name == compact
        ]
        if len(exact_name) == 1:
            push(exact_name[0], token.text, "exact")
            continue

        scored: list[tuple[CatalogEntry, int, float, bool]] = []
        for entry in entries:
            if entry.id in used:
                continue
            rank, fuzzy, exact = _score_token(token.text, entry)
            threshold = 0.72 if agreed else FUZZY_OK
            ok = exact or rank in (0, 1) or fuzzy >= threshold
            if not ok:
                continue
            scored.append((entry, rank, fuzzy, exact))
        scored.sort(key=lambda row: (not row[3], row[1], -row[2]))
        if not scored:
            marked = _marked_room_fallback(token.text, entries, used)
            if marked:
                push(marked, token.text, "fuzzy")
            continue
        best = scored[0]
        second = scored[1] if len(scored) > 1 else None
        if (
            second
            and not best[3]
            and best[1] == second[1]
            and abs(best[2] - second[2]) < 0.06
        ):
            continue
        if not best[3] and best[1] > 1 and best[2] < (0.72 if agreed else FUZZY_OK):
            continue
        push(
            best[0],
            token.text,
            "exact" if best[3] or best[1] == 0 else "fuzzy",
        )
    return matches


def load_image(raw: bytes) -> Image.Image:
    if not raw:
        raise TarkovKeyOcrError("请粘贴截图")
    if len(raw) > MAX_RECOGNIZE_BYTES:
        raise TarkovKeyOcrError("图片过大，请裁切钥匙箱后再试")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except UnidentifiedImageError as exc:
        raise TarkovKeyOcrError("无法读取截图") from exc
    except OSError as exc:
        raise TarkovKeyOcrError("无法读取截图") from exc
    image = image.convert("RGB")
    width, height = image.size
    if width < MIN_SOURCE_EDGE or height < MIN_SOURCE_EDGE:
        raise TarkovKeyOcrError("图片过小，请使用游戏内钥匙箱截图")
    return image


def wants_progress_stream(accept: str, progress_header: str = "") -> bool:
    """客户端用 Accept: ndjson 或 X-Recognize-Progress 要逐步进度。"""
    if "application/x-ndjson" in (accept or "").lower():
        return True
    return (progress_header or "").strip().lower() in {"1", "true", "yes"}


def progress_payload(message: str, stats: dict[str, Any] | None = None) -> dict[str, Any]:
    row = stats or {}
    phase = str(row.get("phase") or "ocr").strip() or "ocr"
    return {
        "event": "progress",
        "message": (message or "识别中…").strip() or "识别中…",
        "percent": _clamp_percent(row.get("percent")),
        "phase": phase,
    }


def collect_tile_tokens(
    image: Image.Image,
    recognizers: Sequence[NamedRecognizer],
    *,
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> tuple[list[OcrToken], int, dict[str, LocatedToken]]:
    _throw_if_cancelled(cancel)
    boxes = tile_rects(image.width, image.height)
    bag: dict[str, set[str]] = {}
    order: list[str] = []
    located: dict[str, LocatedToken] = {}
    pack = [item for item in recognizers if item.name.strip()]
    tile_total = max(1, len(boxes))
    step_total = max(1, tile_total * max(1, len(pack)) * 2)
    step = 0
    warmed: set[str] = set()
    _emit_progress(
        progress,
        f"已切成 {len(boxes)} 块正方形",
        percent=8,
        phase="tiles",
        tile_count=len(boxes),
        tile_index=0,
        step=0,
        step_total=step_total,
    )
    for tile_index, box in enumerate(boxes, start=1):
        _throw_if_cancelled(cancel)
        tile = prepare_tile(image, box)
        inverted = ImageOps.invert(tile)
        geom = TileGeom(
            x=box[0],
            y=box[1],
            w=box[2],
            h=box[3],
            square_side=max(box[2], box[3]),
            prepared_side=tile.size[0],
        )
        for rec in pack:
            family = rec.name.strip() or "ocr"
            label = _engine_label(family)
            for suffix, frame in (("", tile), ("_inv", inverted)):
                _throw_if_cancelled(cancel)
                percent = 8 + int(84 * step / step_total)
                channel = "反色补扫" if suffix else "正图"
                if family not in warmed:
                    _emit_progress(
                        progress,
                        f"正在加载 {label}…",
                        percent=percent,
                        phase="load",
                        tile_count=len(boxes),
                        tile_index=tile_index,
                        step=step,
                        step_total=step_total,
                        engine=family,
                    )
                    warmed.add(family)
                _emit_progress(
                    progress,
                    f"第 {tile_index}/{len(boxes)} 块 · {label} · {channel}",
                    percent=percent,
                    phase="ocr",
                    tile_count=len(boxes),
                    tile_index=tile_index,
                    step=step,
                    step_total=step_total,
                    engine=family,
                )
                _absorb_lines(
                    bag,
                    order,
                    located,
                    as_ocr_lines(rec.engine.recognize(frame)),
                    f"{family}{suffix}",
                    geom,
                )
                step += 1
    tokens = [
        OcrToken(text=text, engines=frozenset(bag[normalize_text(text)]))
        for text in order
    ]
    return tokens, len(boxes), located


def recognize_image(
    image: Image.Image,
    catalog: list[dict[str, str]],
    *,
    recognizer: TileRecognizer | None = None,
    recognizers: Sequence[NamedRecognizer] | None = None,
    db: Any = None,
    use_case: str = "tarkov_keys",
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    pack = resolve_recognizers(
        recognizer=recognizer,
        recognizers=recognizers,
        db=db,
        use_case=use_case,
    )
    _throw_if_cancelled(cancel)
    _emit_progress(progress, "正在准备识别引擎…", percent=4, phase="prepare")
    tokens, tile_count, located = collect_tile_tokens(
        image, pack, progress=progress, cancel=cancel
    )
    _emit_progress(progress, "正在对照钥匙短名…", percent=94, phase="match")
    parsed: list[OcrToken] = []
    for token in tokens:
        for text in parse_tokens(token.text):
            parsed.append(OcrToken(text=text, engines=token.engines))
    cross_check = True
    if db is not None:
        from app.services.ocr.config import load_ocr_config, use_case_cross_check

        cross_check = use_case_cross_check(load_ocr_config(db), use_case)
    matches = match_keys(parsed, catalog, cross_check=cross_check)
    result = {
        "matches": [match.__dict__ for match in matches],
        "tile_count": tile_count,
        "overlay": build_overlay(image.width, image.height, matches, located),
        "engines": [rec.name for rec in pack],
    }
    _emit_progress(progress, "识别完成", percent=100, phase="done")
    return result


def recognize_image_bytes(
    raw: bytes,
    catalog: list[dict[str, str]],
    *,
    recognizer: TileRecognizer | None = None,
    recognizers: Sequence[NamedRecognizer] | None = None,
    db: Any = None,
    use_case: str = "tarkov_keys",
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    return recognize_image(
        load_image(raw),
        catalog,
        recognizer=recognizer,
        recognizers=recognizers,
        db=db,
        use_case=use_case,
        progress=progress,
        cancel=cancel,
    )


def resolve_recognizers(
    *,
    recognizer: TileRecognizer | None = None,
    recognizers: Sequence[NamedRecognizer] | None = None,
    db: Any = None,
    use_case: str = "tarkov_keys",
) -> list[NamedRecognizer]:
    return _resolve_recognizers(
        recognizer, recognizers, db=db, use_case=use_case
    )


def _clamp_percent(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def _engine_label(name: str) -> str:
    from app.services.ocr.catalog import ENGINE_LABELS

    key = (name or "").strip()
    return ENGINE_LABELS.get(key, key or "OCR")


def _emit_progress(
    progress: ProgressFn | None,
    message: str,
    **stats: Any,
) -> None:
    if progress is None:
        return
    progress(message, stats)


def _resolve_recognizers(
    recognizer: TileRecognizer | None,
    recognizers: Sequence[NamedRecognizer] | None,
    *,
    db: Any = None,
    use_case: str = "tarkov_keys",
) -> list[NamedRecognizer]:
    if recognizers:
        pack = [item for item in recognizers if item.name.strip()]
        if pack:
            return pack
    if recognizer is not None:
        return [NamedRecognizer(name="paddle", engine=recognizer)]
    return _default_recognizers(db=db, use_case=use_case)


def _default_recognizers(
    *,
    db: Any = None,
    use_case: str = "tarkov_keys",
) -> list[NamedRecognizer]:
    from app.services.ocr.runtime import named_engines_for

    return named_engines_for(use_case, db=db)


def _absorb_lines(
    bag: dict[str, set[str]],
    order: list[str],
    located: dict[str, LocatedToken],
    lines: list[OcrLine],
    engine: str,
    geom: TileGeom,
) -> None:
    for line in lines:
        source = None
        if line.w >= 2 and line.h >= 2:
            source = map_tile_xywh(geom, line.x, line.y, line.w, line.h)
        for text in parse_tokens(line.text):
            key = normalize_text(text)
            if not key:
                continue
            if key not in bag:
                bag[key] = set()
                order.append(text)
            bag[key].add(engine)
            if source is None:
                continue
            previous = located.get(key)
            area = source[2] * source[3]
            if previous is None or area > previous.width * previous.height:
                located[key] = LocatedToken(
                    text=text,
                    x=source[0],
                    y=source[1],
                    width=source[2],
                    height=source[3],
                )


def build_overlay(
    width: int,
    height: int,
    matches: list[KeyOcrMatch],
    located: dict[str, LocatedToken],
) -> dict[str, Any]:
    boxes: list[dict[str, Any]] = []
    used: set[str] = set()
    for match in matches:
        key = normalize_text(match.ocr_text)
        used.add(key)
        spot = located.get(key)
        if spot is None:
            continue
        boxes.append(
            {
                "x": round(spot.x, 1),
                "y": round(spot.y, 1),
                "width": round(spot.width, 1),
                "height": round(spot.height, 1),
                "label": match.short_name or match.name,
                "item_id": match.id,
                "kind": "hit" if match.confidence == "exact" else "fuzzy",
            }
        )
    misses: list[dict[str, Any]] = []
    for key, spot in located.items():
        if key in used:
            continue
        misses.append(
            {
                "x": round(spot.x, 1),
                "y": round(spot.y, 1),
                "width": round(spot.width, 1),
                "height": round(spot.height, 1),
                "label": spot.text,
                "item_id": "",
                "kind": "miss",
            }
        )
    misses.sort(key=lambda row: row["width"] * row["height"], reverse=True)
    boxes.extend(misses[:OVERLAY_MISS_CAP])
    return {"width": width, "height": height, "boxes": boxes}


def _is_noise(text: str) -> bool:
    key = normalize_text(text)
    if not key or key in KEY_OCR_NOISE:
        return True
    trimmed = text.strip()
    if re.fullmatch(r"\d+%", trimmed):
        return True
    if re.fullmatch(r"\d+/\d+", trimmed):
        return True
    if re.fullmatch(r"\d+x\d+", key, flags=re.I):
        return True
    return False


def _is_short_latin(needle: str) -> bool:
    return bool(_LATIN_TOKEN_RE.fullmatch(needle) and len(needle) < 3)


def _is_numeric(text: str) -> bool:
    return bool(re.fullmatch(r"\d+", normalize_text(text)))


def _is_plain_latin_word(needle: str) -> bool:
    return bool(re.fullmatch(r"[a-z]+", needle) and len(needle) <= 5)


def _is_weak_short(value: str) -> bool:
    key = normalize_text(value)
    return (not key) or len(key) < 2 or key in WEAK_SHORT


def _short_aliases(short_name: str) -> tuple[str, ...]:
    aliases: list[str] = []
    seen: set[str] = set()
    short_key = normalize_text(short_name)
    compact_short = compact_text(short_name)
    for item in (short_key, compact_short, compact_short.replace("key", "")):
        if not item or len(item) < 2 or item in WEAK_SHORT or item in seen:
            continue
        seen.add(item)
        aliases.append(item)
    return tuple(aliases)


def _catalog_entries(keys: list[dict[str, str]]) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []
    for key in keys:
        ident = str(key.get("id") or "").strip()
        if not ident:
            continue
        name = str(key.get("name") or "").strip()
        short_name = str(key.get("short_name") or "").strip()
        name_key = normalize_text(name)
        short_key = normalize_text(short_name)
        if not name_key and not short_key:
            continue
        out.append(
            CatalogEntry(
                id=ident,
                name=name or short_name or ident,
                short_name=short_name,
                icon_link=str(key.get("icon_link") or "").strip(),
                name_key=name_key,
                short_key=short_key,
                compact_name=compact_text(name),
                compact_short=compact_text(short_name),
                short_aliases=_short_aliases(short_name),
            )
        )
    return out


def _alias_hits(entry: CatalogEntry, needle: str, compact: str) -> bool:
    if _is_short_latin(needle):
        return False
    return needle in entry.short_aliases or compact in entry.short_aliases


def _room_key_digits(short_key: str) -> str | None:
    match = _ROOM_KEY_RE.fullmatch(short_key)
    return match.group(2) if match else None


def _allow_room_score(needle: str, entry: CatalogEntry, exact: bool) -> bool:
    room = _room_key_digits(entry.short_key)
    if not room:
        return True
    seen = None
    match = _TOKEN_ROOM_RE.search(needle)
    if match:
        seen = match.group(1)
    if seen and seen != room:
        return False
    if exact:
        return True
    return bool(seen == room and _CJK_RE.search(needle))


def _score_token(token: str, entry: CatalogEntry) -> tuple[int, float, bool]:
    needle = normalize_text(token)
    compact = compact_text(token)
    exact = _alias_hits(entry, needle, compact)
    if entry.name_key and (entry.name_key == needle or entry.compact_name == compact):
        exact = True
    rank_raw = hit_rank(
        token,
        entry.name,
        "" if _is_weak_short(entry.short_name) else entry.short_name,
        *entry.short_aliases,
    )
    rank = (
        rank_raw
        if rank_raw == 0 or (rank_raw == 1 and len(needle) >= 5)
        else 9
    )
    fuzzy = 0.0
    if not _is_numeric(token) and not _is_plain_latin_word(needle):
        if entry.short_key and not _is_weak_short(entry.short_name) and len(needle) >= 4:
            fuzzy = max(
                fuzzy,
                fuzzy_score(entry.short_key, needle),
                fuzzy_score(entry.compact_short, compact),
            )
        if entry.name_key and len(needle) >= 4:
            fuzzy = max(
                fuzzy,
                fuzzy_score(entry.name_key, needle),
                fuzzy_score(entry.compact_name, compact),
            )
    if not _allow_room_score(needle, entry, exact):
        return 9, 0.0, False
    return rank, fuzzy, exact


def _is_misread_dorm_one(
    token: str, entries: list[CatalogEntry], used_ids: set[str]
) -> bool:
    match = _DORM_ONE_RE.fullmatch(normalize_text(token))
    if not match:
        return False
    twin = f"2{match.group(1)}钥匙"
    return any(entry.id in used_ids and entry.short_key == twin for entry in entries)


def _marked_room_fallback(
    token: str, entries: list[CatalogEntry], used_ids: set[str]
) -> CatalogEntry | None:
    needle = normalize_text(token)
    match = _MARKED_ROOM_RE.fullmatch(needle)
    if not match:
        return None
    if not _ROOM_GLYPH_RE.search(match.group(2)):
        return None
    room = match.group(1)
    hits = [
        entry
        for entry in entries
        if entry.id not in used_ids
        and (
            entry.short_key == room
            or entry.short_key == f"{room}钥匙"
            or entry.compact_short == f"{room}钥匙"
            or room in entry.short_aliases
        )
    ]
    return hits[0] if len(hits) == 1 else None


def _collect_lines(*texts: str) -> list[str]:
    lines: list[str] = []
    for blob in texts:
        raw = (blob or "").replace("\r", "\n")
        if not raw.strip():
            continue
        for line in raw.split("\n"):
            cleaned = _USES_RE.sub(" ", line)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                lines.append(cleaned)
    return _join_stacked_cjk(lines)


def _join_stacked_cjk(lines: list[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for index, current in enumerate(lines):
        if skip:
            skip = False
            continue
        nxt = lines[index + 1] if index + 1 < len(lines) else ""
        if _is_single_cjk(current) and _is_single_cjk(nxt):
            out.append(f"{current.strip()}{nxt.strip()}")
            skip = True
            continue
        out.append(current)
    return out


def _is_single_cjk(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff]", (text or "").strip()))
