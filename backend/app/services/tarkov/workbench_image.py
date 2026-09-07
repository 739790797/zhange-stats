"""工作台改装预览图：工厂/裸枪用 dump 静图；自定义组合走 image-gen 代理。

图鉴数据仍只读 json.tarkov.dev dump。出图不是图鉴回源，见 workbench_image_pw。
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import Any, Protocol
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.tarkov import workbench as wb

logger = logging.getLogger(__name__)

IMAGE_GEN_ORIGIN = "https://image-gen.tarkov-changes.com"
_IMAGE_GEN_HOST = "image-gen.tarkov-changes.com"
_CACHE_MAX = 500
_MAX_PAIRS = 80

_cache_lock = threading.Lock()
_image_cache: dict[str, str] = {}
_backend_override: "ImageGenBackend | None" = None


class ImageGenBusy(Exception):
    """已有出图占用浏览器，新请求不要再堵工作线程。"""


class ImageGenBackend(Protocol):
    @property
    def busy(self) -> bool: ...

    @property
    def last_error(self) -> str | None: ...

    def generate(
        self,
        *,
        gun_id: str,
        items: list[dict[str, Any]],
        weapon_name: str,
    ) -> str: ...


def set_image_gen_backend(backend: ImageGenBackend | None) -> None:
    global _backend_override
    _backend_override = backend


def clear_image_cache() -> None:
    with _cache_lock:
        _image_cache.clear()


def accept_generated_image_url(url: str) -> str | None:
    """只接受 image-gen 同源 URL；相对路径补成该站。"""
    text = (url or "").strip()
    if not text:
        return None
    if text.startswith("/") and not text.startswith("//"):
        return IMAGE_GEN_ORIGIN + text
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme in ("http", "https") and host == _IMAGE_GEN_HOST:
        return text
    return None


def _pairs_key(pairs: list[tuple[str, str]]) -> str:
    return ",".join(sorted(f"{slot}:{item}" for slot, item in pairs if slot and item))


def _bp_hex24(text: str) -> str:
    """与 EFTForge 前端 _bpHex24 一致：24 位 hex 实例 id。"""
    mask = 0xFFFFFFFF
    h1, h2, h3 = 0x6B4A1C7F, 0x3E9D5A2B, 0xD1E4C7A9
    for ch in text:
        c = ord(ch)
        h1 = ((h1 ^ c) * 0x9E3779B9) & mask
        h2 = ((h2 ^ c) * 0x85EBCA6B) & mask
        h3 = ((h3 ^ c) * 0xC2B2AE35) & mask
        h1 ^= (h2 >> 13) ^ (h3 >> 7)
        h2 ^= (h1 >> 17) ^ (h3 >> 5)
        h3 ^= (h1 >> 11) ^ (h2 >> 19)
    h1 = (h1 ^ h2 ^ h3) & mask
    h2 = (h2 ^ ((h1 * 0x27D4EB2D) & mask)) & mask
    h3 = (h3 ^ ((h2 * 0x165667B1) & mask)) & mask
    return "".join(f"{v:08x}" for v in (h1, h2, h3))


def ordered_pairs(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    installed = wb._pairs_map(pairs)
    out: list[tuple[str, str]] = []

    def walk(item_id: str) -> None:
        item = index.items.get(item_id)
        if not item:
            return
        for slot in item.slots:
            child_id = installed.get(slot.id, "")
            if not child_id:
                continue
            out.append((slot.id, child_id))
            walk(child_id)

    walk(gun.id)
    return out[:_MAX_PAIRS]


def classify_build(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    pairs: list[tuple[str, str]],
) -> str:
    ordered = ordered_pairs(index, gun, pairs)
    if not ordered:
        return "bare"
    factory = ordered_pairs(index, gun, wb.map_factory_pairs(index, gun.id))
    if _pairs_key(ordered) == _pairs_key(factory):
        return "factory"
    return "custom"


def build_spt_items(
    index: wb.WorkbenchIndex,
    gun: wb.WbItem,
    pairs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """SPT 信封：机匣 hideout + 配件 slotId=nameId（mod_barrel 等）。"""
    gun_instance = _bp_hex24(gun.id + ":root")
    items: list[dict[str, Any]] = [
        {
            "_id": gun_instance,
            "_tpl": gun.id,
            "slotId": "hideout",
            "parentId": "hideout",
        }
    ]
    instance_map: dict[str, str] = {gun.id: gun_instance}
    for slot_id, item_id in ordered_pairs(index, gun, pairs):
        slot = index.slots.get(slot_id)
        if not slot:
            continue
        game_name = (slot.name_id or slot.name or "").strip()
        if not game_name:
            continue
        parent_instance = instance_map.get(slot.parent_item_id)
        if not parent_instance:
            continue
        instance_id = _bp_hex24(parent_instance + ":" + game_name)
        items.append(
            {
                "_id": instance_id,
                "_tpl": item_id,
                "slotId": game_name,
                "parentId": parent_instance,
            }
        )
        instance_map[item_id] = instance_id
    return items


def search_name(gun: wb.WbItem) -> str:
    """出图站检索只要英文；中文 overlay 名点不到结果。"""
    return (gun.name_en or gun.short_name_en or gun.id).strip()


def static_image_url(gun: wb.WbItem, kind: str) -> str | None:
    if kind == "bare":
        return gun.image_link or None
    return gun.preset_image_link or gun.image_link or None


def _cache_get(key: str) -> str | None:
    with _cache_lock:
        return _image_cache.get(key)


def _cache_put(key: str, url: str) -> None:
    with _cache_lock:
        if key in _image_cache:
            _image_cache[key] = url
            return
        if len(_image_cache) >= _CACHE_MAX:
            oldest = next(iter(_image_cache))
            del _image_cache[oldest]
        _image_cache[key] = url


def _active_backend() -> ImageGenBackend:
    if _backend_override is not None:
        return _backend_override
    from app.services.tarkov.workbench_image_pw import patchright_backend

    return patchright_backend()


def image_status() -> dict[str, Any]:
    settings = get_settings()
    if not settings.TARKOV_WORKBENCH_IMAGE_GEN:
        return {
            "enabled": False,
            "busy": False,
            "message": "预览出图已关闭",
        }
    backend = _active_backend()
    return {
        "enabled": True,
        "busy": backend.busy,
        "message": backend.last_error,
    }


def render_build_image(
    db: Session,
    gun_id: str,
    pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    index = wb.load_index(db)
    gun = wb._require_gun(index, gun_id)
    wb.validate_build(index, gun, pairs)
    kind = classify_build(index, gun, pairs)
    static = static_image_url(gun, kind if kind != "custom" else "factory")
    if kind in ("bare", "factory"):
        return {
            "kind": kind,
            "image_url": static,
            "busy": False,
            "message": None,
            "enabled": True,
        }

    settings = get_settings()
    if not settings.TARKOV_WORKBENCH_IMAGE_GEN:
        return {
            "kind": "unavailable",
            "image_url": static,
            "busy": False,
            "message": "预览出图已关闭",
            "enabled": False,
        }

    ordered = ordered_pairs(index, gun, pairs)
    cache_src = json.dumps([gun.id, _pairs_key(ordered)], ensure_ascii=False)
    cache_key = hashlib.sha256(cache_src.encode("utf-8")).hexdigest()[:16]
    cached = _cache_get(cache_key)
    if cached:
        return {
            "kind": "generated",
            "image_url": cached,
            "busy": False,
            "message": None,
            "enabled": True,
        }

    backend = _active_backend()
    items = build_spt_items(index, gun, pairs)
    logger.info("workbench image-gen start gun=%s", gun.id)
    try:
        url = backend.generate(
            gun_id=gun.id,
            items=items,
            weapon_name=search_name(gun),
        )
    except ImageGenBusy:
        return {
            "kind": "unavailable",
            "image_url": static,
            "busy": True,
            "message": None,
            "enabled": True,
        }
    except Exception as exc:
        logger.warning("workbench image-gen failed: %s", exc)
        return {
            "kind": "unavailable",
            "image_url": static,
            "busy": False,
            "message": "改装预览图暂时不可用",
            "enabled": True,
        }
    safe = accept_generated_image_url(str(url or ""))
    if not safe:
        logger.warning("workbench image-gen rejected url=%s", url)
        return {
            "kind": "unavailable",
            "image_url": static,
            "busy": False,
            "message": "改装预览图暂时不可用",
            "enabled": True,
        }
    _cache_put(cache_key, safe)
    return {
        "kind": "generated",
        "image_url": safe,
        "busy": False,
        "message": None,
        "enabled": True,
    }
