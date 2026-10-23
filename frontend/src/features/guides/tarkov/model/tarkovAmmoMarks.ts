/** 20°C 海平面音速；与 Wiki / eftforge 亚音速（S）标记一致。 */
export const SOUND_SPEED_MPS = 343;

const TRACER_COLOR_ZH: Record<string, string> = {
  red: "红色",
  green: "绿色",
  yellow: "黄色",
  orange: "橙色",
  white: "白色",
  blue: "蓝色",
  tracerred: "红色",
  tracergreen: "绿色",
  traceryellow: "黄色",
};

export function isSubsonicAmmo(initialSpeed: number | null | undefined): boolean {
  const n = Number(initialSpeed);
  return Number.isFinite(n) && n > 0 && n < SOUND_SPEED_MPS;
}

/** 曳光角标悬浮文案，例如「红色曳光弹」。 */
export function tracerMarkLabel(color: string | null | undefined): string {
  const key = (color || "").trim().toLowerCase();
  const zh = TRACER_COLOR_ZH[key];
  return zh ? `${zh}曳光弹` : "曳光弹";
}

const SUBSONIC_MARK_HINT = "亚音速弹";

export function ammoTraitMarks(row: {
  initial_speed?: number | null;
  tracer?: boolean | null;
  tracer_color?: string | null;
}): { key: "S" | "T"; hint: string }[] {
  const marks: { key: "S" | "T"; hint: string }[] = [];
  if (isSubsonicAmmo(row.initial_speed)) {
    marks.push({ key: "S", hint: SUBSONIC_MARK_HINT });
  }
  if (row.tracer) {
    marks.push({ key: "T", hint: tracerMarkLabel(row.tracer_color) });
  }
  return marks;
}

/** 碎弹率 / 跳弹率：上游 0–1。 */
export function formatChancePct(value: number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "0%";
  const pct = Math.round(n * 1000) / 10;
  const text = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
  return `${text}%`;
}

export const AMMO_COLUMN_HINTS = {
  caliber: "弹药口径。点击可查看可用该口径的枪械。",
  name: "弹药名称。右上角 S 为亚音速弹，T 为曳光弹。",
  pack: "对应的盒装弹药外观。",
  damage: "击中未护甲部位的肉体伤害。",
  penetration: "穿透力，决定打穿护甲的难度。",
  armorDamage: "每次命中护甲的耐久损耗。",
  fragmentation: "击中后破片的概率。破片通常额外造成约 50% 肉体伤害。",
  ricochet: "击中头盔时发生跳弹的概率。护甲一般不判定跳弹。",
  accuracy: "相对默认弹药的精度修正。",
  recoil: "相对默认弹药的后坐力修正。增为更难压，减为更稳。",
  lightBleed: "造成小出血的概率修正。",
  heavyBleed: "造成大出血的概率修正。",
  speed: "枪口初速（米/秒）。低于音速（约 343 m/s）视为亚音速。",
  armorEffect: "对 1–6 级护甲的估算效果，不是游戏内实时演算。",
  armorClass: "护甲等级。色块表示该弹对该级护甲的估算效果。",
} as const;
