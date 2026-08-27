"""模组工具注册表：每个可操作模组一份规格，探测 / 安装 / 配置 / 指令都读这里。

新增模组时只加一条 `ModToolSpec`（加能力位），不要复制 Chunky 卡片或 RCON 编排。

能力位
- detect：按文件名（忽略加载器）扫 /mods 与 /plugins
- catalog：用写死的 Modrinth project id 拉「当前服加载器 + MC 版本」的最新文件，对比已装版本
- links：卡片上的 Modrinth / CurseForge / Wiki（CF 可按加载器换页）
- install / update：Pelican pull 到 /mods 或 /plugins，替换旧 jar
- config：键值预设（对账已有配置文件的顶层标量，一键只改钉住的键）
- commands：RCON 白名单（`command_tree` 静态补全，通用发送器按 argv 校验）
- features：模组功能栏（表单式操作，如 Chunky 生成范围、BlueMap 更新范围）

后续可接、暂不实现
- 依赖链（如 ChunkyBorder 依赖 Chunky）
- 禁用 jar（改名 .disabled）
- 配置 diff / 热重载失败回滚
- 多预设并存、按世界覆盖
- server.properties 服级钉（启动时自动打）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.minecraft.mod_catalog import query_from_jar

PLUGIN_LOADERS = frozenset({"paper", "spigot", "bukkit", "purpur", "folia"})
_LOADER_SUFFIXES = frozenset(
    {
        "fabric",
        "forge",
        "neoforge",
        "quilt",
        "bukkit",
        "spigot",
        "paper",
        "purpur",
        "folia",
        "sponge",
        "cli",
    }
)
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
class ModConfigPin:
    file: str
    key: str
    value: str


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
    argv: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ModFeatureSpec:
    id: str
    title: str
    summary: str = ""


@dataclass(frozen=True)
class ModToolSpec:
    id: str
    title: str
    match_names: tuple[str, ...]
    exclude_names: tuple[str, ...] = ()
    links: ModToolLinks = field(default_factory=ModToolLinks)
    plugin_loaders: frozenset[str] = PLUGIN_LOADERS
    config_mod_dir: str = ""
    config_plugin_dir: str = ""
    factory_mod_pins: tuple[ModConfigPin, ...] = ()
    factory_plugin_pins: tuple[ModConfigPin, ...] = ()
    summary: str = ""
    probe_command: str = ""
    command_prefix: str = ""
    command_tree: tuple[ModCommandNode, ...] = ()
    features: tuple[ModFeatureSpec, ...] = ()
    capabilities: tuple[str, ...] = ("detect", "catalog", "links", "install", "config")


class ModCommandError(ValueError):
    pass


BLUEMAP_CORE_PINS: tuple[ModConfigPin, ...] = (
    ModConfigPin(file="core.conf", key="accept-download", value="true"),
)

CHUNKY_MOD_PINS: tuple[ModConfigPin, ...] = (
    ModConfigPin(file="config.json", key="language", value="zh_CN"),
    ModConfigPin(file="config.json", key="continueOnRestart", value="true"),
    ModConfigPin(file="config.json", key="forceLoadExistingChunks", value="false"),
    ModConfigPin(file="config.json", key="silent", value="false"),
    ModConfigPin(file="config.json", key="updateInterval", value="5"),
)

CHUNKY_PLUGIN_PINS: tuple[ModConfigPin, ...] = (
    ModConfigPin(file="config.yml", key="language", value="zh_CN"),
    ModConfigPin(file="config.yml", key="continue-on-restart", value="true"),
    ModConfigPin(file="config.yml", key="force-load-existing-chunks", value="false"),
    ModConfigPin(file="config.yml", key="silent", value="false"),
    ModConfigPin(file="config.yml", key="update-interval", value="5"),
)

BLUEMAP_LINKS = ModToolLinks(
    modrinth_id="swbUV1cr",
    modrinth_slug="bluemap",
    curseforge_by_loader={
        "fabric": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "quilt": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "forge": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "neoforge": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "paper": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "spigot": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "bukkit": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "purpur": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
        "folia": "https://www.curseforge.com/minecraft/mc-mods/bluemap",
    },
    curseforge_fallback="https://www.curseforge.com/minecraft/mc-mods/bluemap",
    wiki_url="https://bluemap.bluecolored.de/wiki/",
    github_url="https://github.com/BlueMap-Minecraft/BlueMap",
    mcmod_url="https://www.mcmod.cn/class/3461.html",
    icon_url="https://cdn.modrinth.com/data/swbUV1cr/icon.png",
)

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
_MAP_ARG = ModCommandArg(id="map", label="地图", kind="map")
_OPTIONAL_MAP_ARG = ModCommandArg(id="map", label="地图", kind="map", optional=True)
_OPTIONAL_X_ARG = ModCommandArg(
    id="x",
    label="X",
    kind="int",
    min_value=-30_000_000,
    max_value=30_000_000,
    optional=True,
)
_OPTIONAL_Z_ARG = ModCommandArg(
    id="z",
    label="Z",
    kind="int",
    min_value=-30_000_000,
    max_value=30_000_000,
    optional=True,
)
_OPTIONAL_RADIUS_ARG = ModCommandArg(
    id="radius",
    label="半径",
    kind="int",
    min_value=1,
    max_value=1_000_000,
    optional=True,
)
_BLUEMAP_UPDATE_ARGS = (
    _OPTIONAL_MAP_ARG,
    _OPTIONAL_X_ARG,
    _OPTIONAL_Z_ARG,
    _OPTIONAL_RADIUS_ARG,
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

BLUEMAP_COMMAND_TREE: tuple[ModCommandNode, ...] = (
    ModCommandNode(id="status", label="查看状态", argv=()),
    ModCommandNode(id="version", label="版本信息"),
    ModCommandNode(id="help", label="帮助"),
    ModCommandNode(
        id="reload",
        label="重载配置",
        args=(
            ModCommandArg(
                id="mode",
                label="模式",
                kind="enum",
                options=(("light", "轻量"),),
                optional=True,
            ),
        ),
    ),
    ModCommandNode(id="maps", label="列出地图"),
    ModCommandNode(id="storages", label="列出存储"),
    ModCommandNode(id="start", label="开始渲染"),
    ModCommandNode(id="stop", label="停止渲染"),
    ModCommandNode(id="freeze", label="冻结地图", args=(_MAP_ARG,)),
    ModCommandNode(id="unfreeze", label="解冻地图", args=(_MAP_ARG,)),
    ModCommandNode(
        id="purge",
        label="清空地图",
        args=(_MAP_ARG,),
        confirm="会删除该地图已渲数据并重新渲染，期间网页地图不可用。确定清空？",
    ),
    ModCommandNode(id="update", label="增量更新", args=_BLUEMAP_UPDATE_ARGS),
    ModCommandNode(id="fix-edges", label="修边", args=_BLUEMAP_UPDATE_ARGS),
    ModCommandNode(
        id="force-update",
        label="强制重渲",
        args=_BLUEMAP_UPDATE_ARGS,
        confirm="会无视改动检测、整图重渲，耗时长。确定强制更新？",
    ),
    ModCommandNode(id="tasks", label="任务队列"),
    ModCommandNode(
        id="tasks-cancel",
        label="取消全部任务",
        argv=("tasks", "cancel"),
        args=(
            ModCommandArg(
                id="target",
                label="目标",
                kind="enum",
                options=(("all", "全部"),),
            ),
        ),
        confirm="会取消队列里所有渲染任务。确定？",
    ),
)

CHUNKY_FEATURES: tuple[ModFeatureSpec, ...] = (
    ModFeatureSpec(
        id="chunky.pregenerate",
        title="生成范围",
        summary="半径按方块计。500 大约覆盖 1000×1000 区域，过程可随时暂停，进度会保留。",
    ),
)

BLUEMAP_FEATURES: tuple[ModFeatureSpec, ...] = (
    ModFeatureSpec(
        id="bluemap.render",
        title="更新范围",
        summary="不填半径则更新整张图。BlueMap 平时会自动增量更新，改过配置或漏渲时才需要手动触发。",
    ),
)

SPECS: tuple[ModToolSpec, ...] = (
    ModToolSpec(
        id="chunky",
        title="Chunky",
        summary="预生成区块，减少第一次探索卡顿",
        match_names=("chunky",),
        exclude_names=("chunkyborder", "chunky-border"),
        links=CHUNKY_LINKS,
        config_mod_dir="config/chunky",
        config_plugin_dir="plugins/Chunky",
        factory_mod_pins=CHUNKY_MOD_PINS,
        factory_plugin_pins=CHUNKY_PLUGIN_PINS,
        probe_command="chunky progress",
        command_prefix="chunky",
        command_tree=CHUNKY_COMMAND_TREE,
        features=CHUNKY_FEATURES,
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
    ModToolSpec(
        id="bluemap",
        title="BlueMap",
        summary="浏览器里看世界 3D 地图",
        match_names=("bluemap",),
        links=BLUEMAP_LINKS,
        config_mod_dir="config/bluemap",
        config_plugin_dir="plugins/BlueMap",
        factory_mod_pins=BLUEMAP_CORE_PINS,
        factory_plugin_pins=BLUEMAP_CORE_PINS,
        probe_command="bluemap",
        command_prefix="bluemap",
        command_tree=BLUEMAP_COMMAND_TREE,
        features=BLUEMAP_FEATURES,
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
    raw = str(matches[-1]).lstrip("vV")
    if "-" in raw:
        head, tail = raw.rsplit("-", 1)
        if tail.lower() in _LOADER_SUFFIXES:
            return head
    return raw


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


def uses_plugin_config(loader: str, spec: ModToolSpec, *, present_directory: str = "") -> bool:
    return present_directory == "/plugins" or is_plugin_loader(loader, spec)


def factory_pins_out(
    spec: ModToolSpec,
    loader: str = "",
    *,
    present_directory: str = "",
) -> list[dict[str, str]]:
    plugin = uses_plugin_config(loader, spec, present_directory=present_directory)
    rows = spec.factory_plugin_pins if plugin else spec.factory_mod_pins
    return [{"file": row.file, "key": row.key, "value": row.value} for row in rows]


def safe_config_relpath(raw: str, *, fallback: str = "") -> str:
    """配置目录内的相对路径；拒绝 ..。"""
    text = (raw or "").replace("\\", "/").strip().lstrip("/")
    if not text:
        return fallback
    parts = [part for part in text.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        return fallback
    return "/".join(parts)


def spec_config_directories(spec: ModToolSpec) -> list[str]:
    rows: list[str] = []
    for rel in (spec.config_mod_dir, spec.config_plugin_dir):
        text = (rel or "").replace("\\", "/").strip().strip("/")
        if text:
            rows.append(f"/{text}")
    return rows


def relativize_config_path(raw: str, directory: str = "", *, fallback: str = "") -> str:
    """把绝对路径或相对路径收成配置目录内的相对文件名。"""
    text = (raw or "").replace("\\", "/").strip()
    dir_norm = (directory or "").replace("\\", "/").strip().rstrip("/")
    prefixes: list[str] = []
    if dir_norm:
        prefixes.append(dir_norm)
        stripped = dir_norm.lstrip("/")
        if stripped and stripped != dir_norm:
            prefixes.append(stripped)
        if not dir_norm.startswith("/"):
            prefixes.append(f"/{dir_norm}")
    matched = False
    for prefix in prefixes:
        if text == prefix:
            return fallback
        if text.startswith(f"{prefix}/"):
            text = text[len(prefix) + 1 :]
            matched = True
            break
    if text.startswith("/") and prefixes and not matched:
        return fallback
    return safe_config_relpath(text, fallback=fallback)


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


def features_out(spec: ModToolSpec) -> list[dict[str, str]]:
    return [
        {"id": row.id, "title": row.title, "summary": row.summary} for row in spec.features
    ]


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
    if arg.kind in {"world", "token", "map"}:
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
    tokens = list(node.argv) if node.argv is not None else [node.id]
    for token in [prefix, *tokens]:
        if token and not _TOKEN_RE.match(token):
            raise ModCommandError("指令不合法")
    payload = args or {}
    parts = [prefix, *tokens]
    skipped_optional = False
    for arg in node.args:
        raw = payload.get(arg.id)
        if raw is None or raw == "":
            if arg.optional:
                skipped_optional = True
                continue
            raise ModCommandError(f"缺少「{arg.label}」")
        if skipped_optional:
            raise ModCommandError(f"填写「{arg.label}」前需补全前面的参数")
        parts.append(_format_command_arg(arg, raw))
    return " ".join(part for part in parts if part)
