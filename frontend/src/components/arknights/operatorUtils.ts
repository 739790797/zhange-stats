import type { ArknightsOwnedChar } from "@/api/types";

export const POTENTIAL_ROMAN = ["", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"];

export function evolveLabel(phase: number) {
  if (phase >= 2) return "精二";
  if (phase >= 1) return "精一";
  return "精零";
}

export function moduleEquips(owned: ArknightsOwnedChar) {
  return (owned.equips || []).filter(
    (e) => !e.locked && e.type_icon && e.type_icon !== "original",
  );
}
