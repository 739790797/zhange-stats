"""模组工具注册表：每个可操作模组一份规格，探测 / 安装 / 配置 / 指令都读这里。

新增模组时只加一条 `ModToolSpec`（加能力位），不要复制 Chunky 卡片或 RCON 编排。

能力位
- detect：按文件名（忽略加载器）扫 /mods 与 /plugins
- catalog：用写死的 Modrinth project id 拉「当前服加载器 + MC 版本」的最新文件，对比已装版本
- links：卡片上的 Modrinth / CurseForge / Wiki（CF 可按加载器换页）
- install / update：Pelican pull 到 /mods 或 /plugins，替换旧 jar
- config：把预设文件写到该模组的配置目录
- commands：RCON 白名单（`command_tree` 静态补全，通用发送器按 argv 校验）

后续可接、暂不实现
- 依赖链（如 ChunkyBorder 依赖 Chunky）
- 禁用 jar（改名 .disabled）
- 配置 diff / 热重载失败回滚
- 多预设并存、按世界覆盖
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.minecraft_mod_catalog import query_from_jar

PLUGIN_LOADERS = frozenset({"paper", "spigot", "bukkit", "purpur", "folia"})
_VERSION = re.compile(r"v?\d+\.\d+(?:\.\d+)?(?:-[a-z]+\d*)?", re.I)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")

SHAPE_CHOICES: tuple[tuple[str, str], ...] = (
    ("square", "正方形"),
    ("circle", "圆形"),
    ("diamond", "菱形"),
    ("ellipse", "椭圆"),
    ("rectangle", "矩形"),
    ("triangle", "三角形"),
    ("pentagon", "五边形"),
    ("hexagon", "六边形"),
    ("star", "星形"),
)
PATTERN_CHOICES: tuple[tuple[str, str], ...] = (
    ("concentric", "由内向外"),
    ("loop", "逐行"),
    ("spiral", "螺旋"),
    ("csv", "CSV"),
    ("region", "区域文件"),
)


@dataclass(frozen=True)
class ModToolLinks:
    modrinth_id: str = ""
    modrinth_slug: str = ""
    curseforge_by_loader: dict[str, str] = field(default_factory=dict)
    curseforge_fallback: str = ""
    wiki_url: str = ""
    github_url: str = ""
    mcmod_url: str = ""
    icon_url: str = ""


@dataclass(frozen=True)
class ModConfigPreset:
    id: str
    title: str
    summary: str
    filename: str = ""
    content: str = ""
    mod_filename: str = ""
    plugin_filename: str = ""
    mod_content: str = ""
    plugin_content: str = ""


@dataclass(frozen=True)
class ModCommandArg:
    id: str
    label: str
    kind: str
    options: tuple[tuple[str, str], ...] = ()
    min_value: int | None = None
    max_value: int | None = None
    optional: bool = False


@dataclass(frozen=True)
class ModCommandNode:
    id: str
    label: str
    args: tuple[ModCommandArg, ...] = ()
    confirm: str = ""
    show_in_bar: bool = True


@dataclass(frozen=True)
class ModToolSpec:
    id: str
    title: str
    summary: str
    match_names: tuple[str, ...]
    exclude_names: tuple[str, ...] = ()
    links: ModToolLinks = field(default_factory=ModToolLinks)
    plugin_loaders: frozenset[str] = PLUGIN_LOADERS
    config_mod_dir: str = ""
    config_plugin_dir: str = ""
    presets: tuple[ModConfigPreset, ...] = ()
    probe_command: str = ""
    command_prefix: str = ""
    command_tree: tuple[ModCommandNode, ...] = ()
    capabilities: tuple[str, ...] = ("detect", "catalog", "links", "install", "config")


class ModCommandError(ValueError):
    pass


CHUNKY_SERVER_YML = """# 战鸽预设：中文提示、重启后续跑、降低刷屏
version: 2
language: zh_CN
continue-on-restart: true
force-load-existing-chunks: false
silent: false
update-interval: 5
"""

CHUNKY_SERVER_JSON = """{
  "version": 2,
  "language": "zh_CN",
  "continueOnRestart": true,
  "forceLoadExistingChunks": false,
  "silent": false,
  "updateInterval": 5
}
"""

CHUNKY_LINKS = ModToolLinks(
    modrinth_id="fALzjamp",
    modrinth_slug="chunky",
    curseforge_by_loader={
        "fabric": "https://www.curseforge.com/minecraft/mc-mods/chunky-pregenerator",
        "quilt": "https://www.curseforge.com/minecraft/mc-mods/chunky-pregenerator",
        "forge": "https://www.curseforge.com/minecraft/mc-mods/chunky-pregenerator-forge",
        "neoforge": "https://www.curseforge.com/minecraft/mc-mods/chunky-pregenerator-forge",
        "paper": "https://www.curseforge.com/minecraft/bukkit-plugins/chunky-pregenerator",
        "spigot": "https://www.curseforge.com/minecraft/bukkit-plugins/chunky-pregenerator",
        "bukkit": "https://www.curseforge.com/minecraft/bukkit-plugins/chunky-pregenerator",
        "purpur": "https://www.curseforge.com/minecraft/bukkit-plugins/chunky-pregenerator",
    },
    curseforge_fallback="https://www.curseforge.com/minecraft/mc-mods/chunky-pregenerator",
    wiki_url="https://github.com/pop4959/Chunky/wiki",
    github_url="https://github.com/pop4959/Chunky",
    mcmod_url="https://www.mcmod.cn/class/6239.html",
    icon_url="https://cdn.modrinth.com/data/fALzjamp/icon.png",
)

_WORLD_ARG = ModCommandArg(id="world", label="世界", kind="world")
_OPTIONAL_WORLD_ARG = ModCommandArg(
    id="world",
    label="世界",
    kind="world",
    optional=True,
)

CHUNKY_COMMAND_TREE: tuple[ModCommandNode, ...] = (
    ModCommandNode(id="world", label="设置世界", args=(_WORLD_ARG,)),
    ModCommandNode(
        id="shape",
        label="设置形状",
        args=(ModCommandArg(id="shape", label="形状", kind="enum", options=SHAPE_CHOICES),),
    ),
    ModCommandNode(
        id="center",
        label="设置中心",
        args=(
            ModCommandArg(
                id="x",
                label="X",
                kind="int",
                min_value=-30_000_000,
                max_value=30_000_000,
            ),
            ModCommandArg(
                id="z",
                label="Z",
                kind="int",
                min_value=-30_000_000,
                max_value=30_000_000,
            ),
        ),
    ),
    ModCommandNode(
        id="radius",
        label="设置半径",
        args=(
            ModCommandArg(
                id="radius",
                label="半径",
                kind="int",
                min_value=1,
                max_value=1_000_000,
            ),
        ),
    ),
    ModCommandNode(
        id="pattern",
        label="设置模式",
        args=(
            ModCommandArg(
                id="pattern",
                label="模式",
                kind="enum",
                options=PATTERN_CHOICES,
            ),
        ),
    ),
    ModCommandNode(id="selection", label="查看选择"),
    ModCommandNode(id="spawn", label="中心设为出生点"),
    ModCommandNode(
        id="worldborder",
        label="对齐世界边界",
        args=(_OPTIONAL_WORLD_ARG,),
    ),
    ModCommandNode(id="reload", label="重载配置"),
    ModCommandNode(
        id="trim",
        label="裁剪区块",
        confirm="会删除当前选择范围外的区块，不可恢复。确定裁剪？",
    ),
    ModCommandNode(id="confirm", label="确认"),
)

SPECS: tuple[ModToolSpec, ...] = (
    ModToolSpec(
        id="chunky",
        title="Chunky",
        summary="预生成世界区块",
        match_names=("chunky",),
        exclude_names=("chunkyborder", "chunky-border"),
        links=CHUNKY_LINKS,
        config_mod_dir="config/chunky",
        config_plugin_dir="plugins/Chunky",
        presets=(
            ModConfigPreset(
                id="zhange",
                title="战鸽预设",
                summary="中文、重启后续跑、控制台 5 秒一条进度",
                mod_filename="config.json",
                mod_content=CHUNKY_SERVER_JSON,
                plugin_filename="config.yml",
                plugin_content=CHUNKY_SERVER_YML,
            ),
        ),
        probe_command="chunky progress",
        command_prefix="chunky",
        command_tree=CHUNKY_COMMAND_TREE,
        capabilities=(
            "detect",
            "catalog",
            "links",
            "install",
            "update",
            "config",
            "commands",
        ),
    ),
)
SPEC_BY_ID = {row.id: row for row in SPECS}


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def jar_matches_spec(filename: str, spec: ModToolSpec) -> bool:
    query = query_from_jar(filename).lower()
    compact_query = _compact(query)
    compact_stem = _compact(filename)
    for excl in spec.exclude_names:
        token = _compact(excl)
        if token and (token in compact_query or token in compact_stem):
            return False
    for name in spec.match_names:
        wanted = _compact(name)
        if wanted and compact_query == wanted:
            return True
    return False


def version_from_jar(filename: str) -> str:
    matches = _VERSION.findall(filename or "")
    if not matches:
        return ""
    return str(matches[-1]).lstrip("vV")


def is_plugin_loader(loader: str, spec: ModToolSpec | None = None) -> bool:
    loaders = spec.plugin_loaders if spec is not None else PLUGIN_LOADERS
    return (loader or "").strip().lower() in loaders


def install_directory(loader: str, spec: ModToolSpec, *, present_directory: str = "") -> str:
    if present_directory in {"/mods", "/plugins"}:
        return present_directory
    return "/plugins" if is_plugin_loader(loader, spec) else "/mods"


def config_directory(loader: str, spec: ModToolSpec, *, present_directory: str = "") -> str:
    plugin = present_directory == "/plugins" or is_plugin_loader(loader, spec)
    raw = spec.config_plugin_dir if plugin else spec.config_mod_dir
    return raw.strip("/").strip()


def curseforge_url(loader: str, spec: ModToolSpec) -> str:
    mapping = spec.links.curseforge_by_loader or {}
    return mapping.get((loader or "").strip().lower()) or spec.links.curseforge_fallback or ""


def spec_project_id(spec: ModToolSpec) -> str:
    return (spec.links.modrinth_id or spec.links.modrinth_slug or "").strip()


def modrinth_url(spec: ModToolSpec) -> str:
    slug = (spec.links.modrinth_slug or spec.links.modrinth_id or "").strip()
    if not slug:
        return ""
    return f"https://modrinth.com/mod/{slug}"


def spec_links_out(spec: ModToolSpec, loader: str = "") -> dict[str, str]:
    links = spec.links
    return {
        "modrinth_url": modrinth_url(spec),
        "curseforge_url": curseforge_url(loader, spec),
        "wiki_url": links.wiki_url,
        "github_url": links.github_url,
        "mcmod_url": links.mcmod_url,
        "icon_url": links.icon_url,
    }


def preset_by_id(spec: ModToolSpec, preset_id: str) -> ModConfigPreset | None:
    wanted = (preset_id or "").strip()
    for row in spec.presets:
        if row.id == wanted:
            return row
    return spec.presets[0] if spec.presets and not wanted else None


def uses_plugin_config(loader: str, spec: ModToolSpec, *, present_directory: str = "") -> bool:
    return present_directory == "/plugins" or is_plugin_loader(loader, spec)


def preset_file_for_loader(
    preset: ModConfigPreset,
    loader: str,
    spec: ModToolSpec,
    *,
    present_directory: str = "",
) -> tuple[str, str]:
    """按加载器选一份出厂文件：模组 config.json，插件 config.yml。"""
    plugin = uses_plugin_config(loader, spec, present_directory=present_directory)
    if plugin:
        name = (preset.plugin_filename or preset.filename or "").strip()
        body = preset.plugin_content or preset.content
    else:
        name = (preset.mod_filename or preset.filename or "").strip()
        body = preset.mod_content or preset.content
    return name, body


def read_draft_content(blob: Any, tool_id: str, preset_id: str) -> str | None:
    if not isinstance(blob, dict):
        return None
    tool = blob.get(tool_id)
    if not isinstance(tool, dict):
        return None
    entry = tool.get(preset_id)
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        text = entry.get("content")
        if isinstance(text, str):
            return text
    return None


def upsert_draft_content(
    blob: Any,
    tool_id: str,
    preset_id: str,
    content: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(blob, dict):
        for key, value in blob.items():
            out[str(key)] = dict(value) if isinstance(value, dict) else value
    tool = out.get(tool_id)
    tool_map: dict[str, Any] = dict(tool) if isinstance(tool, dict) else {}
    prev = tool_map.get(preset_id)
    entry: dict[str, Any] = dict(prev) if isinstance(prev, dict) else {}
    entry["content"] = content
    tool_map[preset_id] = entry
    out[tool_id] = tool_map
    return out


def clear_draft_content(blob: Any, tool_id: str, preset_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(blob, dict):
        for key, value in blob.items():
            out[str(key)] = dict(value) if isinstance(value, dict) else value
    tool = out.get(tool_id)
    if not isinstance(tool, dict):
        return out
    tool.pop(preset_id, None)
    if tool:
        out[tool_id] = tool
    else:
        out.pop(tool_id, None)
    return out


def resolve_preset_body(
    preset: ModConfigPreset,
    loader: str,
    spec: ModToolSpec,
    blob: Any,
    *,
    present_directory: str = "",
) -> tuple[str, str, str]:
    filename, factory = preset_file_for_loader(
        preset, loader, spec, present_directory=present_directory
    )
    draft = read_draft_content(blob, spec.id, preset.id)
    if draft is not None:
        return filename, draft, "draft"
    return filename, factory, "factory"


def config_directory_abs(
    loader: str,
    spec: ModToolSpec,
    *,
    present_directory: str = "",
) -> str:
    rel = config_directory(loader, spec, present_directory=present_directory)
    if not rel:
        return ""
    return f"/{rel}"


def command_tree_out(spec: ModToolSpec) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in spec.command_tree:
        rows.append(
            {
                "id": node.id,
                "label": node.label,
                "confirm": node.confirm,
                "show_in_bar": node.show_in_bar,
                "args": [
                    {
                        "id": arg.id,
                        "label": arg.label,
                        "kind": arg.kind,
                        "options": [
                            {"value": value, "label": label} for value, label in arg.options
                        ],
                        "min_value": arg.min_value,
                        "max_value": arg.max_value,
                        "optional": arg.optional,
                    }
                    for arg in node.args
                ],
            }
        )
    return rows


def command_node_by_id(spec: ModToolSpec, command_id: str) -> ModCommandNode | None:
    wanted = (command_id or "").strip()
    for node in spec.command_tree:
        if node.id == wanted:
            return node
    return None


def _format_command_arg(arg: ModCommandArg, raw: Any) -> str:
    if arg.kind == "int":
        try:
            number = int(raw)
        except (TypeError, ValueError) as exc:
            raise ModCommandError(f"{arg.label}须为整数") from exc
        lo = -30_000_000 if arg.min_value is None else arg.min_value
        hi = 30_000_000 if arg.max_value is None else arg.max_value
        if number < lo or number > hi:
            raise ModCommandError(f"{arg.label}超出范围")
        return str(number)
    text = str(raw).strip()
    if arg.kind == "enum":
        mapping = {value.lower(): value for value, _label in arg.options}
        picked = mapping.get(text.lower())
        if not picked:
            raise ModCommandError(f"不支持的{arg.label}")
        return picked
    if arg.kind in {"world", "token"}:
        if not _TOKEN_RE.match(text):
            raise ModCommandError(f"{arg.label}不合法")
        return text
    raise ModCommandError("未知参数类型")


def assemble_mod_command(
    spec: ModToolSpec,
    command_id: str,
    args: dict[str, Any] | None = None,
) -> str:
    if "commands" not in spec.capabilities:
        raise ModCommandError("该模组不支持指令")
    node = command_node_by_id(spec, command_id)
    if node is None:
        raise ModCommandError("不支持的指令")
    prefix = (spec.command_prefix or spec.id).strip()
    if not _TOKEN_RE.match(prefix) or not _TOKEN_RE.match(node.id):
        raise ModCommandError("指令不合法")
    payload = args or {}
    parts = [prefix, node.id]
    for arg in node.args:
        raw = payload.get(arg.id)
        if raw is None or raw == "":
            if arg.optional:
                continue
            raise ModCommandError(f"缺少「{arg.label}」")
        parts.append(_format_command_arg(arg, raw))
    return " ".join(parts)
