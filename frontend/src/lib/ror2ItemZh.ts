/** 游戏语言文件没有这些词。物品列表自己的第二层中文。 */
const RARITY_ZH: Record<string, string> = {
  Common: "普通",
  Uncommon: "优秀",
  Legendary: "传说",
  Boss: "首领",
  Lunar: "月球",
  Void: "虚空",
  Meal: "料理",
  Hallowed: "圣洁",
  Hex: "咒印",
  Page: "书页",
  Untiered: "未分级",
  Equipment: "装备",
  "Lunar Equipment": "月球装备",
  "Elite Equipment": "精英装备",
};

const STACK_ZH: Record<string, string> = {
  Linear: "线性",
  Exponential: "指数",
  Hyperbolic: "双曲",
  Reciprocal: "倒数",
  None: "无",
  Special: "特殊",
};

/** Steam 简体商店名。物品列表的资料片筛选用，不回写到 Wiki 原文。 */
const EXPANSION_ZH: Record<string, string> = {
  SotV: "虚空幸存者",
  SotS: "风暴探寻者",
  AC: "合金意念",
  HC: "万象归衡",
};

export function ror2ItemRarityZh(id: string): string {
  return RARITY_ZH[id] ?? id;
}

export function ror2ItemStackZh(stack: string): string {
  if (!stack) return "";
  return stack
    .split(" / ")
    .map((part) => STACK_ZH[part] ?? part)
    .join(" / ");
}

export function ror2ItemExpansionZh(id: string, fallback = ""): string {
  if (id === "base") return "本体";
  return EXPANSION_ZH[id] ?? fallback;
}

/** 游戏语言文件 LOADOUT_SKILL_*。没给的分组保持原文。 */
const LOADOUT_SKILL_ZH: Record<string, string> = {
  Primary: "主要技能",
  Secondary: "次要技能",
  Utility: "辅助技能",
  Special: "特殊技能",
  Misc: "其他",
};

const LOADOUT_SKILL_ORDER = ["Primary", "Secondary", "Utility", "Special", "Misc"] as const;

export function ror2LoadoutSkillZh(slot: string): string {
  return LOADOUT_SKILL_ZH[slot] ?? slot;
}

export function ror2LoadoutSkillRank(slot: string): number {
  const index = LOADOUT_SKILL_ORDER.indexOf(slot as (typeof LOADOUT_SKILL_ORDER)[number]);
  return index === -1 ? LOADOUT_SKILL_ORDER.length : index;
}
