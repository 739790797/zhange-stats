"""模组配置键值预设：只解析/改顶层标量，尽量留注释。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from app.services.minecraft.pack import merge_properties, parse_properties

PresetStatus = Literal["missing_files", "no_preset", "match", "mismatch"]

PINNABLE_EXTS = frozenset(
    {"properties", "cfg", "json", "yml", "yaml", "conf", "config"}
)
MAX_PINS = 200
MAX_DIRS = 20
MAX_KEY_LEN = 128
MAX_VALUE_LEN = 4096
MAX_PATH_LEN = 256
_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def is_pinnable_filename(name: str) -> bool:
    text = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in text or text.startswith("."):
        return False
    return text.rsplit(".", 1)[-1].lower() in PINNABLE_EXTS


def safe_server_dir_path(raw: str, *, allow_root: bool = False) -> str:
    """服内目录路径；拒绝 ..。默认不允许选服根。"""
    parts = [
        part
        for part in (raw or "").replace("\\", "/").strip().split("/")
        if part and part != "."
    ]
    if any(part == ".." for part in parts):
        return ""
    if not parts:
        return "/" if allow_root else ""
    path = "/" + "/".join(parts)
    if len(path) > MAX_PATH_LEN:
        return ""
    return path


def safe_server_file_path(raw: str) -> str:
    """服内绝对文件路径；拒绝 .. 与服根。"""
    return safe_server_dir_path(raw, allow_root=False)


def path_is_within(path: str, directory: str) -> bool:
    target = safe_server_dir_path(path, allow_root=False)
    base = safe_server_dir_path(directory, allow_root=True)
    if not target or not base:
        return False
    if base == "/":
        return True
    return target == base or target.startswith(f"{base}/")


def path_is_within_any(path: str, directories: list[str]) -> bool:
    return any(path_is_within(path, row) for row in directories)


def normalize_directories(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        path = safe_server_dir_path(str(item or ""), allow_root=False)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
        if len(out) >= MAX_DIRS:
            break
    return out


def pin_directories(pins: list[dict[str, str]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for pin in pins:
        path = pin.get("file") or ""
        parent = path.rsplit("/", 1)[0] or "/"
        if parent not in seen:
            seen.add(parent)
            out.append(parent)
    return out


def pin_format(path: str) -> str:
    text = (path or "").replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in text:
        return ""
    ext = text.rsplit(".", 1)[-1].lower()
    if ext in {"properties", "cfg"}:
        return "properties"
    if ext == "json":
        return "json"
    if ext in {"yml", "yaml", "conf", "config"}:
        return "kv"
    return ""


def scalar_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def parse_scalar_keys(text: str, path: str) -> dict[str, str]:
    kind = pin_format(path)
    if kind == "json":
        return _parse_json_scalars(text)
    if kind == "properties":
        return {
            str(key): str(value)
            for key, value in parse_properties(text).items()
            if str(key)
        }
    if kind == "kv":
        return _parse_kv_scalars(text)
    return {}


def apply_scalar_pins(text: str, path: str, updates: dict[str, str]) -> str:
    clean = {
        str(key).strip(): str(value)
        for key, value in (updates or {}).items()
        if str(key).strip()
    }
    if not clean:
        return text or ""
    kind = pin_format(path)
    if kind == "json":
        return _apply_json_scalars(text, clean)
    if kind == "properties":
        return merge_properties(text, clean)
    if kind == "kv":
        return _merge_kv_lines(text, clean)
    raise ValueError("这种文件不能做预设")


def read_saved_pins(blob: Any, tool_id: str) -> list[dict[str, str]]:
    entry = _tool_blob(blob, tool_id)
    if not entry:
        return []
    raw = entry.get("pins")
    if not isinstance(raw, list):
        return []
    return normalize_pins(raw)


def read_saved_directories(blob: Any, tool_id: str) -> list[str]:
    entry = _tool_blob(blob, tool_id)
    if not entry:
        return []
    return normalize_directories(entry.get("directories"))


def write_saved_pins(
    blob: Any, tool_id: str, pins: list[dict[str, str]]
) -> dict[str, Any]:
    return write_saved_entry(blob, tool_id, pins=pins)


def write_saved_entry(
    blob: Any,
    tool_id: str,
    *,
    pins: list[dict[str, str]] | None = None,
    directories: list[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(blob, dict):
        for key, value in blob.items():
            if str(key) == tool_id:
                continue
            out[str(key)] = value
    next_pins = (
        normalize_pins(pins) if pins is not None else read_saved_pins(blob, tool_id)
    )
    next_dirs = (
        normalize_directories(directories)
        if directories is not None
        else read_saved_directories(blob, tool_id)
    )
    if next_dirs:
        next_pins = [
            row for row in next_pins if path_is_within_any(row["file"], next_dirs)
        ]
    elif directories is not None:
        next_pins = []
    entry: dict[str, Any] = {}
    if next_pins:
        entry["pins"] = next_pins
    if next_dirs:
        entry["directories"] = next_dirs
    if entry:
        out[tool_id] = entry
    return out


def _tool_blob(blob: Any, tool_id: str) -> dict[str, Any] | None:
    if not isinstance(blob, dict):
        return None
    entry = blob.get(tool_id)
    return entry if isinstance(entry, dict) else None


def normalize_pins(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw:
        pin = _normalize_pin_row(row)
        if pin is None:
            continue
        mark = (pin["file"], pin["key"])
        if mark in seen:
            out = [item for item in out if (item["file"], item["key"]) != mark]
        seen.add(mark)
        out.append(pin)
        if len(out) >= MAX_PINS:
            break
    return out


def reconcile_pins(
    *,
    pins: list[dict[str, str]],
    files: dict[str, str | None],
) -> dict[str, Any]:
    """files: 服内绝对路径 → 正文；缺文件用 None。"""
    if not pins:
        return {"status": "no_preset", "diffs": [], "missing_files": []}
    missing: list[str] = []
    diffs: list[dict[str, str]] = []
    seen_missing: set[str] = set()
    parsed_cache: dict[str, dict[str, str]] = {}
    found_any = False
    for pin in pins:
        rel = pin["file"]
        if rel not in files or files[rel] is None:
            if rel not in seen_missing:
                missing.append(rel)
                seen_missing.add(rel)
            diffs.append(
                {
                    "file": rel,
                    "key": pin["key"],
                    "expected": pin["value"],
                    "actual": "",
                }
            )
            continue
        found_any = True
        if rel not in parsed_cache:
            parsed_cache[rel] = parse_scalar_keys(files[rel] or "", rel)
        actual = parsed_cache[rel].get(pin["key"])
        if actual is None or actual != pin["value"]:
            diffs.append(
                {
                    "file": rel,
                    "key": pin["key"],
                    "expected": pin["value"],
                    "actual": actual or "",
                }
            )
    if not found_any:
        status: PresetStatus = "missing_files"
    elif diffs:
        status = "mismatch"
    else:
        status = "match"
    return {
        "status": status,
        "diffs": diffs,
        "missing_files": missing,
    }


def _normalize_pin_row(row: Any) -> dict[str, str] | None:
    if not isinstance(row, dict):
        return None
    rel = safe_server_file_path(str(row.get("file") or ""))
    key = str(row.get("key") or "").strip()
    if not rel or not is_pinnable_filename(rel):
        return None
    if not key or len(key) > MAX_KEY_LEN or not _KEY_RE.match(key):
        return None
    value = row.get("value")
    text = "" if value is None else str(value)
    if len(text) > MAX_VALUE_LEN:
        return None
    if "\n" in text or "\r" in text:
        return None
    return {"file": rel, "key": key, "value": text}


def _parse_json_scalars(text: str) -> dict[str, str]:
    raw = (text or "").lstrip("\ufeff").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        name = str(key).strip()
        if not name or isinstance(value, (dict, list)):
            continue
        out[name] = scalar_str(value)
    return out


def _coerce_json_value(existing: Any, raw: str) -> Any:
    text = str(raw)
    if isinstance(existing, bool):
        return text.strip().lower() in {"true", "1", "yes"}
    if isinstance(existing, int) and not isinstance(existing, bool):
        try:
            return int(text)
        except ValueError:
            return text
    if isinstance(existing, float):
        try:
            return float(text)
        except ValueError:
            return text
    low = text.strip().lower()
    if existing is None:
        if low == "true":
            return True
        if low == "false":
            return False
        if low == "null":
            return None
        try:
            return int(text)
        except ValueError:
            pass
        return text
    return text


def _apply_json_scalars(text: str, updates: dict[str, str]) -> str:
    raw = (text or "").lstrip("\ufeff").strip()
    data: dict[str, Any]
    if not raw:
        data = {}
    else:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("JSON 根须为对象")
        data = parsed
    for key, value in updates.items():
        current = data.get(key)
        if isinstance(current, (dict, list)):
            continue
        data[key] = _coerce_json_value(current, value)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _is_comment(stripped: str) -> bool:
    return not stripped or stripped.startswith("#") or stripped.startswith("//")


def _unquote_kv_value(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    for token in (" #", "\t#", " //"):
        if token in text:
            text = text.split(token, 1)[0].rstrip()
    return text


def _split_kv(stripped: str) -> tuple[str, str, str] | None:
    if stripped.startswith("- "):
        return None
    if ":" in stripped:
        key, _, rest = stripped.partition(":")
        sep = ":"
    elif "=" in stripped:
        key, _, rest = stripped.partition("=")
        sep = "="
    else:
        return None
    name = key.strip()
    if not name or not _KEY_RE.match(name):
        return None
    value = rest.strip()
    if value in {"", "{", "[", "{}", "[]"} or value.startswith("{") or value.startswith("["):
        return None
    return name, sep, _unquote_kv_value(value)


def _parse_kv_scalars(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in (text or "").replace("\ufeff", "").splitlines():
        if raw[:1] in {" ", "\t"}:
            continue
        stripped = raw.strip()
        if _is_comment(stripped):
            continue
        parsed = _split_kv(stripped)
        if parsed is None:
            continue
        name, _sep, value = parsed
        out[name] = value
    return out


def _format_kv_value(value: str) -> str:
    text = str(value)
    if text == "":
        return '""'
    low = text.lower()
    if low in {"true", "false", "null"}:
        return low
    if re.fullmatch(r"-?\d+", text):
        return text
    if any(ch in text for ch in ":#{}[]'\" \t"):
        return json.dumps(text, ensure_ascii=False)
    return text


def _merge_kv_lines(text: str, updates: dict[str, str]) -> str:
    pending = dict(updates)
    lines: list[str] = []
    for raw in (text or "").splitlines():
        if raw[:1] in {" ", "\t"}:
            lines.append(raw)
            continue
        stripped = raw.strip()
        if _is_comment(stripped):
            lines.append(raw)
            continue
        parsed = _split_kv(stripped)
        if parsed is None:
            lines.append(raw)
            continue
        name, sep, _old = parsed
        if name not in pending:
            lines.append(raw)
            continue
        joiner = ": " if sep == ":" else "="
        lines.append(f"{name}{joiner}{_format_kv_value(pending.pop(name))}")
    for key, value in pending.items():
        lines.append(f"{key}: {_format_kv_value(value)}")
    body = "\n".join(lines).rstrip()
    return f"{body}\n" if body else ""
