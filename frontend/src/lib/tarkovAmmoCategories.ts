/**
 * 口径分类对齐官方 Wiki Ballistics 快选：
 * Pistol / PDW / Rifle / Shotgun / Other
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

function normKey(caliber: string): string {
  return caliber.trim().toLowerCase().replace(/\s+/g, "");
}

/** 兼容旧库乱名与新同步展示名 */
const CATEGORY_BY_KEY: Record<string, AmmoCategoryId> = {
  "1143x23acp": "pistol",
  ".45acp": "pistol",
  "9x18pm": "pistol",
  "9x18mm": "pistol",
  "9x19para": "pistol",
  "9x19mm": "pistol",
  "9x21": "pistol",
  "9x21mm": "pistol",
  "9x33r": "pistol",
  ".357magnum": "pistol",
  "7.62x25tt": "pistol",
  "7.62x25mm": "pistol",
  "46x30": "pdw",
  "4.6x30mm": "pdw",
  "57x28": "pdw",
  "5.7x28mm": "pdw",
  "5.45x39": "rifle",
  "5.45x39mm": "rifle",
  "5.56x45nato": "rifle",
  "5.56x45mm": "rifle",
  "7.62x35": "rifle",
  ".300blackout": "rifle",
  "7.62x39": "rifle",
  "7.62x39mm": "rifle",
  "7.62x51": "rifle",
  "7.62x51mm": "rifle",
  "7.62x54r": "rifle",
  "7.62x54mmr": "rifle",
  "9x39": "rifle",
  "9x39mm": "rifle",
  "366tkm": "rifle",
  ".366tkm": "rifle",
  "1.27x55": "rifle",
  "12.7x55mm": "rifle",
  "86x70": "rifle",
  ".338lapua": "rifle",
  "12g": "shotgun",
  "12/70": "shotgun",
  "20g": "shotgun",
  "20/70": "shotgun",
  "23x75": "shotgun",
  "23x75mm": "shotgun",
  "40x46": "other",
  "40x46mm": "other",
  "40mmru": "other",
  "1.27x108": "other",
  "12.7x108mm": "other",
  "30x29": "other",
  "30x29mm": "other",
};

const PRETTY_LABEL: Record<string, string> = {
  "1143x23acp": ".45 ACP",
  "9x18pm": "9x18mm",
  "9x19para": "9x19mm",
  "9x21": "9x21mm",
  "9x33r": ".357 Magnum",
  "7.62x25tt": "7.62x25mm",
  "46x30": "4.6x30mm",
  "57x28": "5.7x28mm",
  "5.45x39": "5.45x39mm",
  "5.56x45nato": "5.56x45mm",
  "7.62x35": ".300 Blackout",
  "7.62x39": "7.62x39mm",
  "7.62x51": "7.62x51mm",
  "7.62x54r": "7.62x54mm R",
  "9x39": "9x39mm",
  "366tkm": ".366 TKM",
  "1.27x55": "12.7x55mm",
  "86x70": ".338 Lapua",
  "12g": "12/70",
  "20g": "20/70",
  "23x75": "23x75mm",
  "40x46": "40x46mm",
  "40mmru": "40mm RU",
  "1.27x108": "12.7x108mm",
  "30x29": "30x29mm",
};

export function formatCaliberLabel(caliber: string): string {
  return PRETTY_LABEL[normKey(caliber)] || caliber;
}

export function classifyCaliber(caliber: string): AmmoCategoryId {
  const key = normKey(caliber);
  const hit = CATEGORY_BY_KEY[key];
  if (hit) return hit;

  if (/9x18|9x19|9x21|7\.62x25|\.45|45acp|357|tokarev|makarov|para/.test(key)) {
    return "pistol";
  }
  if (/4\.?6x30|5\.?7x28|46x30|57x28/.test(key)) return "pdw";
  if (/12g|20g|12\/70|20\/70|23x75|shotgun/.test(key)) return "shotgun";
  if (/40x46|40mm|12\.?7x108|1\.27x108|grenade|30x29/.test(key)) {
    return "other";
  }
  if (
    /5\.45|5\.56|7\.62x(35|39|51|54)|9x39|\.300|\.338|366|12\.?7x55|1\.27x55|86x70|blackout|lapua/.test(
      key,
    )
  ) {
    return "rifle";
  }
  return "other";
}

export function calibersInCategory(
  allCalibers: string[],
  category: AmmoCategoryId,
): string[] {
  return allCalibers.filter((c) => classifyCaliber(c) === category);
}
