import { TARKOV_ITEM_ICON_PATHS } from "@/lib/tarkovItemIcons";
import {
  ITEMS_BASE_PATH,
  TARKOV_HANDBOOK_ROOTS,
  handbookHref,
  itemHrefFromTypes,
  itemPageBySlug,
} from "@/lib/tarkovItemTypes";
import { TARKOV_MAP_ICON_PATHS } from "@/lib/tarkovMapIcons";

export type TarkovNavStatus = "ready" | "soon";

export type TarkovHomeLink = {
  id: string;
  label: string;
  href: string;
  status: TarkovNavStatus;
  keywords?: string[];
  icon?: string;
};

export type TarkovHomeGroup = {
  id: string;
  label: string;
  en?: string;
  items: TarkovHomeLink[];
};

export type TarkovMapCard = TarkovHomeLink & {
  english: string;
  icon: string;
  comingSoon?: boolean;
};

export type TarkovItemCard = TarkovHomeLink & {
  icon: string;
};

export type TarkovTraderCard = TarkovHomeLink & {
  english: string;
  chinese: string;
  specialty: string;
  accent: string;
};

export function traderPortraitUrl(id: string): string {
  return `https://tarkov.dev/images/traders/${id}-portrait.png`;
}

/** tarkov.dev 任务表 / 筛选条用的商人小图标。 */
export function traderIconUrl(id: string): string {
  return `https://tarkov.dev/images/traders/${id}-icon.jpg`;
}

const TRADER_NICK_RE = /\s*[（(][^）)]+[）)]\s*$/;

/** 全站商人展示名：英文。旧「Name（昵称）」回退时剥掉括号。 */
export function traderDisplayName(slug = "", fallback = ""): string {
  const key = slug.trim();
  const known = TARKOV_TRADERS.find((item) => item.id === key);
  if (known?.english) return known.english;
  const raw = fallback.trim();
  if (!raw) return key;
  return raw.replace(TRADER_NICK_RE, "").trim() || raw;
}

/** tarkov.dev 头像文件名（Goons 用 Knight，邪教徒用祭司）。 */
const BOSS_PORTRAIT_FILES: Record<string, string> = {
  reshala: "reshala-portrait.webp",
  killa: "killa-portrait.png",
  glukhar: "glukhar-portrait.png",
  shturman: "shturman-portrait.png",
  sanitar: "sanitar-portrait.png",
  tagilla: "tagilla-portrait.png",
  kaban: "kaban-portrait.png",
  kollontay: "kollontay-portrait.png",
  zryachiy: "zryachiy-portrait.png",
  goons: "knight-portrait.png",
  cultists: "cultist-priest-portrait.webp",
  partisan: "partisan-portrait.png",
};

export function bossPortraitUrl(id: string): string {
  const file = BOSS_PORTRAIT_FILES[id];
  return file ? `https://assets.tarkov.dev/${file}` : "";
}

export type TarkovBossRow = TarkovHomeLink & {
  map: string;
  spawn: string;
  guards: string;
  accent: string;
};

export const TARKOV_HOME_PATH = "/guides/tarkov";

export function isTarkovHomePath(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "") || "/";
  return path === TARKOV_HOME_PATH;
}

export const MAPS_HREF = "/guides/tarkov/maps";
export const TARKOV_TRADERS_PATH = "/guides/tarkov/traders";
export const TARKOV_BOSSES_PATH = "/guides/tarkov/bosses";
export const TARKOV_HIDEOUT_PATH = "/guides/tarkov/hideout";
export const TARKOV_BARTERS_PATH = "/guides/tarkov/barters";
export const TARKOV_CRAFTS_PATH = "/guides/tarkov/crafts";
export const TARKOV_LOOT_TIERS_PATH = "/guides/tarkov/loot-tiers";
export const TARKOV_HIDEOUT_COST_PATH = "/guides/tarkov/hideout-cost";
export const TARKOV_WIPE_LENGTH_PATH = "/guides/tarkov/wipe-length";
export const TARKOV_BITCOIN_FARM_PATH = "/guides/tarkov/bitcoin-farm";
export const TARKOV_KEY_PACKS_PATH = "/guides/tarkov/key-packs";
export const TARKOV_GAME_LOGS_PATH = "/guides/tarkov/game-logs";
export const TARKOV_ME_PATH = "/guides/tarkov/me";

export const TARKOV_ME_TAB_IDS = ["tasks", "keys", "logs"] as const;
export type TarkovMeTabId = (typeof TARKOV_ME_TAB_IDS)[number];

export function resolveTarkovMeTab(raw: string | null | undefined): TarkovMeTabId {
  const key = (raw || "").trim();
  if (key === "logs" || key === "keys" || key === "tasks") return key;
  return "tasks";
}

export function tarkovMeHref(tab: TarkovMeTabId = "tasks"): string {
  return `${TARKOV_ME_PATH}?tab=${encodeURIComponent(tab)}`;
}

export function tarkovKeyPackHref(opts?: {
  q?: string;
  map?: string;
}): string {
  const params = new URLSearchParams();
  params.set("tab", "keys");
  const map = (opts?.map || "").trim();
  const q = (opts?.q || "").trim();
  if (map) params.set("map", map);
  if (q) params.set("q", q);
  return `${TARKOV_ME_PATH}?${params.toString()}`;
}
const PROGRESSION_HREF = "/guides/tarkov/progression";
export const TARKOV_TASKS_PATH = "/guides/tarkov/tasks";
export const TARKOV_RAID_PREP_PATH = "/guides/tarkov/raid-prep";

/** 首页短 id → json.tarkov.dev / 详情路径 slug。 */
const MAP_SLUG_ALIASES: Record<string, string> = {
  lab: "the-lab",
  streets: "streets-of-tarkov",
  labyrinth: "the-labyrinth",
};

export function tarkovMapSlug(id: string): string {
  return MAP_SLUG_ALIASES[id] || id;
}

export function tarkovMapHref(id: string): string {
  if (id === "openworld" || id === "transits") return MAPS_HREF;
  return `${MAPS_HREF}/${encodeURIComponent(id)}`;
}

export function tarkovHideoutHref(slug: string): string {
  return `${TARKOV_HIDEOUT_PATH}/${encodeURIComponent(slug)}`;
}

export function tarkovTaskHref(taskId: string): string {
  return `${TARKOV_TASKS_PATH}/${encodeURIComponent(taskId)}`;
}

export function tarkovRaidPrepHref(mapId?: string): string {
  if (!mapId) return TARKOV_RAID_PREP_PATH;
  return `${TARKOV_RAID_PREP_PATH}?map=${encodeURIComponent(mapId)}`;
}

export function tarkovRaidRoomHref(publicId: string): string {
  return `${TARKOV_RAID_PREP_PATH}/rooms/${encodeURIComponent(publicId)}`;
}

export function tarkovRaidRoomShareUrl(publicId: string, origin: string): string {
  return `${String(origin || "").replace(/\/$/, "")}${tarkovRaidRoomHref(publicId)}`;
}

export function tarkovTraderHref(slug: string): string {
  return `${TARKOV_TRADERS_PATH}/${encodeURIComponent(slug)}`;
}

/** 首页 The Goons / 邪教徒 对应 tarkov.dev 的 knight / cultist-priest。 */
const BOSS_DETAIL_SLUG: Record<string, string> = {
  goons: "knight",
  cultists: "cultist-priest",
};

export function tarkovBossHref(id: string): string {
  const slug = BOSS_DETAIL_SLUG[id] || id;
  return `${TARKOV_BOSSES_PATH}/${encodeURIComponent(slug)}`;
}

const GOLD = "#c8932a";
const TEAL = "#4ab8b8";
const GREEN = "#7ab648";
const RED = "#d44a4a";

/** 顺序对齐 tarkov.dev/maps：中文名 localeCompare，开放世界 / 转移点垫底。 */
const MAP_DEFS: Array<{
  id: string;
  label: string;
  english: string;
  keywords?: string[];
  comingSoon?: boolean;
}> = [
  { id: "reserve", label: "储备站", english: "Reserve", keywords: ["reserve"] },
  { id: "lighthouse", label: "灯塔", english: "Lighthouse", keywords: ["lighthouse"] },
  { id: "factory", label: "工厂", english: "Factory", keywords: ["factory"] },
  { id: "shoreline", label: "海岸线", english: "Shoreline", keywords: ["shoreline"] },
  { id: "customs", label: "海关", english: "Customs", keywords: ["customs"] },
  { id: "interchange", label: "立交桥", english: "Interchange", keywords: ["interchange"] },
  { id: "terminal", label: "码头", english: "Terminal", keywords: ["terminal", "pier"] },
  { id: "labyrinth", label: "迷宫", english: "Labyrinth", keywords: ["labyrinth"] },
  { id: "icebreaker", label: "破冰船", english: "Icebreaker", keywords: ["icebreaker"] },
  { id: "woods", label: "森林", english: "Woods", keywords: ["woods"] },
  { id: "lab", label: "实验室", english: "The Lab", keywords: ["lab", "the lab"] },
  {
    id: "streets",
    label: "塔科夫街区",
    english: "Streets of Tarkov",
    keywords: ["streets", "streets of tarkov"],
  },
  {
    id: "ground-zero",
    label: "中心区",
    english: "Ground Zero",
    keywords: ["ground zero", "gz", "街区"],
  },
  {
    id: "openworld",
    label: "开放世界",
    english: "Open World",
    keywords: ["open world", "openworld"],
    comingSoon: true,
  },
  {
    id: "transits",
    label: "转移点",
    english: "Transits",
    keywords: ["transit", "transits"],
    comingSoon: true,
  },
];

export const TARKOV_MAPS: TarkovMapCard[] = MAP_DEFS.map((def) => {
  const icon = TARKOV_MAP_ICON_PATHS[def.id];
  if (!icon) {
    throw new Error(`missing tarkov map icon: ${def.id}`);
  }
  const soon = Boolean(def.comingSoon);
  return {
    ...def,
    href: soon ? MAPS_HREF : tarkovMapHref(def.id),
    status: soon ? "soon" : "ready",
    icon,
    keywords: [def.english, ...(def.keywords || [])],
  };
});

export type TarkovMapMark = {
  id: string;
  label: string;
  icon: string;
};

/** 用中文/英文名找回首页同款地图图标；变体图（夜间工厂、暗室、21+）复用主图。 */
export function tarkovMapMarkByName(name: string): TarkovMapMark | null {
  const text = (name || "").trim();
  if (!text) return null;
  const lowered = text.toLowerCase();
  const exact = TARKOV_MAPS.find(
    (row) => row.label === text || row.english.toLowerCase() === lowered,
  );
  if (exact) return { id: exact.id, label: text, icon: exact.icon };
  if (text === "夜间工厂" || lowered.includes("factory (night)")) {
    return {
      id: "night-factory",
      label: text,
      icon: TARKOV_MAP_ICON_PATHS.factory,
    };
  }
  const prefixed = [...TARKOV_MAPS]
    .sort((a, b) => b.label.length - a.label.length)
    .find(
      (row) =>
        text.startsWith(row.label) ||
        lowered.startsWith(row.english.toLowerCase()),
    );
  if (prefixed) return { id: prefixed.id, label: text, icon: prefixed.icon };
  return { id: "", label: text, icon: "" };
}

export const TARKOV_TRADERS: TarkovTraderCard[] = [
  {
    id: "prapor",
    english: "Prapor",
    chinese: "",
    label: "Prapor",
    href: tarkovTraderHref("prapor"),
    status: "ready",
    keywords: ["售货员", "俄商"],
    specialty: "武器 & 弹药",
    accent: GOLD,
  },
  {
    id: "therapist",
    english: "Therapist",
    chinese: "",
    label: "Therapist",
    href: tarkovTraderHref("therapist"),
    status: "ready",
    keywords: ["治疗者", "大妈", "小护士"],
    specialty: "医疗 & 任务物品",
    accent: TEAL,
  },
  {
    id: "fence",
    english: "Fence",
    chinese: "",
    label: "Fence",
    href: tarkovTraderHref("fence"),
    status: "ready",
    keywords: ["围栏", "黑商"],
    specialty: "赃物收购",
    accent: GREEN,
  },
  {
    id: "skier",
    english: "Skier",
    chinese: "",
    label: "Skier",
    href: tarkovTraderHref("skier"),
    status: "ready",
    keywords: ["滑雪者", "走私客"],
    specialty: "改件 & 装备",
    accent: TEAL,
  },
  {
    id: "peacekeeper",
    english: "Peacekeeper",
    chinese: "",
    label: "Peacekeeper",
    href: tarkovTraderHref("peacekeeper"),
    status: "ready",
    keywords: ["维和者", "美商"],
    specialty: "NATO 武器",
    accent: TEAL,
  },
  {
    id: "mechanic",
    english: "Mechanic",
    chinese: "",
    label: "Mechanic",
    href: tarkovTraderHref("mechanic"),
    status: "ready",
    keywords: ["机械师"],
    specialty: "武器改装",
    accent: GOLD,
  },
  {
    id: "ragman",
    english: "Ragman",
    chinese: "",
    label: "Ragman",
    href: tarkovTraderHref("ragman"),
    status: "ready",
    keywords: ["ragman", "服装商", "破布"],
    specialty: "护甲 & 服装",
    accent: GOLD,
  },
  {
    id: "jaeger",
    english: "Jaeger",
    chinese: "",
    label: "Jaeger",
    href: tarkovTraderHref("jaeger"),
    status: "ready",
    keywords: ["猎人", "耶格"],
    specialty: "装备 & 食物",
    accent: GOLD,
  },
  {
    id: "lightkeeper",
    english: "Lightkeeper",
    chinese: "",
    label: "Lightkeeper",
    href: tarkovTraderHref("lightkeeper"),
    status: "ready",
    keywords: ["灯塔看守", "灯塔商人"],
    specialty: "灯塔任务",
    accent: GOLD,
  },
  {
    id: "ref",
    english: "Ref",
    chinese: "",
    label: "Ref",
    href: tarkovTraderHref("ref"),
    status: "ready",
    keywords: ["裁判", "竞技场裁判", "竞技场"],
    specialty: "竞技场",
    accent: RED,
  },
  {
    id: "btr-driver",
    english: "BTR Driver",
    chinese: "",
    label: "BTR Driver",
    href: tarkovTraderHref("btr-driver"),
    status: "ready",
    keywords: ["btr", "装甲车"],
    specialty: "街头补给",
    accent: GOLD,
  },
];

/** 首页商人条与 Hub / 顶栏同一集合。 */
export const TARKOV_HOME_TRADERS: TarkovTraderCard[] = TARKOV_TRADERS;

/** PvP 常规图出生率 / 护卫，对齐 json.tarkov.dev maps（不含 Terminal / 活动图）。 */
export const TARKOV_BOSSES: TarkovBossRow[] = [
  {
    id: "reshala",
    label: "Reshala",
    href: tarkovBossHref("reshala"),
    status: "ready",
    keywords: ["沙拉"],
    map: "海关",
    spawn: "45%",
    guards: "×4",
    accent: GOLD,
  },
  {
    id: "killa",
    label: "Killa",
    href: tarkovBossHref("killa"),
    status: "ready",
    map: "立交桥",
    spawn: "45%",
    guards: "—",
    accent: GOLD,
  },
  {
    id: "glukhar",
    label: "Glukhar",
    href: tarkovBossHref("glukhar"),
    status: "ready",
    keywords: ["火车头"],
    map: "储备站",
    spawn: "30%",
    guards: "×6",
    accent: GOLD,
  },
  {
    id: "shturman",
    label: "Shturman",
    href: tarkovBossHref("shturman"),
    status: "ready",
    map: "森林",
    spawn: "45%",
    guards: "×2–3",
    accent: GREEN,
  },
  {
    id: "sanitar",
    label: "Sanitar",
    href: tarkovBossHref("sanitar"),
    status: "ready",
    map: "海岸线",
    spawn: "45%",
    guards: "×3",
    accent: GOLD,
  },
  {
    id: "tagilla",
    label: "Tagilla",
    href: tarkovBossHref("tagilla"),
    status: "ready",
    keywords: ["锤哥"],
    map: "工厂",
    spawn: "30%",
    guards: "—",
    accent: RED,
  },
  {
    id: "kaban",
    label: "Kaban",
    href: tarkovBossHref("kaban"),
    status: "ready",
    map: "塔科夫街区",
    spawn: "45%",
    guards: "×6",
    accent: GOLD,
  },
  {
    id: "kollontay",
    label: "Kollontay",
    href: tarkovBossHref("kollontay"),
    status: "ready",
    keywords: ["科隆泰"],
    map: "塔科夫街区",
    spawn: "45%",
    guards: "×4",
    accent: GOLD,
  },
  {
    id: "zryachiy",
    label: "Zryachiy",
    href: tarkovBossHref("zryachiy"),
    status: "ready",
    keywords: ["守灯人"],
    map: "灯塔",
    spawn: "100%",
    guards: "×2",
    accent: GREEN,
  },
  {
    id: "goons",
    label: "The Goons",
    href: tarkovBossHref("goons"),
    status: "ready",
    keywords: ["三狗", "三兄弟", "骑士", "大管", "鸟眼", "knight", "big pipe", "birdeye"],
    map: "游荡",
    spawn: "15%",
    guards: "×2",
    accent: GREEN,
  },
  {
    id: "cultists",
    label: "邪教徒",
    href: tarkovBossHref("cultists"),
    status: "ready",
    map: "海关/森林",
    spawn: "10%",
    guards: "×4",
    accent: GREEN,
  },
  {
    id: "partisan",
    label: "Partisan",
    href: tarkovBossHref("partisan"),
    status: "ready",
    map: "游荡",
    spawn: "10%",
    guards: "—",
    accent: GREEN,
  },
];

/** 首页 BOSS 表与 Hub / 顶栏同一集合。 */
export const TARKOV_HOME_BOSSES: TarkovBossRow[] = TARKOV_BOSSES;

export const TARKOV_PROGRESSION: TarkovHomeLink[] = [
  {
    id: "tasks",
    label: "任务",
    href: TARKOV_TASKS_PATH,
    status: "ready",
    keywords: ["tasks", "quests"],
  },
  {
    id: "hideout",
    label: "藏身处",
    href: TARKOV_HIDEOUT_PATH,
    status: "ready",
    keywords: ["hideout", "藏身处"],
  },
  { id: "achievements", label: "成就", href: PROGRESSION_HREF, status: "soon" },
  { id: "prestige", label: "声望", href: PROGRESSION_HREF, status: "soon" },
  {
    id: "loot-tiers",
    label: "战利品等级",
    href: TARKOV_LOOT_TIERS_PATH,
    status: "ready",
    keywords: ["loot", "战利品"],
  },
];

/** 塔科夫个人中心：任务 / 钥匙 / 日志路径（搜索仍收录；工具栏走顶栏入口）。 */
export const TARKOV_ME_NAV: TarkovHomeLink = {
  id: "me",
  label: "个人中心",
  href: tarkovMeHref(),
  status: "ready",
  icon: "◎",
  keywords: [
    "任务管理",
    "任务树",
    "任务进度",
    "钥匙管理",
    "钥匙分类",
    "钥匙分类速查",
    "钥匙用途",
    "开哪扇门",
    "任务钥匙",
    "打包",
    "门锁",
    "日志路径",
    "游戏日志",
    "日志",
    "截图",
    "目录绑定",
    "自动检测",
    "application",
  ],
};

/** 首页联机大厅入口（搜索仍收录；工具栏不再重复）。 */
export const TARKOV_RAID_PREP_NAV: TarkovHomeLink = {
  id: "raid-prep",
  label: "联机大厅",
  href: TARKOV_HOME_PATH,
  status: "ready",
  icon: "⌖",
  keywords: ["raid", "prep", "lobby", "战局", "准备", "联机", "大厅", "任务点位", "房间"],
};

/** 首页右侧工具栏。 */
export const TARKOV_TOOLS: TarkovHomeLink[] = [
  {
    id: "ammo-chart",
    label: "弹药图表筛选器",
    href: `${ITEMS_BASE_PATH}/ammo`,
    status: "ready",
    icon: "⊕",
    keywords: ["弹药对照", "穿透", "散点", "ammo", "筛选"],
  },
  {
    id: "barter-profit",
    label: "商人交易利润",
    href: TARKOV_BARTERS_PATH,
    status: "ready",
    icon: "⇌",
    keywords: ["barter", "以物易物"],
  },
  {
    id: "craft-profit",
    label: "藏身处制作利润",
    href: TARKOV_CRAFTS_PATH,
    status: "ready",
    icon: "⚙",
    keywords: ["crafts", "制作"],
  },
  {
    id: "loot-tier-rank",
    label: "战利品等级排名",
    href: TARKOV_LOOT_TIERS_PATH,
    status: "ready",
    icon: "◈",
    keywords: ["loot", "战利品"],
  },
  {
    id: "hideout-cost",
    label: "藏身处建造成本",
    href: TARKOV_HIDEOUT_COST_PATH,
    status: "ready",
    icon: "⌂",
    keywords: ["hideout", "建造"],
  },
  {
    id: "wipe-length",
    label: "平均删档周期",
    href: TARKOV_WIPE_LENGTH_PATH,
    status: "ready",
    icon: "◷",
    keywords: ["wipe", "删档"],
  },
  {
    id: "btc-farm",
    label: "比特币矿场利润",
    href: TARKOV_BITCOIN_FARM_PATH,
    status: "ready",
    icon: "₿",
    keywords: ["bitcoin", "btc", "矿场"],
  },
];

/** 顶栏物品下拉：对齐 tarkov.dev 三分组，链到本站手册分类。 */
export const TARKOV_ITEM_MENU_GROUPS: TarkovHomeGroup[] = [
  {
    id: "gear",
    label: "装备",
    en: "Gear",
    items: [
      { id: "headsets", label: "耳机", href: `${ITEMS_BASE_PATH}/headsets`, status: "ready" },
      { id: "helmets", label: "头盔", href: `${ITEMS_BASE_PATH}/helmets`, status: "ready" },
      { id: "glasses", label: "眼镜", href: `${ITEMS_BASE_PATH}/glasses`, status: "ready" },
      { id: "armors", label: "护甲", href: `${ITEMS_BASE_PATH}/armors`, status: "ready" },
      { id: "rigs", label: "胸挂", href: `${ITEMS_BASE_PATH}/rigs`, status: "ready" },
      { id: "backpacks", label: "背包", href: `${ITEMS_BASE_PATH}/backpacks`, status: "ready" },
      { id: "meds", label: "医疗", href: `${ITEMS_BASE_PATH}/meds`, status: "ready" },
    ],
  },
  {
    id: "weaponry",
    label: "武器",
    en: "Weapons",
    items: [
      { id: "ammo", label: "弹药", href: `${ITEMS_BASE_PATH}/ammo`, status: "ready" },
      { id: "guns", label: "枪支", href: `${ITEMS_BASE_PATH}/guns`, status: "ready" },
      { id: "mods", label: "配件", href: `${ITEMS_BASE_PATH}/weapon-mods`, status: "ready" },
      { id: "pistol-grips", label: "手枪式握把", href: `${ITEMS_BASE_PATH}/pistol-grips`, status: "ready" },
      { id: "suppressors", label: "消音器", href: `${ITEMS_BASE_PATH}/suppressors`, status: "ready" },
    ],
  },
  {
    id: "tools",
    label: "装备 & 工具",
    en: "Gear & Tools",
    items: [
      { id: "grenades", label: "手榴弹", href: `${ITEMS_BASE_PATH}/grenades`, status: "ready" },
      { id: "containers", label: "容器", href: `${ITEMS_BASE_PATH}/containers`, status: "ready" },
      { id: "barter-items", label: "交换用物品", href: `${ITEMS_BASE_PATH}/barter`, status: "ready" },
      { id: "keys", label: "钥匙", href: `${ITEMS_BASE_PATH}/keys`, status: "ready" },
      { id: "provisions", label: "给养品", href: `${ITEMS_BASE_PATH}/provisions`, status: "ready" },
    ],
  },
];

export type TarkovTopNavItem = {
  id: string;
  label: string;
  href: string;
  groups?: TarkovHomeGroup[];
};

export const TARKOV_TOP_NAV: TarkovTopNavItem[] = [
  {
    id: "maps",
    label: "地图",
    href: MAPS_HREF,
    groups: [{ id: "maps", label: "突袭地图", items: TARKOV_MAPS }],
  },
  {
    id: "items",
    label: "物品",
    href: ITEMS_BASE_PATH,
    groups: TARKOV_ITEM_MENU_GROUPS,
  },
  {
    id: "traders",
    label: "商人",
    href: TARKOV_TRADERS_PATH,
    groups: [{ id: "traders", label: "商人", items: TARKOV_TRADERS }],
  },
  {
    id: "bosses",
    label: "BOSS",
    href: TARKOV_BOSSES_PATH,
    groups: [{ id: "bosses", label: "BOSS", items: TARKOV_BOSSES }],
  },
  {
    id: "progression",
    label: "进度",
    href: TARKOV_TASKS_PATH,
    groups: [{ id: "progression", label: "进度", items: TARKOV_PROGRESSION }],
  },
];

export type TarkovSearchHit = TarkovHomeLink & {
  group: string;
};

function linkKeywords(link: TarkovHomeLink): string {
  return [link.label, link.id, ...(link.keywords || [])].join(" ");
}

const SEARCH_TOKEN_RE = /[0-9a-zA-Z]+|[\u4e00-\u9fff]+/g;

export function compactSearchText(text: string): string {
  return (text || "").trim().toLowerCase().replace(/[\s\-_.·•]+/g, "");
}

export function textMatchesQuery(
  query: string,
  ...fields: Array<string | undefined>
): boolean {
  const q = (query || "").trim();
  if (!q) return false;
  const compactQ = compactSearchText(q);
  const tokens = q.toLowerCase().match(SEARCH_TOKEN_RE) || [];
  const blob = fields.filter(Boolean).join(" ");
  const compactBlob = compactSearchText(blob);
  const lowerBlob = blob.toLowerCase();
  if (compactQ && compactBlob.includes(compactQ)) return true;
  if (
    tokens.length > 0 &&
    tokens.every((token) => lowerBlob.includes(token) || compactBlob.includes(token))
  ) {
    return true;
  }
  return false;
}

export const TARKOV_HANDBOOK_CHIPS: TarkovHomeLink[] = TARKOV_HANDBOOK_ROOTS.map(
  (root) => ({
    id: root.slug,
    label: root.label,
    href: handbookHref(root),
    status: root.status,
  }),
);

export type TarkovHomeItemGroup = {
  id: string;
  label: string;
  en: string;
  items: TarkovItemCard[];
};

/** 首页物品三行，与顶栏下拉三大类一致。 */
export const TARKOV_HOME_ITEM_GROUPS: TarkovHomeItemGroup[] =
  TARKOV_ITEM_MENU_GROUPS.map((group) => ({
    id: group.id,
    label: group.label,
    en: group.en || "",
    items: group.items.map((item) => {
      const icon = TARKOV_ITEM_ICON_PATHS[item.id];
      if (!icon) {
        throw new Error(`missing tarkov item icon: ${item.id}`);
      }
      return { ...item, icon };
    }),
  }));

export const TARKOV_HOME_ITEMS: TarkovItemCard[] =
  TARKOV_HOME_ITEM_GROUPS.flatMap((group) => group.items);

export function buildHomeSearchIndex(): TarkovSearchHit[] {
  const hits: TarkovSearchHit[] = [];
  const push = (group: string, items: TarkovHomeLink[]) => {
    for (const item of items) {
      hits.push({ ...item, group });
    }
  };
  push("工具", [TARKOV_RAID_PREP_NAV, TARKOV_ME_NAV, ...TARKOV_TOOLS]);
  push("地图", TARKOV_MAPS);
  push("商人", TARKOV_TRADERS);
  push("BOSS", TARKOV_BOSSES);
  push("进度", TARKOV_PROGRESSION);
  for (const group of TARKOV_ITEM_MENU_GROUPS) {
    push(`物品 · ${group.label}`, group.items);
  }
  for (const root of TARKOV_HANDBOOK_ROOTS) {
    hits.push({
      id: `handbook-${root.slug}`,
      label: root.label,
      href: handbookHref(root),
      status: root.status,
      keywords: [root.slug, ...root.children.map((c) => c.label)],
      group: "手册分类",
    });
  }
  return hits;
}

export function filterHomeSearch(
  query: string,
  index: TarkovSearchHit[] = buildHomeSearchIndex(),
): TarkovSearchHit[] {
  const q = query.trim();
  if (!q) return [];
  return index.filter((hit) => textMatchesQuery(q, linkKeywords(hit)));
}

const SITE_SEARCH_NAV_GROUPS = new Set(["工具", "地图", "进度", "手册分类"]);

export function isSiteSearchNavGroup(group: string): boolean {
  return SITE_SEARCH_NAV_GROUPS.has(group) || group.startsWith("物品 ·");
}

export type TarkovSiteSearchHit = {
  id: string;
  name: string;
  extra?: string;
  icon_link?: string;
  types?: string[];
  slug?: string;
};

export type TarkovSiteSearchResult = {
  q?: string;
  items?: TarkovSiteSearchHit[];
  tasks?: TarkovSiteSearchHit[];
  traders?: TarkovSiteSearchHit[];
  bosses?: TarkovSiteSearchHit[];
  item_count?: number;
  task_count?: number;
  trader_count?: number;
  boss_count?: number;
};

export type TarkovSiteSearchRow = {
  key: string;
  href: string;
  label: string;
  extra?: string;
  icon?: string;
  soon?: boolean;
};

export type TarkovSiteSearchSection = {
  id: string;
  label: string;
  extra?: string;
  hits: TarkovSiteSearchRow[];
};

function searchSectionExtra(shown: number, total: number): string | undefined {
  if (total > shown) return `显示前 ${shown} 条 / 共 ${total}`;
  return undefined;
}

export function buildSiteSearchSections(
  q: string,
  api: TarkovSiteSearchResult | undefined,
  navIndex: TarkovSearchHit[] = buildHomeSearchIndex(),
): TarkovSiteSearchSection[] {
  const needle = q.trim();
  if (!needle) return [];
  const sections: TarkovSiteSearchSection[] = [];
  const tasks = api?.tasks ?? [];
  if (tasks.length) {
    sections.push({
      id: "tasks",
      label: "任务",
      extra: searchSectionExtra(tasks.length, api?.task_count ?? tasks.length),
      hits: tasks.map((hit) => ({
        key: `task-${hit.id}`,
        href: tarkovTaskHref(hit.id),
        label: hit.name,
        extra: hit.extra,
        icon: hit.icon_link,
      })),
    });
  }
  const items = api?.items ?? [];
  if (items.length) {
    sections.push({
      id: "items",
      label: "物品",
      extra: searchSectionExtra(items.length, api?.item_count ?? items.length),
      hits: items.map((hit) => ({
        key: `item-${hit.id}`,
        href: itemHrefFromTypes(hit.id, hit.types),
        label: hit.name,
        extra: hit.extra,
        icon: hit.icon_link,
      })),
    });
  }
  const traders = api?.traders ?? [];
  if (traders.length) {
    sections.push({
      id: "traders",
      label: "商人",
      extra: searchSectionExtra(
        traders.length,
        api?.trader_count ?? traders.length,
      ),
      hits: traders.map((hit) => ({
        key: `trader-${hit.slug || hit.id}`,
        href: tarkovTraderHref(hit.slug || hit.id),
        label: hit.name,
        extra: hit.extra,
        icon: hit.icon_link,
      })),
    });
  }
  const bosses = api?.bosses ?? [];
  if (bosses.length) {
    sections.push({
      id: "bosses",
      label: "BOSS",
      extra: searchSectionExtra(
        bosses.length,
        api?.boss_count ?? bosses.length,
      ),
      hits: bosses.map((hit) => ({
        key: `boss-${hit.slug || hit.id}`,
        href: tarkovBossHref(hit.slug || hit.id),
        label: hit.name,
        extra: hit.extra,
        icon: hit.icon_link,
      })),
    });
  }
  const navHits = filterHomeSearch(needle, navIndex).filter((hit) =>
    isSiteSearchNavGroup(hit.group),
  );
  if (navHits.length) {
    sections.push({
      id: "nav",
      label: "栏目",
      hits: navHits.map((hit) => ({
        key: `nav-${hit.group}-${hit.id}`,
        href: hit.href,
        label: hit.label,
        extra: hit.group,
        soon: hit.status === "soon",
      })),
    });
  }
  return sections;
}

/** 浏览器标签：栏目名；详情页再用物品/任务名覆盖。 */
export function tarkovPageTitle(pathname: string): string {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/guides/tarkov") return "逃离塔科夫";
  if (path.startsWith("/guides/tarkov/tasks")) return "任务";
  if (path.startsWith("/guides/tarkov/raid-prep")) return "联机大厅";
  if (path.startsWith("/guides/tarkov/traders")) return "商人";
  if (path.startsWith("/guides/tarkov/bosses")) return "BOSS";
  if (path.startsWith("/guides/tarkov/maps")) return "地图";
  if (path.startsWith("/guides/tarkov/hideout-cost")) return "藏身处建造成本";
  if (path.startsWith("/guides/tarkov/hideout")) return "藏身处";
  if (path.startsWith("/guides/tarkov/barters")) return "商人交易利润";
  if (path.startsWith("/guides/tarkov/crafts")) return "藏身处制作利润";
  if (path.startsWith("/guides/tarkov/loot-tiers")) return "战利品等级";
  if (path.startsWith("/guides/tarkov/wipe-length")) return "平均删档周期";
  if (path.startsWith("/guides/tarkov/bitcoin-farm")) return "比特币矿场利润";
  if (path.startsWith("/guides/tarkov/me")) return "个人中心";
  if (path.startsWith("/guides/tarkov/key-packs")) return "个人中心";
  if (path.startsWith("/guides/tarkov/game-logs")) return "个人中心";
  if (path.startsWith("/guides/tarkov/progression")) return "进度";
  if (path.startsWith("/guides/tarkov/items")) {
    const seg = path.split("/")[4];
    if (seg) {
      const page = itemPageBySlug(seg);
      if (page) return page.label;
    }
    return "物品";
  }
  return "逃离塔科夫";
}

/** 顶栏高亮：物品子路径、进度下的任务页都算对应栏目激活。 */
export function isTarkovTopNavActive(
  href: string,
  pathname: string,
  extraHrefs: string[] = [],
): boolean {
  const match = (h: string) =>
    pathname === h || pathname.startsWith(`${h}/`);
  return match(href) || extraHrefs.some(match);
}
