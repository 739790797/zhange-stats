import type { EndfieldChar, EndfieldSkill } from "@/api/types";
import { PROPERTY_SKILL_BG } from "./constants";

export function skillBgForChar(char: EndfieldChar) {
  return PROPERTY_SKILL_BG[char.property_name || ""] || "#8a9099";
}

export function formatOwnTs(ts?: number | null) {
  if (!ts) return null;
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("zh-CN");
}

export function isLimited(labelType?: string) {
  const t = (labelType || "").toLowerCase();
  return t.includes("up") || t.includes("limit");
}

export function skillByType(skills: EndfieldSkill[], match: string[]) {
  return skills.find((s) => match.includes(s.skill_type)) || null;
}
