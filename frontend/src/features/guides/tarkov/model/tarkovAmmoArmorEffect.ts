/**
 * 弹药对 1–6 级护甲效果（对齐 Wiki Ballistics / NFA 0–6 档语义）。
 * 由穿透力 + 对甲伤害估算，非游戏内实时演算，允许与 Wiki 个别格子差一档。
 */

export type ArmorEffectLevel = 0 | 1 | 2 | 3 | 4 | 5 | 6;

/** Wiki 档位中文（短标签，适合色块） */
export const ARMOR_EFFECT_LABELS: Record<ArmorEffectLevel, string> = {
  0: "无效",
  1: "勉强",
  2: "扫射",
  3: "略好",
  4: "有效",
  5: "很好",
  6: "无视",
};

/** 接近 Wiki 表的红→绿色阶 */
export const ARMOR_EFFECT_COLORS: Record<
  ArmorEffectLevel,
  { bg: string; fg: string }
> = {
  0: { bg: "#6d1010", fg: "#ffffff" },
  1: { bg: "#8f2a14", fg: "#ffffff" },
  2: { bg: "#a34818", fg: "#ffffff" },
  3: { bg: "#a35f16", fg: "#ffffff" },
  4: { bg: "#6b7024", fg: "#ffffff" },
  5: { bg: "#3d7a2a", fg: "#ffffff" },
  6: { bg: "#2f9b32", fg: "#ffffff" },
};

/** 满耐久下的等效护甲抗力（社区常用 BSG 近似） */
function effectiveResist(armorClass: number, durabilityPct: number): number {
  const dur = Math.max(0, Math.min(100, durabilityPct));
  return (121 - 5000 / (45 + dur * 2)) * armorClass * 0.1;
}

/** 单发穿透概率 0–1 */
export function estimatePenChance(
  penetration: number,
  armorClass: number,
  durabilityPct = 100,
): number {
  const resist = effectiveResist(armorClass, durabilityPct);
  const gap = penetration - resist;
  if (gap >= 0) return Math.min(0.99, 0.9 + Math.min(0.09, gap * 0.01));
  if (gap <= -15) return 0;
  return Math.min(1, Math.max(0, 0.004 * (15 + gap) ** 2));
}

function durabilityLossPct(
  penetration: number,
  armorClass: number,
  armorDamagePct: number,
): number {
  // 简化：按对甲%与穿透掉耐久，忽略材质差
  const points = Math.max(
    1,
    penetration * (armorDamagePct / 100) * 0.45 * (0.7 + 0.05 * armorClass),
  );
  const maxDur = 60;
  return (points / maxDur) * 100;
}

/** 期望「被护甲挡住」的发数（首发穿透前），再映射到 Wiki 0–6 */
function expectedBlockedShots(
  penetration: number,
  armorClass: number,
  armorDamagePct: number,
): number {
  let dur = 100;
  let expected = 0;
  let alive = 1;
  for (let i = 0; i < 40 && alive > 1e-4 && dur > 0; i++) {
    const p = estimatePenChance(penetration, armorClass, dur);
    expected += alive * (1 - p);
    alive *= 1 - p;
    dur = Math.max(
      0,
      dur - durabilityLossPct(penetration, armorClass, armorDamagePct),
    );
  }
  if (alive > 0.25) return 30;
  return expected;
}

function levelFromBlocked(
  blocked: number,
  firstShotChance: number,
): ArmorEffectLevel {
  // Wiki：6 = 首发穿透率通常 >80% / 平均挡住 <1
  if (firstShotChance >= 0.8 || blocked < 1) return 6;
  if (blocked < 3) return 5;
  if (blocked < 5) return 4;
  if (blocked < 9) return 3;
  if (blocked < 13) return 2;
  if (blocked < 20) return 1;
  return 0;
}

export function armorEffectLevel(
  penetration: number,
  armorClass: number,
  armorDamagePct: number,
): ArmorEffectLevel {
  const pen = Math.max(0, Number(penetration) || 0);
  const ad = Math.max(0, Number(armorDamagePct) || 0);
  const cls = Math.min(6, Math.max(1, Math.round(armorClass)));
  const blocked = expectedBlockedShots(pen, cls, ad);
  const first = estimatePenChance(pen, cls, 100);
  return levelFromBlocked(blocked, first);
}

export function armorEffectsForAmmo(
  penetration: number,
  armorDamagePct: number,
): ArmorEffectLevel[] {
  return [1, 2, 3, 4, 5, 6].map((c) =>
    armorEffectLevel(penetration, c, armorDamagePct),
  );
}
