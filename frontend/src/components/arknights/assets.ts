import { GAME_RES, PROFESSION_CLASS_FILE } from "./constants";

export function eliteIconSrc(phase: number) {
  const p = Math.max(0, Math.min(2, phase | 0));
  return `/arknights/elite_${p}.png`;
}

export function professionIconSrc(profession: string) {
  const file = PROFESSION_CLASS_FILE[profession] || "class_caster.png";
  return `/arknights/${file}`;
}

export function portraitSrc(charId: string, evolvePhase: number) {
  const stage = evolvePhase >= 2 ? 2 : 1;
  return `${GAME_RES}/portrait/${charId}_${stage}.png`;
}
