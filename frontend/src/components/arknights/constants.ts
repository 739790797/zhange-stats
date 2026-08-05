/** 稀有度底栏 / 描边色（贴近游戏卡面） */
export const RARITY_ACCENT: Record<number, string> = {
  6: "#f5a623",
  5: "#9b59d0",
  4: "#49b3e6",
  3: "#7dce82",
  2: "#9aa0a6",
  1: "#9aa0a6",
};

export const GAME_RES =
  "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main";

export const PROFESSION_CLASS_FILE: Record<string, string> = {
  PIONEER: "class_vanguard.png",
  WARRIOR: "class_guard.png",
  TANK: "class_defender.png",
  SNIPER: "class_sniper.png",
  CASTER: "class_caster.png",
  MEDIC: "class_medic.png",
  SUPPORT: "class_supporter.png",
  SPECIAL: "class_specialist.png",
};

export const COMPARE_MAX = 5;
/** 更接近游戏编队卡比例 */
export const CARD_W = 120;
export const CARD_H = 156;
export const CARD_GAP = 6;
export const LABEL_W = 176;
export const ROLE_UID_STORAGE_KEY = "zhange.arknights.roleUidByMember";

export type SortMode = "catalog" | "level";

export const RARITY_CN: Record<number, string> = {
  6: "六星",
  5: "五星",
  4: "四星",
  3: "三星",
  2: "二星",
  1: "一星",
};
