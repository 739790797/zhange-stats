/**
 * 枪械口径大类：与弹药 tab 同一套口径映射（手枪 / PDW / 步枪 / 霰弹 / 其它）。
 */
import {
  type AmmoCategoryId,
  AMMO_CATEGORIES,
  DEFAULT_AMMO_CATEGORY,
  calibersInCategory,
  classifyCaliber,
  formatCaliberLabel,
} from "@/lib/tarkovAmmoCategories";

export type GunCategoryId = AmmoCategoryId;

export type GunCategory = {
  id: GunCategoryId;
  label: string;
};

/** 标签去掉「弹」后缀，语义仍是同一口径族 */
export const GUN_CATEGORIES: GunCategory[] = [
  { id: "pistol", label: "手枪" },
  { id: "pdw", label: "PDW" },
  { id: "rifle", label: "步枪" },
  { id: "shotgun", label: "霰弹" },
  { id: "other", label: "其它" },
];

export const DEFAULT_GUN_CATEGORY: GunCategoryId = DEFAULT_AMMO_CATEGORY;

export {
  AMMO_CATEGORIES,
  calibersInCategory,
  classifyCaliber,
  formatCaliberLabel,
};

/** 仅翻译上游 weapon_class；没有对应文案则原样显示，不补造类型 */
export const WEAPON_CLASS_LABELS: Record<string, string> = {
  "assault-rifle": "突击步枪",
  handgun: "手枪",
  shotgun: "霰弹枪",
  "sniper-rifle": "狙击步枪",
  "assault-carbine": "卡宾枪",
  "marksman-rifle": "精确射手步枪",
  smg: "冲锋枪",
  machinegun: "机枪",
  "grenade-launcher": "榴弹发射器",
  revolver: "左轮",
  "rocket-launcher": "火箭筒",
};

export function formatWeaponClass(weaponClass: string): string {
  const key = (weaponClass || "").trim();
  if (!key) return "—";
  return WEAPON_CLASS_LABELS[key] || key;
}

/** 手册武器子类 → dump `weapon_class`；投掷物 / 近战走物品目录，不在这里。 */
const HANDBOOK_GUN_WEAPON_CLASSES: Record<string, string[]> = {
  "5b5f78fc86f77409407a7f90": ["assault-rifle"],
  "5b5f796a86f774093f2ed3c0": ["smg"],
  "5b5f794b86f77409407a7f92": ["shotgun"],
  "5b5f79a486f77409407a7f94": ["machinegun"],
  "5b5f78e986f77447ed5636b1": ["assault-carbine"],
  "5b5f79d186f774093f2ed3c2": ["grenade-launcher"],
  "5b5f791486f774093f2ed3be": ["marksman-rifle"],
  "5b5f792486f77447ed5636b3": ["handgun", "revolver"],
  "5b5f798886f77447ed5636b5": ["sniper-rifle"],
  "5b5f79eb86f77447ed5636b7": ["rocket-launcher"],
};

export function weaponClassesForHandbookChildId(
  id: string | null | undefined,
): string[] | undefined {
  const key = (id || "").trim();
  if (!key) return undefined;
  return HANDBOOK_GUN_WEAPON_CLASSES[key];
}
