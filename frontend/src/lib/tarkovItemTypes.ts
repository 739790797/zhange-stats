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
    status: "soon",
    children: [],
  },
  {
    id: "5b619f1a86f77450a702a6f3",
    order: 1,
    label: "任务物品",
    slug: "quest-items",
    status: "soon",
    children: [],
  },
  {
    id: "5b5f78b786f77447ed5636af",
    order: 2,
    label: "货币",
    slug: "money",
    status: "soon",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b343",
    order: 3,
    label: "地图",
    slug: "maps",
    status: "soon",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b345",
    order: 4,
    label: "特殊装备",
    slug: "special-equipment",
    status: "soon",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b341",
    order: 5,
    label: "情报物品",
    slug: "info-items",
    status: "soon",
    children: [],
  },
  {
    id: "5b47574386f77428ca22b342",
    order: 6,
    label: "钥匙",
    slug: "keys",
    status: "soon",
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
    status: "soon",
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
    status: "soon",
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
    status: "soon",
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
    status: "soon",
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
    status: "soon",
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
