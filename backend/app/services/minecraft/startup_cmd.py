"""把服内文件和用户选择拼成一条 Pelican 启动指令。

-jar 核心：``java [JVM] -jar 文件名 [nogui|--nogui]``
Forge 1.17+ / NeoForge：``java @user_jvm_args.txt @…/unix_args.txt nogui``
"""

from __future__ import annotations

import re
from typing import Any, Literal

Launch = Literal["jar", "args"]
Kind = Literal["mod", "plugin", "hybrid"]

LOADER_LABELS = {
    "neoforge": "NeoForge",
    "forge": "Forge",
    "fabric": "Fabric",
    "quilt": "Quilt",
    "paper": "Paper",
    "purpur": "Purpur",
    "vanilla": "原版",
}

LOADER_CHOICES = ("neoforge", "forge", "fabric", "quilt", "paper", "purpur", "vanilla")

_HEAP_RE = re.compile(r"-Xm[sx]\S+", re.I)
_JAVA_MAJOR_RE = re.compile(r"java[_-]?(\d+)", re.I)
_UNIX_VER_RE = re.compile(r"/([^/]+)/unix_args\.txt$", re.I)


def loader_label(loader: str, loader_version: str = "", mc_version: str = "") -> str:
    name = LOADER_LABELS.get(loader, loader or "未识别")
    bits = [name]
    if loader_version:
        bits.append(loader_version)
    text = " ".join(bits)
    if mc_version:
        text = f"{text} · Minecraft {mc_version}"
    return text


def parse_mc(mc: str) -> tuple[int, int, int]:
    nums: list[int] = []
    for part in (mc or "").split(".")[:3]:
        match = re.match(r"(\d+)", part)
        nums.append(int(match.group(1)) if match else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def mc_from_neoforge(version: str) -> str:
    match = re.match(r"(\d+)\.(\d+)", version or "")
    if not match:
        return ""
    major, minor = int(match.group(1)), int(match.group(2))
    if major >= 25:
        return f"{major}.{minor}" if minor else str(major)
    if minor == 0:
        return f"1.{major}"
    return f"1.{major}.{minor}"


def java_major_for_mc(mc: str) -> int:
    major, minor, patch = parse_mc(mc)
    if major >= 25:
        return 21
    if major == 1 and (minor > 20 or (minor == 20 and patch >= 5)):
        return 21
    if major == 1 and minor >= 18:
        return 17
    if major == 1 and minor >= 17:
        return 16
    return 8


def image_java_major(image: str) -> int | None:
    match = _JAVA_MAJOR_RE.search(image or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def suggest_image(images: list[str], major: int) -> str:
    for image in images:
        if image_java_major(image) == major:
            return image
    return images[0] if images else ""


def java_warning(image: str, expected: int) -> str:
    found = image_java_major(image)
    if found and expected and found != expected:
        return f"这个核心通常用 Java {expected}，当前镜像是 Java {found}"
    return ""


def suggest_heap_flags(limit_mb: int) -> str:
    """按面板内存限额给初始堆，留出余量。8G 容器得到 -Xms6G -Xmx6G。"""
    if limit_mb <= 0:
        return "-Xms2G -Xmx2G"
    reserve = 2048 if limit_mb >= 4096 else 1024
    heap = max(1024, int(limit_mb) - reserve)
    if heap >= 1024:
        return f"-Xms{heap // 1024}G -Xmx{heap // 1024}G"
    return f"-Xms{heap}M -Xmx{heap}M"


def heap_flags_from_text(text: str) -> str:
    found = _HEAP_RE.findall(text or "")
    out: list[str] = []
    seen: set[str] = set()
    for token in found:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return " ".join(out)


def build_jar_command(jvm: str, jar: str, server_args: str) -> str:
    filename = (jar or "").strip()
    if not filename or filename.startswith("@"):
        return ""
    parts = ["java"]
    flags = " ".join((jvm or "").split())
    if flags:
        parts.append(flags)
    parts.extend(["-jar", filename])
    args = " ".join((server_args or "").split())
    if args:
        parts.append(args)
    return " ".join(parts)


def build_args_command(unix_args: str) -> str:
    path = (unix_args or "").strip().lstrip("/")
    if not path.endswith("unix_args.txt"):
        return ""
    return f"java @user_jvm_args.txt @{path} nogui"


def assess_command(
    launch: str,
    *,
    jar: str,
    jar_exists: bool,
    unix_args: str,
    unix_exists: bool,
) -> tuple[bool, str]:
    if launch == "args":
        if not unix_args:
            return False, "没有找到 unix_args.txt"
        if not unix_exists:
            return False, "unix_args.txt 不在服目录里"
        return True, ""
    filename = (jar or "").strip()
    if not filename:
        return False, "还没有服务端 jar"
    if not jar_exists:
        return False, "服务端 jar 还不在服目录里"
    return True, ""


def parse_command(command: str) -> dict[str, str]:
    text = " ".join((command or "").split())
    if "@user_jvm_args.txt" in text and "unix_args.txt" in text:
        match = re.search(r"@(libraries/\S*?unix_args\.txt)", text)
        return {
            "launch": "args",
            "jvm": "",
            "jar": "",
            "unix_args": match.group(1) if match else "",
            "server_args": "nogui",
        }
    if "-jar" not in text:
        return {"launch": "", "jvm": "", "jar": "", "unix_args": "", "server_args": ""}
    before, _, after = text.partition("-jar")
    jvm = re.sub(r"^\s*java\s*", "", before).strip()
    bits = after.split()
    return {
        "launch": "jar",
        "jvm": jvm,
        "jar": bits[0] if bits else "",
        "unix_args": "",
        "server_args": " ".join(bits[1:]),
    }


def _version_from_unix(path: str) -> str:
    match = _UNIX_VER_RE.search((path or "").replace("\\", "/"))
    return match.group(1) if match else ""


def _family(name: str) -> str:
    low = (name or "").lower()
    for key in (
        "arclight",
        "youer",
        "mohist",
        "banner",
        "purpur",
        "paper",
        "quilt",
        "fabric",
        "neoforge",
        "forge",
    ):
        if key in low:
            return key
    return ""


def _jar_names(root_names: list[str]) -> list[str]:
    out: list[str] = []
    for name in root_names:
        low = name.lower()
        if not low.endswith(".jar"):
            continue
        if "installer" in low:
            continue
        out.append(name)
    return out


def _pick_jar(jars: list[str], family: str, loader: str = "") -> str:
    hits = [name for name in jars if _family(name) == family]
    if loader:
        marked = [name for name in hits if loader in name.lower()]
        if marked:
            return marked[0]
    return hits[0] if hits else ""


def detect_install(root_names: list[str], unix_paths: list[str]) -> dict[str, Any]:
    """从根目录文件名和 unix_args 路径认出整合包自带的核心。"""
    jars = _jar_names(root_names)
    neo = [path for path in unix_paths if "/neoforge/" in path.replace("\\", "/").lower()]
    forge = [
        path
        for path in unix_paths
        if "/minecraftforge/forge/" in path.replace("\\", "/").lower()
    ]
    if neo:
        path = sorted(neo)[-1]
        version = _version_from_unix(path)
        return {
            "loader": "neoforge",
            "loader_version": version,
            "mc_version": mc_from_neoforge(version),
            "launch": "args",
            "unix_args": path.lstrip("/"),
            "jar": "",
            "family": "neoforge",
            "kind": "mod",
            "server_args": "nogui",
            "jars": jars,
        }
    if forge:
        path = sorted(forge)[-1]
        folder = _version_from_unix(path)
        mc, _, forge_ver = folder.partition("-")
        modern = True
        major, minor, _patch = parse_mc(mc)
        if major == 1 and minor < 17:
            modern = False
        return {
            "loader": "forge",
            "loader_version": forge_ver,
            "mc_version": mc,
            "launch": "args" if modern else "jar",
            "unix_args": path.lstrip("/") if modern else "",
            "jar": "",
            "family": "forge",
            "kind": "mod",
            "server_args": "nogui",
            "jars": jars,
        }

    order = (
        "arclight",
        "youer",
        "mohist",
        "banner",
        "purpur",
        "paper",
        "quilt",
        "fabric",
        "neoforge",
        "forge",
    )
    for family in order:
        jar = _pick_jar(jars, family)
        if not jar:
            continue
        loader = family
        if family == "arclight":
            low = jar.lower()
            if "fabric" in low:
                loader = "fabric"
            elif "neoforge" not in low and re.search(r"(?<!neo)forge", low):
                loader = "forge"
            else:
                loader = "neoforge"
        kind: Kind = "mod"
        server_args = "nogui"
        if family in {"paper", "purpur"}:
            kind = "plugin"
            server_args = "--nogui"
            loader = family
        elif family in {"arclight", "youer", "mohist", "banner"}:
            kind = "hybrid"
        return {
            "loader": loader,
            "loader_version": "",
            "mc_version": "",
            "launch": "jar",
            "unix_args": "",
            "jar": jar,
            "family": family,
            "kind": kind,
            "server_args": server_args,
            "jars": jars,
        }
    vanilla = next((name for name in jars if name.lower() == "server.jar"), "")
    if vanilla:
        return {
            "loader": "vanilla",
            "loader_version": "",
            "mc_version": "",
            "launch": "jar",
            "unix_args": "",
            "jar": vanilla,
            "family": "vanilla",
            "kind": "mod",
            "server_args": "nogui",
            "jars": jars,
        }
    return {
        "loader": "",
        "loader_version": "",
        "mc_version": "",
        "launch": "jar",
        "unix_args": "",
        "jar": "",
        "family": "",
        "kind": "mod",
        "server_args": "nogui",
        "jars": jars,
    }


_EXTRAS: dict[str, list[dict[str, str]]] = {
    "neoforge": [
        {"id": "arclight", "label": "Arclight", "kind": "hybrid", "server_args": "nogui"},
        {"id": "youer", "label": "Youer", "kind": "hybrid", "server_args": "nogui"},
    ],
    "forge": [
        {"id": "arclight", "label": "Arclight", "kind": "hybrid", "server_args": "nogui"},
        {"id": "mohist", "label": "Mohist", "kind": "hybrid", "server_args": "nogui"},
    ],
    "fabric": [
        {"id": "arclight", "label": "Arclight", "kind": "hybrid", "server_args": "nogui"},
        {"id": "banner", "label": "Banner", "kind": "hybrid", "server_args": "nogui"},
    ],
    "quilt": [],
    "paper": [
        {"id": "purpur", "label": "Purpur", "kind": "plugin", "server_args": "--nogui"},
    ],
    "purpur": [
        {"id": "paper", "label": "Paper", "kind": "plugin", "server_args": "--nogui"},
    ],
    "vanilla": [
        {"id": "paper", "label": "Paper", "kind": "plugin", "server_args": "--nogui"},
        {"id": "purpur", "label": "Purpur", "kind": "plugin", "server_args": "--nogui"},
    ],
}


def core_choices(detected: dict[str, Any], loader: str) -> list[dict[str, Any]]:
    """整合包自带的核心在前，同加载器能跑的其他核心跟在后面。"""
    choices: list[dict[str, Any]] = []
    jars: list[str] = list(detected.get("jars") or [])
    family = str(detected.get("family") or "")
    if detected.get("loader") and (
        detected.get("unix_args") or detected.get("jar") or family
    ):
        version = str(detected.get("loader_version") or "")
        label = LOADER_LABELS.get(str(detected.get("loader") or ""), "整合包")
        if family in {"arclight", "youer", "mohist", "banner", "paper", "purpur"}:
            label = family[:1].upper() + family[1:]
        elif version:
            label = f"{label} {version}"
        label = f"{label}（整合包自带）"
        choices.append(
            {
                "id": "bundled",
                "label": label,
                "kind": detected.get("kind") or "mod",
                "launch": detected.get("launch") or "jar",
                "bundled": True,
                "jar": str(detected.get("jar") or ""),
                "unix_args": str(detected.get("unix_args") or ""),
                "server_args": str(detected.get("server_args") or "nogui"),
                "family": family,
            }
        )
    for row in _EXTRAS.get(loader, []):
        if row["id"] == family:
            continue
        jar = _pick_jar(jars, row["id"], loader)
        choices.append(
            {
                "id": row["id"],
                "label": row["label"],
                "kind": row["kind"],
                "launch": "jar",
                "bundled": False,
                "jar": jar,
                "unix_args": "",
                "server_args": row["server_args"],
                "family": row["id"],
            }
        )
    return choices


def startup_variable_key(variables: list[dict[str, Any]]) -> str:
    keys = {str(row.get("key") or "") for row in variables}
    if "STARTUP_CMD" in keys:
        return "STARTUP_CMD"
    if "STARTUP" in keys:
        return "STARTUP"
    return ""


def live_startup_command(details: dict[str, Any]) -> str:
    variables = details.get("variables") if isinstance(details.get("variables"), list) else []
    for key in ("STARTUP_CMD", "STARTUP"):
        for row in variables:
            if str(row.get("key") or "") == key:
                value = str(row.get("value") or "").strip()
                if value and "{{" not in value:
                    return value
    command = str(details.get("command") or "").strip()
    if command and "{{" not in command:
        return command
    return ""
