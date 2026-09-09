"""局前任务页截图识别：裁任务列表区 + 共享 OCR + 闭集匹配。

引擎由系统配置「文字识别」按场景「塔科夫局前任务」挑选（默认熊猫 OCR）。
权重走任务配置「文字识别模型」，识别时不再现场下载。切块与闭集匹配留在本模块，
不进共享 OCR 层。与钥匙箱共用进程内一把识别锁。
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.ocr.types import NamedEngine, OcrError
from app.services.tarkov.key_ocr import (
    MAX_RECOGNIZE_BYTES,
    as_ocr_lines,
    end_recognize,
    try_begin_recognize,
)

Image.MAX_IMAGE_PIXELS = 20_000_000

logger = logging.getLogger("zhange.ocr")

USE_CASE = "tarkov_raid_prep"
MIN_SOURCE_EDGE = 80
FUZZY_OK = 0.76
LIST_CROP = {"x": 0.1, "y": 0.17, "w": 0.58, "h": 0.78}
PREFERRED_SIZES = ((1920, 1080), (2560, 1440))
UPSCALE_WANT = 2.0
UPSCALE_MAX_EDGE = 1920

_TOKEN_RE = re.compile(r"[0-9a-zA-Z]+|[\u4e00-\u9fff]+")
_COMPACT_RE = re.compile(r"[\s\-_.·•]+")
_SPACE_RE = re.compile(r"[\s\u3000]+")
_PUNCT_RE = re.compile(
    r"[·•・．.。,，、:：;；!！?？\"'“”‘’（）()【】\[\]<>《》\-_—–−_/\\|]+"
)
_ELLIPSIS_RE = re.compile(r"…+")
_PROGRESS_RE = re.compile(r"\d+%")
_PERCENTISH_RE = re.compile(r"[%ea]", re.IGNORECASE)
_LEADING_JUNK_RE = re.compile(r"^[^\u4e00-\u9fffA-Za-z0-9]+")
_DIGIT_ONLY_RE = re.compile(r"^[\d.%／/ea]+$", re.IGNORECASE)
_STATUS_ONLY_RE = re.compile(r"^进行中!?$", re.IGNORECASE)
_STATUS_JUNK_RE = re.compile(r"^[\d.%@/\\[\]TtFf]+$", re.IGNORECASE)
_MAP_ONLY_RE = re.compile(
    r"^(任意地点|中心区|工厂|灯塔|海关|海岸线|储备站|街区|海找玉|海央线)$"
)
_STREETS_TAIL_RE = re.compile(r"科夫街区$")
_MERCHANT_DOT_RE = re.compile(r"^[\u4e00-\u9fff]{1,2}\s*[。．.、]")
_MERCHANT_DOT_STRIP_RE = re.compile(r"^[\u4e00-\u9fff]{1,2}\s*[。．.、]+\s*")
_MERCHANT_LEAD_RE = re.compile(
    r"^[\u4e00-\u9fff]{1}\s+(?=[\u4e00-\u9fff]{1,2}\s*[。．.、])"
)
_HERMIT_RE = re.compile(
    r"^[\u4e00-\u9fff]\s+([\u4e00-\u9fff]\s+[\u4e00-\u9fff])\s*$"
)
_CJK_NAME_RE = re.compile(
    r"[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9\s\-·•\"'“”‘’]{1,48}"
)
_QUOTE_PART_RE = re.compile(r"[\"'“”‘’·•]+(\d+)\s*$")
_PART_TAIL_RE = re.compile(
    r"[\u4e00-\u9fff][\s\-·•\"'“”‘’]{0,4}(\d+)(?:\s*%|\s|$)"
)
_LATIN_TAIL_RE = re.compile(r"\s+[A-Za-z]{1,3}$")
_DASH_SPLIT_RE = re.compile(r"\s*-\s*")
_CATALOG_PART_RE = re.compile(r"part\s*(\d+)", re.IGNORECASE)
_GUESS_PART_RE = re.compile(r'(?:-\s*|[\s"\'“”‘’·•]+)(\d+)\s*$')
_TRAIL_SEP_RE = re.compile(r"[\s\-·•\"'“”‘’]+$")
_EXPLICIT_DASH_PART_RE = re.compile(r"-\s*\d+\s*$")
_EXPLICIT_QUOTE_PART_RE = re.compile(r"[\"'“”‘’]\d+\s*$")
_COMPACT_CJK_DIGIT_RE = re.compile(r"[\u4e00-\u9fff]+\d+$")


class TarkovRaidPrepOcrError(OcrError):
    """局前任务识别错误（OcrError 子类，路由可统一 except OcrError）。"""


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    key: str
    short_key: str
    normalized_key: str
    trader_slug: str
    trader_name: str


@dataclass(frozen=True)
class RaidPrepOcrMatch:
    id: str
    name: str
    ocr_text: str
    trader_slug: str = ""
    trader_name: str = ""


def compact_ocr_text(text: str) -> str:
    """对齐局前 OCR：「医疗隐私-5」对目录「医疗隐私 - Part 5」。"""
    return _COMPACT_RE.sub("", (text or "").strip().lower()).replace("part", "")


def ocr_search_tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text or "")]


def normalize_ocr_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower()
    text = _SPACE_RE.sub("", text)
    text = _PUNCT_RE.sub("", text)
    return _ELLIPSIS_RE.sub("", text)


_OCR_NOISE_EXACT = {
    normalize_ocr_text(item)
    for item in (
        "任务",
        "任务列表",
        "商人",
        "类型",
        "分类",
        "接受",
        "完成",
        "进行中",
        "已完成",
        "失败",
        "可用",
        "锁定",
        "每日",
        "每周",
        "行动任务",
        "角色",
        "藏身处",
        "技能",
        "地图",
        "商人处",
        "目标",
        "奖励",
        "状态",
        "地点",
        "进度",
        "全部",
        "筛选",
        "搜索",
        "主线任务",
        "支线任务",
        "进行中!",
    )
}

_OCR_LINE_TAIL_WORDS = (
    "任意地点",
    "塔科夫街区",
    "塔科夫",
    "海岸线",
    "储备站",
    "海关",
    "工厂",
    "灯塔",
    "街区",
    "进行中!",
    "进行中",
    "已完成",
    "失败",
    "进行",
    "进行:",
    "进行*",
)


def ocr_levenshtein(a: str, b: str) -> int:
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


def ocr_fuzzy_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    dist = ocr_levenshtein(a, b)
    min_len = min(len(a), len(b))
    fuzzy = 1 - dist / max(len(a), len(b))
    if dist <= 1 and min_len >= 2:
        fuzzy = max(fuzzy, 0.82)
    elif dist <= 2 and min_len >= 3:
        fuzzy = max(fuzzy, 0.78)
    elif dist <= 3 and min_len >= 5:
        fuzzy = max(fuzzy, 0.72)
    return fuzzy


def ocr_hit_rank(needle: str, *fields: str) -> int | None:
    compact_q = compact_ocr_text(needle)
    tokens = ocr_search_tokens(needle)
    if not compact_q and not tokens:
        return None
    best: int | None = None
    for field in fields:
        hay = str(field or "")
        if not hay:
            continue
        compact_h = compact_ocr_text(hay)
        lower_h = hay.lower()
        if compact_q and compact_h == compact_q:
            return 0
        if compact_q and compact_h.startswith(compact_q):
            best = 1 if best is None else min(best, 1)
            continue
        if compact_q and compact_q in compact_h:
            ratio = len(compact_q) / max(len(compact_h), 1)
            if len(compact_q) >= 4 or ratio >= 0.55:
                best = 2 if best is None else min(best, 2)
            continue
        if compact_q and compact_q.find(compact_h) >= 0 and len(compact_h) >= 4:
            best = 2 if best is None else min(best, 2)
            continue
        if tokens and all(t in lower_h or t in compact_h for t in tokens):
            best = 3 if best is None else min(best, 3)
    return best


def is_preferred_size(width: int, height: int) -> bool:
    return (width, height) in PREFERRED_SIZES


def is_near_widescreen(width: int, height: int) -> bool:
    if width < 800 or height < 450:
        return False
    ratio = width / height
    return 1.7 <= ratio <= 1.85


def list_crop_rect(width: int, height: int) -> tuple[int, int, int, int]:
    ratio = width / max(height, 1)
    crop_h = float(LIST_CROP["h"])
    if ratio < 1.75:
        crop_h = min(0.84, crop_h + (1.75 - ratio) * 0.28)
    x = round(width * LIST_CROP["x"])
    y = round(height * LIST_CROP["y"])
    w = max(1, round(width * LIST_CROP["w"]))
    h = max(1, round(height * crop_h))
    return x, y, w, h


def crop_list_region(image: Image.Image) -> Image.Image:
    x, y, w, h = list_crop_rect(image.width, image.height)
    right = min(image.width, x + w)
    bottom = min(image.height, y + h)
    return image.convert("RGB").crop((x, y, right, bottom))


def maybe_upscale(image: Image.Image) -> Image.Image:
    width, height = image.size
    edge = max(width, height)
    if edge <= 0:
        return image
    scale = (
        UPSCALE_WANT
        if edge * UPSCALE_WANT <= UPSCALE_MAX_EDGE
        else UPSCALE_MAX_EDGE / edge
    )
    if scale <= 1.01:
        return image
    next_w = max(1, int(width * scale))
    next_h = max(1, int(height * scale))
    return image.resize((next_w, next_h), Image.Resampling.LANCZOS)


def load_image(raw: bytes) -> Image.Image:
    if not raw:
        raise TarkovRaidPrepOcrError("请粘贴截图")
    if len(raw) > MAX_RECOGNIZE_BYTES:
        raise TarkovRaidPrepOcrError("图片过大，请裁切任务页后再试")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except UnidentifiedImageError as exc:
        raise TarkovRaidPrepOcrError("无法读取截图") from exc
    except OSError as exc:
        raise TarkovRaidPrepOcrError("无法读取截图") from exc
    image = image.convert("RGB")
    width, height = image.size
    if width < MIN_SOURCE_EDGE or height < MIN_SOURCE_EDGE:
        raise TarkovRaidPrepOcrError("图片过小，请使用游戏内任务页截图")
    return image


def catalog_from_raid_prep(items: Sequence[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("id") or "").strip()
        if not task_id:
            continue
        out.append(
            {
                "id": task_id,
                "name": str(row.get("name") or "").strip(),
                "normalized_name": str(row.get("normalized_name") or "").strip(),
                "trader_slug": str(row.get("trader_slug") or "").strip(),
                "trader_name": str(row.get("trader_name") or "").strip(),
            }
        )
    return out


def ocr_catalog_short_name(name: str) -> str:
    head = _DASH_SPLIT_RE.split(name or "", maxsplit=1)[0].strip()
    return normalize_ocr_text(head)


def ocr_catalog_part_number(name: str) -> str | None:
    match = _CATALOG_PART_RE.search(name or "")
    return match.group(1) if match else None


def ocr_guess_part_info(name_guess: str) -> tuple[str, str | None]:
    trimmed = (name_guess or "").strip()
    part_match = _GUESS_PART_RE.search(trimmed)
    part = part_match.group(1) if part_match else None
    base = trimmed
    if part_match:
        base = trimmed[: part_match.start()]
        base = _TRAIL_SEP_RE.sub("", base)
    base = _LEADING_JUNK_RE.sub("", base).strip()
    return normalize_ocr_text(base), part


def strip_merchant_prefix(text: str) -> str:
    out = text
    while _MERCHANT_DOT_RE.search(out):
        out = _MERCHANT_DOT_STRIP_RE.sub("", out)
    out = _MERCHANT_LEAD_RE.sub("", out)
    while _MERCHANT_DOT_RE.search(out):
        out = _MERCHANT_DOT_STRIP_RE.sub("", out)
    out = _HERMIT_RE.sub(r"\1", out)
    return out.strip()


def extract_task_name_from_ocr_line(line: str) -> str:
    text = re.sub(r"\s+", " ", line or "").strip()
    text = _PROGRESS_RE.sub(" ", text)
    text = _PERCENTISH_RE.sub(" ", text)
    for word in _OCR_LINE_TAIL_WORDS:
        idx = text.find(word)
        if idx > 2:
            text = text[:idx].strip()
    text = _LEADING_JUNK_RE.sub("", text)
    text = strip_merchant_prefix(text)
    match = _CJK_NAME_RE.search(text)
    if match:
        text = re.sub(r"\s+", " ", match.group(0)).strip()
    text = _QUOTE_PART_RE.sub(r" - \1", text)
    if not re.search(r"\d", text):
        part_tail = _PART_TAIL_RE.search(line or "")
        if part_tail:
            text = f"{_TRAIL_SEP_RE.sub('', text)} - {part_tail.group(1)}"
    text = _LATIN_TAIL_RE.sub("", text).strip()
    return text


def is_likely_location_or_status_line(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return True
    if _STATUS_ONLY_RE.match(raw):
        return True
    if _STATUS_JUNK_RE.match(raw):
        return True
    if _MAP_ONLY_RE.match(raw):
        return True
    if _STREETS_TAIL_RE.search(raw):
        return True
    if raw == "塔科夫街区":
        return True
    if len(raw) <= 2 and not re.match(r"^[\u4e00-\u9fff]{2,}$", raw):
        return True
    return False


def parse_ocr_task_lines(text: str) -> list[str]:
    raw_lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in (text or "").replace("\r", "\n").split("\n")
    ]
    out: list[str] = []
    seen: set[str] = set()
    for line in raw_lines:
        if not line:
            continue
        cleaned = extract_task_name_from_ocr_line(line)
        if not cleaned:
            continue
        if is_likely_location_or_status_line(cleaned):
            continue
        key = normalize_ocr_text(cleaned)
        if not key or key in seen:
            continue
        if key in _OCR_NOISE_EXACT:
            continue
        if len(key) < 2:
            continue
        if _DIGIT_ONLY_RE.match(cleaned):
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def merge_ocr_raw_texts(*texts: str) -> list[str]:
    return parse_ocr_task_lines("\n".join(item for item in texts if item))


def _is_suffix_fragment(guess_base: str, catalog_short: str) -> bool:
    return (
        catalog_short.endswith(guess_base)
        and not catalog_short.startswith(guess_base)
        and len(guess_base) < len(catalog_short) * 0.75
    )


def _has_explicit_part_suffix(name_guess: str) -> bool:
    trimmed = name_guess.strip()
    if _EXPLICIT_DASH_PART_RE.search(trimmed) or _EXPLICIT_QUOTE_PART_RE.search(
        trimmed
    ):
        return True
    compact = normalize_ocr_text(trimmed)
    return bool(_COMPACT_CJK_DIGIT_RE.search(compact) and len(compact) >= 3)


def _score_part_number_match(name_guess: str, entry_name: str) -> float:
    guess_base, guess_part = ocr_guess_part_info(name_guess)
    part = ocr_catalog_part_number(entry_name)
    if not guess_part or not part or guess_part != part or not guess_base:
        return 0.0
    best = 0.0
    compact_base = re.sub(r"\d+.*$", "", compact_ocr_text(entry_name))
    for cat_base in filter(None, (ocr_catalog_short_name(entry_name), compact_base)):
        if _is_suffix_fragment(guess_base, cat_base):
            continue
        if cat_base.startswith(guess_base) and len(guess_base) >= 1:
            best = max(best, 0.55 + (len(guess_base) / max(len(cat_base), 1)) * 0.35)
        best = max(best, ocr_fuzzy_score(cat_base, guess_base))
    return best


def _score_line_against_entry(
    name_guess: str,
    needle_key: str,
    entry: CatalogEntry,
) -> tuple[int, float]:
    rank = ocr_hit_rank(name_guess, entry.name, entry.normalized_key)
    fuzzy = 0.0
    for catalog_key in filter(None, (entry.key, entry.short_key)):
        fuzzy = max(fuzzy, ocr_fuzzy_score(catalog_key, needle_key))
    fuzzy = max(fuzzy, _score_part_number_match(name_guess, entry.name))
    return (rank if rank is not None else 9, fuzzy)


def _try_weak_part_fallback(
    name_guess: str,
    entries: list[CatalogEntry],
    used_ids: set[str],
) -> CatalogEntry | None:
    if not _has_explicit_part_suffix(name_guess):
        return None
    guess_base, guess_part = ocr_guess_part_info(name_guess)
    if not guess_part or not guess_base or len(guess_base) < 2:
        return None
    candidates: list[CatalogEntry] = []
    for entry in entries:
        if entry.id in used_ids:
            continue
        if ocr_catalog_part_number(entry.name) != guess_part:
            continue
        short_key = entry.short_key
        if not short_key or len(short_key) > 3:
            continue
        if _is_suffix_fragment(guess_base, short_key):
            continue
        candidates.append(entry)
    return candidates[0] if len(candidates) == 1 else None


def _catalog_entries(tasks: Sequence[dict[str, str]]) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []
    for task in tasks:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            continue
        name = str(task.get("name") or "").strip()
        key = normalize_ocr_text(name)
        normalized_key = normalize_ocr_text(str(task.get("normalized_name") or ""))
        if not key and not normalized_key:
            continue
        out.append(
            CatalogEntry(
                id=task_id,
                name=name or str(task.get("normalized_name") or "") or task_id,
                key=key,
                short_key=ocr_catalog_short_name(name),
                normalized_key=normalized_key,
                trader_slug=str(task.get("trader_slug") or "").strip(),
                trader_name=str(task.get("trader_name") or "").strip(),
            )
        )
    return out


def match_raid_prep_tasks(
    lines: Sequence[str],
    catalog: Sequence[dict[str, str]],
) -> list[RaidPrepOcrMatch]:
    """宁缺毋滥：优先 compact 命中；OCR 误字时用模糊匹配，歧义行丢弃。"""
    entries = _catalog_entries(catalog)
    if not entries:
        return []
    matches: list[RaidPrepOcrMatch] = []
    used_ids: set[str] = set()

    def push(entry: CatalogEntry, ocr_text: str) -> bool:
        if entry.id in used_ids:
            return False
        used_ids.add(entry.id)
        matches.append(
            RaidPrepOcrMatch(
                id=entry.id,
                name=entry.name,
                ocr_text=ocr_text,
                trader_slug=entry.trader_slug,
                trader_name=entry.trader_name,
            )
        )
        return True

    for line in lines:
        name_guess = extract_task_name_from_ocr_line(line)
        if not name_guess:
            continue
        needle_key = normalize_ocr_text(name_guess)
        if not needle_key or len(needle_key) < 2:
            continue
        scored: list[tuple[CatalogEntry, int, float]] = []
        for entry in entries:
            if entry.id in used_ids:
                continue
            rank, fuzzy = _score_line_against_entry(name_guess, needle_key, entry)
            if rank <= 3 or fuzzy >= FUZZY_OK:
                scored.append((entry, rank, fuzzy))
        scored.sort(key=lambda item: (item[1], -item[2]))
        if not scored:
            weak = _try_weak_part_fallback(name_guess, entries, used_ids)
            if weak:
                push(weak, name_guess)
            continue
        best_entry, best_rank, best_fuzzy = scored[0]
        if len(scored) > 1:
            _second_entry, second_rank, second_fuzzy = scored[1]
            if (
                best_rank == second_rank
                and best_rank >= 2
                and abs(best_fuzzy - second_fuzzy) < 0.06
            ):
                weak = _try_weak_part_fallback(name_guess, entries, used_ids)
                if weak:
                    push(weak, name_guess)
                continue
        if best_rank > 3 and best_fuzzy < FUZZY_OK:
            weak = _try_weak_part_fallback(name_guess, entries, used_ids)
            if weak:
                push(weak, name_guess)
            continue
        push(best_entry, name_guess)
    return matches


def _collect_ocr_texts(
    image: Image.Image,
    engines: Sequence[NamedEngine],
) -> list[str]:
    inverted = ImageOps.invert(image.convert("RGB"))
    texts: list[str] = []
    last_fatal: OcrError | None = None
    for rec in engines:
        for src in (image, inverted):
            try:
                raw = rec.engine.recognize(src)
            except OcrError as exc:
                if exc.status_code >= 500:
                    last_fatal = exc
                    logger.exception("raid-prep ocr engine %s failed", rec.name)
                    continue
                logger.exception("raid-prep ocr engine %s failed", rec.name)
                continue
            except Exception:  # noqa: BLE001
                logger.exception("raid-prep ocr engine %s failed", rec.name)
                continue
            texts.extend(line.text for line in as_ocr_lines(raw) if line.text)
    if not texts and last_fatal is not None:
        raise last_fatal
    return texts


def resolve_recognizers(
    *,
    recognizers: Sequence[NamedEngine] | None = None,
    db: Any = None,
) -> list[NamedEngine]:
    if recognizers:
        pack = [item for item in recognizers if item.name.strip()]
        if pack:
            return pack
    from app.services.ocr.runtime import named_engines_for

    return named_engines_for(USE_CASE, db=db)


def empty_result(
    *,
    width: int,
    height: int,
    engines: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "matches": [],
        "width": width,
        "height": height,
        "widescreen": is_near_widescreen(width, height),
        "preferred_size": is_preferred_size(width, height),
        "engines": list(engines),
    }


def recognize_image(
    image: Image.Image,
    catalog: Sequence[dict[str, str]],
    *,
    recognizers: Sequence[NamedEngine] | None = None,
    db: Any = None,
) -> dict[str, Any]:
    width, height = image.size
    widescreen = is_near_widescreen(width, height)
    if not widescreen:
        return empty_result(width=width, height=height)
    pack = resolve_recognizers(recognizers=recognizers, db=db)
    if not catalog:
        return {
            "matches": [],
            "width": width,
            "height": height,
            "widescreen": True,
            "preferred_size": is_preferred_size(width, height),
            "engines": [rec.name for rec in pack],
        }
    crop = maybe_upscale(crop_list_region(image))
    texts = _collect_ocr_texts(crop, pack)
    lines = merge_ocr_raw_texts(*texts)
    matches = match_raid_prep_tasks(lines, catalog)
    return {
        "matches": [
            {
                "id": row.id,
                "name": row.name,
                "ocr_text": row.ocr_text,
                "trader_slug": row.trader_slug,
                "trader_name": row.trader_name,
            }
            for row in matches
        ],
        "width": width,
        "height": height,
        "widescreen": True,
        "preferred_size": is_preferred_size(width, height),
        "engines": [rec.name for rec in pack],
    }


def recognize_image_bytes(
    raw: bytes,
    catalog: Sequence[dict[str, str]],
    *,
    recognizers: Sequence[NamedEngine] | None = None,
    db: Any = None,
) -> dict[str, Any]:
    return recognize_image(
        load_image(raw),
        catalog,
        recognizers=recognizers,
        db=db,
    )


__all__ = [
    "MAX_RECOGNIZE_BYTES",
    "USE_CASE",
    "TarkovRaidPrepOcrError",
    "catalog_from_raid_prep",
    "compact_ocr_text",
    "crop_list_region",
    "empty_result",
    "end_recognize",
    "extract_task_name_from_ocr_line",
    "is_likely_location_or_status_line",
    "is_near_widescreen",
    "is_preferred_size",
    "list_crop_rect",
    "load_image",
    "match_raid_prep_tasks",
    "merge_ocr_raw_texts",
    "normalize_ocr_text",
    "ocr_catalog_short_name",
    "ocr_guess_part_info",
    "ocr_hit_rank",
    "parse_ocr_task_lines",
    "recognize_image",
    "recognize_image_bytes",
    "resolve_recognizers",
    "try_begin_recognize",
]
