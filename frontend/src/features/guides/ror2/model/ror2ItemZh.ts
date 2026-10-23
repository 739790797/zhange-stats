import { ror2ExpansionName } from "@/features/guides/ror2/model/ror2Expansion";

export function ror2ItemExpansionZh(id: string, fallback = ""): string {
  return ror2ExpansionName(id, fallback);
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
