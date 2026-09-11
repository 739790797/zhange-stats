/**
 * 仓库/手册搜索侧栏一级分类（BSG handbook.Categories，ParentId 为空，按 Order 升序）。
 * 子类为 ParentId=一级 的直接下级；配件再展开到手册小类（瞄具 / 枪口等）。
 */

export type TarkovHandbookStatus = "ready" | "soon";

export type TarkovHandbookChild = {
  id: string;
  order: number;
  label: string;
  children?: TarkovHandbookChild[];
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
      {
        id: "5b5f750686f774093e6cb503",
        order: 100,
        label: "装备配件",
        children: [
          { id: "5b5f754a86f774094242f19b", order: 100, label: "弹匣" },
          { id: "5b5f757486f774093e6cb507", order: 110, label: "枪托" },
          { id: "5b5f761f86f774094242f1a1", order: 120, label: "手枪式握把" },
          { id: "5b5f755f86f77447ec5d770e", order: 130, label: "导轨" },
          { id: "5b5f751486f77447ec5d770c", order: 140, label: "拉机柄" },
          { id: "5b5f752e86f774093e6cb505", order: 150, label: "榴弹发射器" },
        ],
      },
      {
        id: "5b5f71b386f774093f2ecf11",
        order: 110,
        label: "功能模块",
        children: [
          {
            id: "5b5f73ec86f774093e6cb4fd",
            order: 100,
            label: "瞄具",
            children: [
              { id: "5b5f740a86f77447ec5d7706", order: 100, label: "突击瞄准镜" },
              { id: "5b5f742686f774093e6cb4ff", order: 110, label: "反射式瞄具" },
              { id: "5b5f744786f774094242f197", order: 120, label: "小型反射式瞄具" },
              { id: "5b5f746686f77447ec5d7708", order: 130, label: "机械瞄具" },
              { id: "5b5f748386f774093e6cb501", order: 140, label: "光学瞄具" },
              { id: "5b5f749986f774094242f199", order: 150, label: "特殊瞄具" },
            ],
          },
          {
            id: "5b5f724186f77447ed5636ad",
            order: 110,
            label: "枪口装置",
            children: [
              { id: "5b5f724c86f774093f2ecf15", order: 100, label: "消焰器及制退器" },
              { id: "5b5f72f786f77447ec5d7702", order: 110, label: "枪口转接器" },
              { id: "5b5f731a86f774093e6cb4f9", order: 120, label: "消音器" },
            ],
          },
          {
            id: "5b5f736886f774094242f193",
            order: 120,
            label: "照明激光设备",
            children: [
              { id: "5b5f73ab86f774094242f195", order: 100, label: "手电筒" },
              { id: "5b5f73c486f77447ec5d7704", order: 110, label: "激光瞄准模块" },
            ],
          },
          { id: "5b5f737886f774093e6cb4fb", order: 130, label: "战术组合设备" },
          { id: "5b5f71de86f774093f2ecf13", order: 140, label: "前握把" },
          { id: "5b5f71c186f77409407a7ec0", order: 150, label: "两脚架" },
          { id: "5b5f74cc86f77447ec5d770a", order: 160, label: "辅助零件" },
        ],
      },
      {
        id: "5b5f75b986f77447ec5d7710",
        order: 120,
        label: "基础部件",
        children: [
          { id: "5b5f75c686f774094242f19f", order: 100, label: "枪管" },
          { id: "5b5f75e486f77447ec5d7712", order: 110, label: "护木" },
          { id: "5b5f760586f774093e6cb509", order: 120, label: "导气箍" },
          { id: "5b5f764186f77447ec5d7714", order: 130, label: "机匣和套筒" },
        ],
      },
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

export function walkHandbookChildren(
  nodes: readonly TarkovHandbookChild[] | undefined,
  visit: (node: TarkovHandbookChild, depth: number) => void,
  depth = 1,
): void {
  for (const node of nodes || []) {
    visit(node, depth);
    if (node.children?.length) {
      walkHandbookChildren(node.children, visit, depth + 1);
    }
  }
}

export function findHandbookChild(
  nodes: readonly TarkovHandbookChild[] | undefined,
  id: string,
): TarkovHandbookChild | undefined {
  const key = (id || "").trim();
  if (!key) return undefined;
  for (const node of nodes || []) {
    if (node.id === key) return node;
    const nested = findHandbookChild(node.children, key);
    if (nested) return nested;
  }
  return undefined;
}

export function handbookChildLabels(
  nodes: readonly TarkovHandbookChild[] | undefined,
): string[] {
  const labels: string[] = [];
  walkHandbookChildren(nodes, (node) => {
    labels.push(node.label);
  });
  return labels;
}

export function handbookNodeCategoryIds(node: TarkovHandbookChild): string[] {
  const ids = [node.id];
  walkHandbookChildren(node.children, (child) => {
    ids.push(child.id);
  });
  return ids;
}

function handbookChildId(rootSlug: string, childLabel: string): string {
  const root = TARKOV_HANDBOOK_ROOTS.find((r) => r.slug === rootSlug);
  let found = "";
  walkHandbookChildren(root?.children, (node) => {
    if (!found && node.label === childLabel) found = node.id;
  });
  return found;
}

function handbookCategoryIds(root: TarkovHandbookRoot): string[] {
  const ids = [root.id];
  walkHandbookChildren(root.children, (node) => {
    ids.push(node.id);
  });
  return ids;
}

export const ITEMS_DEFAULT_SLUG = "gear";
export const ITEMS_DEFAULT_PATH = `${ITEMS_BASE_PATH}/${ITEMS_DEFAULT_SLUG}`;

/** 叶子只用于详情 slug、列预设和旧列表跳转，不再作为独立列表页。 */
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
    categoryIds: [handbookChildId("gear", "头部装备")].filter(Boolean),
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
    slug: "ammo-packs",
    label: "弹药包",
    panel: "catalog",
    parentSlug: "ammo",
    categoryIds: [handbookChildId("ammo", "弹药包")].filter(Boolean),
    types: ["ammoBox"],
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
    slug: "melee",
    label: "近战",
    panel: "catalog",
    parentSlug: "guns",
    categoryIds: [handbookChildId("guns", "近战武器")].filter(Boolean),
    types: ["melee"],
    children: [],
  },
  {
    slug: "pistol-grips",
    label: "手枪式握把",
    panel: "catalog",
    parentSlug: "weapon-mods",
    categoryIds: [handbookChildId("weapon-mods", "手枪式握把")].filter(Boolean),
    types: ["pistolGrip"],
    children: [],
  },
  {
    slug: "suppressors",
    label: "消音器",
    panel: "catalog",
    parentSlug: "weapon-mods",
    categoryIds: [handbookChildId("weapon-mods", "消音器")].filter(Boolean),
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

export function leafPageForCategoryId(
  id: string | null | undefined,
): TarkovItemPage | undefined {
  const key = (id || "").trim();
  if (!key) return undefined;
  return TARKOV_ITEM_LEAVES.find((page) => page.categoryIds.includes(key));
}

export function catalogPresetSlug(
  page: TarkovItemPage,
  child: TarkovHandbookChild | null,
): string {
  if (child) {
    const leaf = leafPageForCategoryId(child.id);
    if (leaf) return leaf.slug;
  }
  return page.slug;
}

/** 列表入口：叶子跳到手册一级 `?child=`，一级保持原路径。 */
export function itemListingHref(slug: string): string {
  const page = itemPageBySlug(slug);
  if (!page) return `${ITEMS_BASE_PATH}/${slug}`;
  if (!page.parentSlug) return `${ITEMS_BASE_PATH}/${page.slug}`;
  const parent = handbookRootBySlug(page.parentSlug);
  if (!parent) return `${ITEMS_BASE_PATH}/${page.slug}`;
  const childId = page.categoryIds[0];
  if (!childId) return handbookHref(parent);
  return `${handbookHref(parent)}?child=${encodeURIComponent(childId)}`;
}

export type ItemBrowseKind = "ammo" | "guns" | "catalog";

export function itemBrowseKind(
  page: TarkovItemPage,
  child: TarkovHandbookChild | null,
): ItemBrowseKind {
  if (page.panel === "ammo") {
    return leafPageForCategoryId(child?.id)?.slug === "ammo-packs"
      ? "catalog"
      : "ammo";
  }
  if (page.panel === "guns") {
    const slug = leafPageForCategoryId(child?.id)?.slug;
    if (slug === "grenades" || slug === "melee") return "catalog";
    return "guns";
  }
  return "catalog";
}

export function catalogPageForBrowse(
  page: TarkovItemPage,
  child: TarkovHandbookChild | null,
): TarkovItemPage {
  if (page.panel === "ammo" || page.panel === "guns") {
    const leaf = child ? leafPageForCategoryId(child.id) : undefined;
    if (leaf) return { ...leaf, children: [] };
  }
  return page;
}

export function itemDetailHref(typeSlug: string, itemId: string): string {
  return `${ITEMS_BASE_PATH}/${typeSlug}/${encodeURIComponent(itemId)}`;
}

const TYPE_TO_ITEM_SLUG: [string, string][] = [
  ["ammo", "ammo"],
  ["ammoBox", "ammo-packs"],
  ["gun", "guns"],
  ["melee", "melee"],
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
  ["preset", "guns"],
];

export function itemSlugFromTypes(types: string[] | undefined): string {
  const set = new Set((types || []).map((t) => String(t).trim()));
  for (const [type, slug] of TYPE_TO_ITEM_SLUG) {
    if (set.has(type)) return slug;
  }
  return "barter";
}

/** 按物品 types 猜手册路径；详情页按 itemId 加载，slug 只影响面包屑。 */
export function itemHrefFromTypes(
  itemId: string,
  types: string[] | undefined,
): string {
  return itemDetailHref(itemSlugFromTypes(types), itemId);
}

export function itemTypeLabelFromTypes(
  types: string[] | undefined,
): string {
  const set = new Set((types || []).map((t) => String(t).trim()));
  for (const [type, slug] of TYPE_TO_ITEM_SLUG) {
    if (!set.has(type)) continue;
    const label = itemPageBySlug(slug)?.label || "";
    if (label) return label;
  }
  return "";
}

export function itemTypeHrefFromTypes(
  types: string[] | undefined,
): string | null {
  const set = new Set((types || []).map((t) => String(t).trim()));
  for (const [type, slug] of TYPE_TO_ITEM_SLUG) {
    if (set.has(type)) return itemListingHref(slug);
  }
  return null;
}

const IGNORE_CATEGORY_IDS = new Set([
  "54009119af1c881c07000029",
  "566162e44bdc2d3f298b4573",
  "5661632d4bdc2d903d8b456b",
  "566168634bdc2d144c8b456c",
]);

export function isGenericItemCategoryId(id: string): boolean {
  return IGNORE_CATEGORY_IDS.has((id || "").trim());
}

export type HandbookCategoryHit = {
  id: string;
  label: string;
  order: number;
};

/** 手册 id 取最细分类：更深的子类优先，否则一级。 */
export function handbookCategoryFromIds(
  ids: readonly string[] | null | undefined,
): HandbookCategoryHit | null {
  const set = new Set(
    (ids || []).map((id) => String(id).trim()).filter(Boolean),
  );
  if (!set.size) return null;
  let childHit: HandbookCategoryHit | null = null;
  let childDepth = -1;
  let rootHit: HandbookCategoryHit | null = null;
  for (const root of TARKOV_HANDBOOK_ROOTS) {
    if (set.has(root.id)) {
      const hit = {
        id: root.id,
        label: root.label,
        order: root.order * 1000,
      };
      if (!rootHit || hit.order < rootHit.order) rootHit = hit;
    }
    for (const [index, child] of root.children.entries()) {
      walkHandbookChildren([child], (node, depth) => {
        if (!set.has(node.id)) return;
        const hit = {
          id: node.id,
          label: node.label,
          order: root.order * 1000 + index,
        };
        if (
          !childHit ||
          depth > childDepth ||
          (depth === childDepth && hit.order < childHit.order)
        ) {
          childHit = hit;
          childDepth = depth;
        }
      });
    }
  }
  return childHit ?? rootHit;
}

/** 手册分类 id → 本站分类页；泛 Item 节点不链。 */
export function handbookHrefFromCategoryId(id: string): string | null {
  const key = (id || "").trim();
  if (!key || IGNORE_CATEGORY_IDS.has(key)) return null;
  for (const root of TARKOV_HANDBOOK_ROOTS) {
    if (root.id === key) return handbookHref(root);
    if (!findHandbookChild(root.children, key)) continue;
    return `${handbookHref(root)}?child=${encodeURIComponent(key)}`;
  }
  return null;
}
