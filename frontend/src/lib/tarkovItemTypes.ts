/**
 * 仓库/手册搜索侧栏一级分类（BSG handbook.Categories，ParentId 为空，按 Order 升序）。
 * 子类为 ParentId=一级 的直接下级（再下一级配件细分不在此展开）。
 */

export type TarkovHandbookStatus = "ready" | "soon";

export type TarkovHandbookChild = {
  id: string;
  order: number;
  label: string;
};

export type TarkovHandbookRoot = {
  /** handbook 分类 ID */
  id: string;
  order: number;
  label: string;
  /** URL 段 */
  slug: string;
  status: TarkovHandbookStatus;
  /** 已接入的内容面板 */
  panel?: "ammo" | "guns";
  /** tarkov.dev ItemType，手册 id 对不上时作目录兜底 */
  types?: string[];
  children: TarkovHandbookChild[];
};

export const ITEMS_BASE_PATH = "/guides/tarkov/items";

/** 与游戏手册一级一致；中文名对齐仓库/手册常见文案 */
export const TARKOV_HANDBOOK_ROOTS: TarkovHandbookRoot[] = [
  {
    id: "6564b96a189fe36f356d177c",
    order: 0,
    label: "战令文件",
    slug: "battle-pass",
    status: "ready",
    types: ["poster"],
    children: [],
  },
  {
    id: "5b619f1a86f77450a702a6f3",
    order: 1,
    label: "任务物品",
    slug: "quest-items",
    status: "ready",
    children: [],
  },
  {
    id: "5b5f78b786f77447ed5636af",
    order: 2,
    label: "货币",
    slug: "money",
    status: "ready",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b343",
    order: 3,
    label: "地图",
    slug: "maps",
    status: "ready",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b345",
    order: 4,
    label: "特殊装备",
    slug: "special-equipment",
    status: "ready",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b341",
    order: 5,
    label: "情报物品",
    slug: "info-items",
    status: "ready",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b342",
    order: 6,
    label: "钥匙",
    slug: "keys",
    status: "ready",
    children: [
      { id: "5c518ec986f7743b68682ce2", order: 100, label: "机械钥匙" },
      { id: "5c518ed586f774119a772aee", order: 100, label: "电子钥匙" },
    ],
  },
  {
    id: "5b47574386f77428ca22b344",
    order: 7,
    label: "医疗物品",
    slug: "meds",
    status: "ready",
    children: [
      { id: "5b47574386f77428ca22b338", order: 100, label: "急救包" },
      { id: "5b47574386f77428ca22b337", order: 100, label: "药品" },
      { id: "5b47574386f77428ca22b339", order: 100, label: "创伤处理" },
      { id: "5b47574386f77428ca22b33a", order: 100, label: "注射器" },
    ],
  },
  {
    id: "5b47574386f77428ca22b340",
    order: 8,
    label: "饮食",
    slug: "provisions",
    status: "ready",
    children: [
      { id: "5b47574386f77428ca22b335", order: 100, label: "饮品" },
      { id: "5b47574386f77428ca22b336", order: 100, label: "食物" },
    ],
  },
  {
    id: "5b47574386f77428ca22b346",
    order: 9,
    label: "弹药",
    slug: "ammo",
    status: "ready",
    panel: "ammo",
    children: [
      { id: "5b47574386f77428ca22b33c", order: 100, label: "弹药包" },
      { id: "5b47574386f77428ca22b33b", order: 100, label: "子弹" },
    ],
  },
  {
    id: "5b5f78dc86f77409407a7f8e",
    order: 10,
    label: "武器",
    slug: "guns",
    status: "ready",
    panel: "guns",
    children: [
      { id: "5b5f78fc86f77409407a7f90", order: 100, label: "突击步枪" },
      { id: "5b5f796a86f774093f2ed3c0", order: 100, label: "冲锋枪" },
      { id: "5b5f794b86f77409407a7f92", order: 100, label: "霰弹枪" },
      { id: "5b5f7a2386f774093f2ed3c4", order: 100, label: "投掷物" },
      { id: "5b5f79a486f77409407a7f94", order: 100, label: "机枪" },
      { id: "5b5f78e986f77447ed5636b1", order: 100, label: "突击卡宾枪" },
      { id: "5b5f7a0886f77409407a7f96", order: 100, label: "近战武器" },
      { id: "5b5f79d186f774093f2ed3c2", order: 100, label: "榴弹发射器" },
      { id: "5b5f791486f774093f2ed3be", order: 100, label: "精确射手步枪" },
      { id: "5b5f792486f77447ed5636b3", order: 100, label: "手枪" },
      { id: "5b5f798886f77447ed5636b5", order: 100, label: "栓动式步枪" },
      { id: "5b5f79eb86f77447ed5636b7", order: 100, label: "特殊武器" },
    ],
  },
  {
    id: "5b5f71a686f77447ed5636ab",
    order: 11,
    label: "武器零件&配件",
    slug: "weapon-mods",
    status: "ready",
    children: [
      { id: "5b5f750686f774093e6cb503", order: 100, label: "装备配件" },
      { id: "5b5f71b386f774093f2ecf11", order: 100, label: "功能模块" },
      { id: "5b5f75b986f77447ec5d7710", order: 100, label: "基础部件" },
    ],
  },
  {
    id: "5b47574386f77428ca22b33f",
    order: 12,
    label: "装备",
    slug: "gear",
    status: "ready",
    children: [
      { id: "5b5f6fa186f77409407a7eb7", order: 100, label: "容器" },
      { id: "5b5f6f8786f77447ed563642", order: 100, label: "战术胸挂" },
      { id: "5b5f6f3c86f774094242ef87", order: 100, label: "耳机" },
      { id: "5b5f6f6c86f774093f2ecf0b", order: 100, label: "背包" },
      { id: "5b5f701386f774093f2ecf0f", order: 100, label: "防弹衣" },
      { id: "5b47574386f77428ca22b330", order: 100, label: "头部装备" },
      { id: "5b47574386f77428ca22b331", order: 100, label: "眼部装备" },
      { id: "5b5f6fd286f774093f2ecf0d", order: 100, label: "安全箱" },
      { id: "5b47574386f77428ca22b32f", order: 100, label: "面部装备" },
      { id: "5b5f704686f77447ec5d76d7", order: 100, label: "装备组件" },
    ],
  },
  {
    id: "5b47574386f77428ca22b33e",
    order: 13,
    label: "交换用物品",
    slug: "barter",
    status: "ready",
    children: [
      { id: "5b47574386f77428ca22b2f6", order: 100, label: "工具" },
      { id: "5b47574386f77428ca22b2f0", order: 100, label: "日常用品" },
      { id: "5b47574386f77428ca22b2ed", order: 100, label: "能源物品" },
      { id: "5b47574386f77428ca22b2f1", order: 100, label: "贵重物品" },
      { id: "5b47574386f77428ca22b2ef", order: 100, label: "电子产品" },
      { id: "5b47574386f77428ca22b2f2", order: 100, label: "易燃物品" },
      { id: "5b47574386f77428ca22b2f3", order: 100, label: "医疗用品" },
      { id: "5b47574386f77428ca22b2ee", order: 100, label: "建筑材料" },
      { id: "5b47574386f77428ca22b2f4", order: 110, label: "其他" },
    ],
  },
];

export function handbookRootBySlug(
  raw: string | null | undefined,
): TarkovHandbookRoot | undefined {
  const key = (raw || "").trim();
  if (!key) return undefined;
  if (key === "gun" || key === "weapons") {
    return TARKOV_HANDBOOK_ROOTS.find((r) => r.slug === "guns");
  }
  return (
    TARKOV_HANDBOOK_ROOTS.find((r) => r.slug === key) ||
    TARKOV_HANDBOOK_ROOTS.find((r) => r.id === key)
  );
}

export function handbookHref(root: TarkovHandbookRoot): string {
  return `${ITEMS_BASE_PATH}/${root.slug}`;
}

export function ammoDetailHref(itemId: string): string {
  return `${ITEMS_BASE_PATH}/ammo/${encodeURIComponent(itemId)}`;
}

/** @deprecated 旧 ItemType 导航；保留别名以免外部引用炸掉 */
export type TarkovItemTypeCard = TarkovHandbookRoot & { key: string };

export function itemTypeHref(key: string): string {
  const root =
    handbookRootBySlug(key) ||
    TARKOV_HANDBOOK_ROOTS.find((r) => r.panel === key);
  return root ? handbookHref(root) : `${ITEMS_BASE_PATH}/${key}`;
}

export function resolveItemTypeKey(
  raw: string | null | undefined,
): string | null {
  const root = handbookRootBySlug(raw);
  return root?.slug ?? null;
}

export function itemTypeCardByKey(
  key: string,
): TarkovHandbookRoot | undefined {
  return handbookRootBySlug(key);
}

export const resolveItemTypeTab = resolveItemTypeKey;

export function itemTypeTabParam(key: string): string {
  return handbookRootBySlug(key)?.slug || key;
}

export function itemTypePathSegment(key: string): string {
  return itemTypeTabParam(key);
}

export type TarkovItemPanel = "ammo" | "guns" | "catalog";

export type TarkovItemPage = {
  slug: string;
  label: string;
  panel: TarkovItemPanel;
  parentSlug?: string;
  categoryIds: string[];
  types?: string[];
  children: TarkovHandbookChild[];
};

function handbookChildId(rootSlug: string, childLabel: string): string {
  const root = TARKOV_HANDBOOK_ROOTS.find((r) => r.slug === rootSlug);
  return root?.children.find((c) => c.label === childLabel)?.id || "";
}

function handbookCategoryIds(root: TarkovHandbookRoot): string[] {
  return [root.id, ...root.children.map((c) => c.id)];
}

/** 顶栏叶子入口（比手册一级更细）。 */
export const TARKOV_ITEM_LEAVES: TarkovItemPage[] = [
  {
    slug: "headsets",
    label: "耳机",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [handbookChildId("gear", "耳机")].filter(Boolean),
    types: ["headphones"],
    children: [],
  },
  {
    slug: "helmets",
    label: "头盔",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [],
    types: ["helmet"],
    children: [],
  },
  {
    slug: "glasses",
    label: "眼镜",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [handbookChildId("gear", "眼部装备")].filter(Boolean),
    types: ["glasses"],
    children: [],
  },
  {
    slug: "armors",
    label: "护甲",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [handbookChildId("gear", "防弹衣")].filter(Boolean),
    types: ["armor"],
    children: [],
  },
  {
    slug: "rigs",
    label: "胸挂",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [handbookChildId("gear", "战术胸挂")].filter(Boolean),
    types: ["rig"],
    children: [],
  },
  {
    slug: "backpacks",
    label: "背包",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [handbookChildId("gear", "背包")].filter(Boolean),
    types: ["backpack"],
    children: [],
  },
  {
    slug: "containers",
    label: "容器",
    panel: "catalog",
    parentSlug: "gear",
    categoryIds: [handbookChildId("gear", "容器")].filter(Boolean),
    types: ["container"],
    children: [],
  },
  {
    slug: "grenades",
    label: "手榴弹",
    panel: "catalog",
    parentSlug: "guns",
    categoryIds: [handbookChildId("guns", "投掷物")].filter(Boolean),
    types: ["grenade"],
    children: [],
  },
  {
    slug: "pistol-grips",
    label: "手枪式握把",
    panel: "catalog",
    parentSlug: "weapon-mods",
    categoryIds: [],
    types: ["pistolGrip"],
    children: [],
  },
  {
    slug: "suppressors",
    label: "消音器",
    panel: "catalog",
    parentSlug: "weapon-mods",
    categoryIds: [],
    types: ["suppressor"],
    children: [],
  },
];

export function handbookRootToPage(root: TarkovHandbookRoot): TarkovItemPage {
  const panel: TarkovItemPanel =
    root.panel === "ammo" || root.panel === "guns" ? root.panel : "catalog";
  return {
    slug: root.slug,
    label: root.label,
    panel,
    categoryIds: handbookCategoryIds(root),
    types: root.types,
    children: root.children,
  };
}

export function allItemPages(): TarkovItemPage[] {
  return [
    ...TARKOV_HANDBOOK_ROOTS.map(handbookRootToPage),
    ...TARKOV_ITEM_LEAVES,
  ];
}

export function itemPageBySlug(
  raw: string | null | undefined,
): TarkovItemPage | undefined {
  const key = (raw || "").trim();
  if (!key) return undefined;
  if (key === "gun" || key === "weapons") {
    return allItemPages().find((p) => p.slug === "guns");
  }
  return allItemPages().find((p) => p.slug === key);
}

export function itemDetailHref(typeSlug: string, itemId: string): string {
  return `${ITEMS_BASE_PATH}/${typeSlug}/${encodeURIComponent(itemId)}`;
}

const TYPE_TO_ITEM_SLUG: [string, string][] = [
  ["ammo", "ammo"],
  ["gun", "guns"],
  ["preset", "guns"],
  ["keys", "keys"],
  ["key", "keys"],
  ["headset", "headsets"],
  ["headphones", "headsets"],
  ["helmet", "helmets"],
  ["glasses", "glasses"],
  ["armor", "armors"],
  ["rig", "rigs"],
  ["backpack", "backpacks"],
  ["grenade", "grenades"],
  ["pistolGrip", "pistol-grips"],
  ["silencer", "suppressors"],
  ["suppressor", "suppressors"],
  ["provisions", "provisions"],
  ["meds", "meds"],
  ["container", "containers"],
  ["armorPlate", "armors"],
  ["poster", "battle-pass"],
];

/** 按物品 types 猜手册路径；详情页按 itemId 加载，slug 只影响面包屑。 */
export function itemHrefFromTypes(
  itemId: string,
  types: string[] | undefined,
): string {
  const set = new Set((types || []).map((t) => String(t).trim()));
  for (const [type, slug] of TYPE_TO_ITEM_SLUG) {
    if (set.has(type)) return itemDetailHref(slug, itemId);
  }
  return itemDetailHref("barter", itemId);
}

export function handbookSectionCode(slug: string): string {
  return `DATABASE_SEC_${slug.replace(/-/g, "_").toUpperCase()}`;
}

const IGNORE_CATEGORY_IDS = new Set([
  "54009119af1c881c07000029",
  "566162e44bdc2d3f298b4573",
  "5661632d4bdc2d903d8b456b",
  "566168634bdc2d144c8b456c",
]);

/** 手册分类 id → 本站分类页；泛 Item 节点不链。 */
export function handbookHrefFromCategoryId(id: string): string | null {
  const key = (id || "").trim();
  if (!key || IGNORE_CATEGORY_IDS.has(key)) return null;
  for (const root of TARKOV_HANDBOOK_ROOTS) {
    if (root.id === key) return handbookHref(root);
    if (root.children.some((child) => child.id === key)) {
      const leaf = TARKOV_ITEM_LEAVES.find((page) =>
        page.categoryIds.includes(key),
      );
      return leaf ? itemTypeHref(leaf.slug) : handbookHref(root);
    }
  }
  return null;
}
