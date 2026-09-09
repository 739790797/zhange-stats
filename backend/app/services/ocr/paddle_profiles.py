"""熊猫 OCR 档位：从 RapidOCR 包内 default_models.yaml 摊开 onnxruntime 成套组合。

v6 各语种共用同一份权重，只列 tiny/small/medium，不按语种重复。
v4/v5 识别语种若没有对应检测，则配中英检测。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_PADDLE_PROFILE = "v5_server"

_SIZES = ("tiny", "small", "medium", "mobile", "server")
_SIZE_RANK = {name: index for index, name in enumerate(("server", "medium", "small", "mobile", "tiny"))}
_VERSION_RANK = {
    "PP-OCRv6": 0,
    "PP-OCRv5": 1,
    "PP-OCRv4": 2,
}
PROFILE_ALIASES = {
    "v5": "v5_server",
    "ppocrv5": "v5_server",
    "pp-ocrv5-server": "v5_server",
    "v6": "v6_small",
    "v6small": "v6_small",
    "v6tiny": "v6_tiny",
    "v6medium": "v6_medium",
}


@dataclass(frozen=True)
class PaddleProfile:
    id: str
    ocr_version: str
    model_type: str
    det_lang: str
    rec_lang: str
    label: str
    group: str


def _short_version(ocr_version: str) -> str:
    digits = "".join(ch for ch in (ocr_version or "") if ch.isdigit())
    return f"v{digits}" if digits else "v"


def _parse_weight_key(key: str) -> tuple[str, str, str] | None:
    parts = str(key or "").rsplit("_", 2)
    if len(parts) != 3:
        return None
    prefix, role, size = parts
    role = role.lower()
    size = size.lower()
    if role not in ("det", "rec") or size not in _SIZES:
        return None
    lang = prefix
    cut = lang.lower().find("_pp-ocr")
    if cut < 0:
        cut = lang.lower().find("_ppocr")
    if cut >= 0:
        lang = lang[:cut]
    lang = lang.strip().lower()
    if not lang:
        return None
    return lang, role, size


def _index_task(raw: Any) -> dict[tuple[str, str], str]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[tuple[str, str], str] = {}
    for key in raw:
        parsed = _parse_weight_key(str(key))
        if parsed is None:
            continue
        lang, role, size = parsed
        if role not in ("det", "rec"):
            continue
        out[(lang, size)] = str(key)
    return out


def _profile_id(ocr_version: str, size: str, rec_lang: str) -> str:
    short = _short_version(ocr_version)
    if rec_lang in ("ch", "multi"):
        return f"{short}_{size}"
    return f"{short}_{size}_{rec_lang}"


def _build_profile(
    *,
    ocr_version: str,
    size: str,
    det_lang: str,
    rec_lang: str,
    rec_key: str,
) -> PaddleProfile:
    profile_id = _profile_id(ocr_version, size, rec_lang)
    native = (rec_key or "").strip()
    return PaddleProfile(
        id=profile_id,
        ocr_version=ocr_version,
        model_type=size,
        det_lang=det_lang,
        rec_lang=rec_lang,
        label=native or profile_id,
        group=ocr_version,
    )


def parse_onnx_paddle_profiles(tree: Mapping[str, Any] | None) -> list[PaddleProfile]:
    """从 RapidOCR default_models 结构列出可加载的 det+rec 套装。只读 onnxruntime。"""
    root = tree.get("onnxruntime") if isinstance(tree, Mapping) else None
    if not isinstance(root, Mapping):
        return []
    found: dict[str, PaddleProfile] = {}
    for version, tasks in root.items():
        if not isinstance(tasks, Mapping):
            continue
        version_s = str(version)
        det_map = _index_task(tasks.get("det"))
        rec_map = _index_task(tasks.get("rec"))
        if version_s == "PP-OCRv6":
            sizes = {size for _lang, size in det_map} | {size for _lang, size in rec_map}
            for size in sizes:
                rec_key = rec_map.get(("multi", size), "")
                if ("multi", size) in det_map and rec_key:
                    row = _build_profile(
                        ocr_version=version_s,
                        size=size,
                        det_lang="ch",
                        rec_lang="ch",
                        rec_key=rec_key,
                    )
                    found[row.id] = row
            continue
        for lang, size in rec_map:
            if (lang, size) in det_map:
                det_lang = lang
            elif ("ch", size) in det_map:
                det_lang = "ch"
            else:
                continue
            row = _build_profile(
                ocr_version=version_s,
                size=size,
                det_lang=det_lang,
                rec_lang=lang,
                rec_key=rec_map[(lang, size)],
            )
            found[row.id] = row
    rows = list(found.values())
    rows.sort(
        key=lambda row: (
            _VERSION_RANK.get(row.ocr_version, 99),
            _SIZE_RANK.get(row.model_type, 99),
            0 if row.rec_lang in ("ch", "multi") else 1,
            row.rec_lang,
        )
    )
    return rows


def load_rapidocr_model_tree() -> dict[str, Any]:
    try:
        from omegaconf import OmegaConf
        from rapidocr.inference_engine.base import InferSession
    except ImportError:
        return {}
    try:
        raw = OmegaConf.to_container(InferSession.model_info, resolve=True)
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


_FALLBACK_PROFILES = (
    PaddleProfile(
        id="v5_server",
        ocr_version="PP-OCRv5",
        model_type="server",
        det_lang="ch",
        rec_lang="ch",
        label="ch_PP-OCRv5_rec_server",
        group="PP-OCRv5",
    ),
    PaddleProfile(
        id="v6_small",
        ocr_version="PP-OCRv6",
        model_type="small",
        det_lang="ch",
        rec_lang="ch",
        label="multi_PP-OCRv6_rec_small",
        group="PP-OCRv6",
    ),
    PaddleProfile(
        id="v6_medium",
        ocr_version="PP-OCRv6",
        model_type="medium",
        det_lang="ch",
        rec_lang="ch",
        label="multi_PP-OCRv6_rec_medium",
        group="PP-OCRv6",
    ),
)


def list_paddle_profiles() -> list[PaddleProfile]:
    parsed = parse_onnx_paddle_profiles(load_rapidocr_model_tree())
    return parsed or list(_FALLBACK_PROFILES)


def paddle_profile_by_id(profile_id: str) -> PaddleProfile | None:
    wanted = (profile_id or "").strip()
    for row in list_paddle_profiles():
        if row.id == wanted:
            return row
    return None


def normalize_paddle_profile(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("-", "_")
    raw = PROFILE_ALIASES.get(raw, raw)
    rows = list_paddle_profiles()
    ids = {row.id for row in rows}
    if raw in ids:
        return raw
    if DEFAULT_PADDLE_PROFILE in ids:
        return DEFAULT_PADDLE_PROFILE
    if rows:
        return rows[0].id
    return DEFAULT_PADDLE_PROFILE


def paddle_rapidocr_enums(profile: str) -> dict[str, Any]:
    from rapidocr import LangDet, LangRec, ModelType, OCRVersion

    meta = paddle_profile_by_id(normalize_paddle_profile(profile))
    if meta is None:
        meta = _FALLBACK_PROFILES[0]
    version = _enum_by_value(OCRVersion, meta.ocr_version) or _enum_by_value(
        OCRVersion, meta.ocr_version.replace("-", "")
    )
    model_type = _enum_by_value(ModelType, meta.model_type)
    if version is None or model_type is None:
        raise ValueError(f"unsupported paddle profile {meta.id}")
    return {
        "ocr_version": version,
        "model_type": model_type,
        "det_lang": _coerce_lang(LangDet, meta.det_lang, LangDet.CH),
        "rec_lang": _coerce_lang(LangRec, meta.rec_lang, LangRec.CH),
    }


def _enum_by_value(enum_cls: Any, value: str) -> Any | None:
    wanted = (value or "").strip().lower().replace("-", "")
    for item in enum_cls:
        token = str(item.value).strip().lower().replace("-", "")
        if token == wanted or item.name.lower().replace("_", "") == wanted:
            return item
    return None


def _coerce_lang(enum_cls: Any, value: str, default: Any) -> Any:
    raw = (value or "").strip().lower()
    for item in enum_cls:
        if str(item.value).lower() == raw or item.name.lower() == raw:
            return item
    return default
