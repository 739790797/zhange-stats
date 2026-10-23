/**
 * 弹药 UI 口径族（手枪弹 / PDW / 步枪弹…）——**不是上游分类字段**。
 * 上游只有：itemCategories=`ammo`、handbook=`rounds`/`ammo`、以及 `ammoType`
 *（bullet / buckshot / grenade / flashbang）。
 * 本文件的大类仅按口径白名单做前端筛选便利，勿当成原生分类写入库。
 *
 * @see https://escapefromtarkov.fandom.com/wiki/Ballistics
 */

export type AmmoCategoryId =
  | "pistol"
  | "pdw"
  | "rifle"
  | "shotgun"
  | "other";

export type AmmoCategory = {
  id: AmmoCategoryId;
  label: string;
};

export const AMMO_CATEGORIES: AmmoCategory[] = [
  { id: "pistol", label: "手枪弹" },
  { id: "pdw", label: "PDW" },
  { id: "rifle", label: "步枪弹" },
  { id: "shotgun", label: "霰弹" },
  { id: "other", label: "其它" },
];

/** 默认打开的大类（常用对照） */
export const DEFAULT_AMMO_CATEGORY: AmmoCategoryId = "rifle";

/** 上游 ammoType 展示顺序与中文标签 */
export const AMMO_TYPE_ORDER = [
  "bullet",
  "buckshot",
  "grenade",
  "flashbang",
] as const;

export const AMMO_TYPE_LABELS: Record<string, string> = {
  bullet: "子弹",
  buckshot: "霰弹",
  grenade: "榴弹",
  flashbang: "闪光",
};

export function formatAmmoTypeLabel(ammoType: string): string {
  const key = (ammoType || "").trim();
  if (!key) return "未标注";
  return AMMO_TYPE_LABELS[key] || key;
}

function normKey(caliber: string): string {
  return caliber.trim().toLowerCase().replace(/\s+/g, "");
}

/** 与后端 _BSG_CALIBER_LABELS 解码结果对齐（含旧库残留的 Caliber* key） */
const CATEGORY_BY_KEY: Record<string, AmmoCategoryId> = {
  "1143x23acp": "pistol",
  ".45acp": "pistol",
  "9x18pm": "pistol",
  "9x18mm": "pistol",
  "9x18pmm": "pistol",
  "9x18mmpmm": "pistol",
  "9x19para": "pistol",
  "9x19mm": "pistol",
  "9x21": "pistol",
  "9x21mm": "pistol",
  "9x33r": "pistol",
  ".357magnum": "pistol",
  "7.62x25tt": "pistol",
  "7.62x25mm": "pistol",
  "127x33": "pistol",
  ".50ae": "pistol",
  "20x1mm": "pistol",
  "46x30": "pdw",
  "4.6x30mm": "pdw",
  "57x28": "pdw",
  "5.7x28mm": "pdw",
  "5.45x39": "rifle",
  "5.45x39mm": "rifle",
  "5.56x45nato": "rifle",
  "5.56x45mm": "rifle",
  "58x42": "rifle",
  "5.8x42mm": "rifle",
  "68x51": "rifle",
  "6.8x51mm": "rifle",
  "7.62x35": "rifle",
  ".300blackout": "rifle",
  "7.62x39": "rifle",
  "7.62x39mm": "rifle",
  "7.62x51": "rifle",
  "7.62x51mm": "rifle",
  "7.62x54r": "rifle",
  "7.62x54mmr": "rifle",
  "784x49": "rifle",
  ".308marlinexpress": "rifle",
  "9x39": "rifle",
  "9x39mm": "rifle",
  "93x64": "rifle",
  "9.3x64mm": "rifle",
  "366tkm": "rifle",
  ".366tkm": "rifle",
  "12.7x55mm": "rifle",
  "127x55": "rifle",
  "127x99": "rifle",
  ".50bmg": "rifle",
  "86x70": "rifle",
  ".338lapua": "rifle",
  "12g": "shotgun",
  "12/70": "shotgun",
  "20g": "shotgun",
  "20/70": "shotgun",
  "23x75": "shotgun",
  "23x75mm": "shotgun",
  "26x75": "other",
  "26x75mm": "other",
  "40x46": "other",
  "40x46mm": "other",
  "40mmru": "other",
  "12.7x108mm": "other",
  "127x108": "other",
  "30x29": "other",
  "30x29mm": "other",
  "725": "other",
  "72.5mm": "other",
};

/** 与后端白名单一致；仅用于展示旧库残留 Caliber* */
const PRETTY_LABEL: Record<string, string> = {
  "1143x23acp": ".45 ACP",
  "9x18pm": "9x18mm",
  "9x18pmm": "9x18mm PMM",
  "9x18mmpmm": "9x18mm PMM",
  "9x19para": "9x19mm",
  "9x21": "9x21mm",
  "9x33r": ".357 Magnum",
  "7.62x25tt": "7.62x25mm",
  "46x30": "4.6x30mm",
  "57x28": "5.7x28mm",
  "5.45x39": "5.45x39mm",
  "5.56x45nato": "5.56x45mm",
  "58x42": "5.8x42mm",
  "68x51": "6.8x51mm",
  "7.62x35": ".300 Blackout",
  "7.62x39": "7.62x39mm",
  "7.62x51": "7.62x51mm",
  "7.62x54r": "7.62x54mm R",
  "784x49": ".308 Marlin Express",
  "9x39": "9x39mm",
  "93x64": "9.3x64mm",
  "366tkm": ".366 TKM",
  "127x33": ".50 AE",
  "127x55": "12.7x55mm",
  "127x99": ".50 BMG",
  "86x70": ".338 Lapua",
  "12g": "12/70",
  "20g": "20/70",
  "20x1mm": "20x1mm",
  "23x75": "23x75mm",
  "26x75": "26x75mm",
  "40x46": "40x46mm",
  "40mmru": "40mm RU",
  "127x108": "12.7x108mm",
  "30x29": "30x29mm",
  "725": "72.5mm",
};

function caliberLookupKey(caliber: string): string {
  return normKey(caliber).replace(/^caliber/, "");
}

export function formatCaliberLabel(caliber: string): string {
  const raw = (caliber || "").trim();
  if (!raw) return "—";
  const key = caliberLookupKey(raw);
  if (PRETTY_LABEL[key]) return PRETTY_LABEL[key];
  // 已是后端解码后的展示名，直接显示；未收录 Caliber* 仅剥前缀
  if (/^caliber/i.test(raw)) return key || raw;
  return raw;
}

export function classifyCaliber(caliber: string): AmmoCategoryId {
  const key = caliberLookupKey(caliber);
  const hit = CATEGORY_BY_KEY[key] || CATEGORY_BY_KEY[normKey(caliber)];
  if (hit) return hit;
  // 未收录口径不猜测大类
  return "other";
}

export function calibersInCategory(
  allCalibers: string[],
  category: AmmoCategoryId,
): string[] {
  return allCalibers.filter((c) => classifyCaliber(c) === category);
}
