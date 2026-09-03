/** 对齐 tarkov.dev 任务目标：撤离状态文案、不把 ExpBonus* 当撤离点。 */

/** 上游 objective.type → 列表短标识。未知 type 原样展示。 */
export const TARKOV_OBJECTIVE_TYPE_LABELS: Record<string, string> = {
  shoot: "击杀",
  findItem: "找到",
  findQuestItem: "捡取",
  giveItem: "上交",
  giveQuestItem: "上交任务物",
  plantItem: "藏匿",
  plantQuestItem: "藏匿任务物",
  mark: "标记",
  visit: "前往",
  extract: "撤离",
  useItem: "使用",
  buildWeapon: "改装",
  sellItem: "出售",
  haveItem: "持有",
  skill: "技能",
  traderLevel: "商人等级",
  traderStanding: "商人声望",
  playerLevel: "等级",
  hideoutStation: "藏身处",
  taskStatus: "关联任务",
  experience: "状态",
  dialogue: "对话",
  globalVariable: "限制",
};

/** 列表芯片展示顺序（已知 type 在前）。 */
export const TARKOV_OBJECTIVE_TYPE_ORDER: string[] = [
  "shoot",
  "findItem",
  "findQuestItem",
  "giveItem",
  "giveQuestItem",
  "plantItem",
  "plantQuestItem",
  "mark",
  "visit",
  "extract",
  "useItem",
  "buildWeapon",
  "sellItem",
  "haveItem",
  "skill",
  "traderLevel",
  "traderStanding",
  "playerLevel",
  "hideoutStation",
  "taskStatus",
  "experience",
  "dialogue",
  "globalVariable",
];

const OBJECTIVE_TYPE_RANK = new Map(
  TARKOV_OBJECTIVE_TYPE_ORDER.map((type, index) => [type, index]),
);

export function tarkovObjectiveTypeLabel(type: string): string {
  const key = type.trim();
  if (!key) return "";
  return TARKOV_OBJECTIVE_TYPE_LABELS[key] || key;
}

export function tarkovObjectiveTypeTone(type: string): string {
  const key = type.trim();
  if (key && OBJECTIVE_TYPE_RANK.has(key)) return key;
  return "unknown";
}

export function orderObjectiveTypes(types: string[] | null | undefined): string[] {
  const seen = new Set<string>();
  const uniq: string[] = [];
  for (const raw of types || []) {
    const key = String(raw || "").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    uniq.push(key);
  }
  return uniq.sort((a, b) => {
    const ra = OBJECTIVE_TYPE_RANK.get(a) ?? TARKOV_OBJECTIVE_TYPE_ORDER.length;
    const rb = OBJECTIVE_TYPE_RANK.get(b) ?? TARKOV_OBJECTIVE_TYPE_ORDER.length;
    if (ra !== rb) return ra - rb;
    return a.localeCompare(b);
  });
}


export const TARKOV_EXIT_STATUS_LABELS: Record<string, string> = {
  Survived: "幸存",
  Runner: "匆匆逃离",
  RunThrough: "匆匆逃离",
  MissingInAction: "失踪",
  MIA: "失踪",
  Killed: "阵亡",
  KIA: "阵亡",
  Left: "离开",
  Transit: "转移",
};

const EXP_BONUS_RE = /^ExpBonus(.+)$/i;

function canonicalizeExitStatus(token: string): string | null {
  let raw = token.trim();
  if (!raw) return null;
  const bonus = raw.match(EXP_BONUS_RE);
  if (bonus) raw = bonus[1];
  const key = raw.replace(/[\s_-]/g, "").toLowerCase();
  const aliases: Record<string, string> = {
    survived: "Survived",
    runner: "Runner",
    runthrough: "Runner",
    missinginaction: "MissingInAction",
    mia: "MissingInAction",
    killed: "Killed",
    kia: "Killed",
    left: "Left",
    transit: "Transit",
  };
  return aliases[key] || null;
}

export function tarkovExitStatusLabel(value: string): string {
  const canon = canonicalizeExitStatus(value) || value.trim();
  return TARKOV_EXIT_STATUS_LABELS[canon] || canon;
}

export function formatTaskExtractLines(obj: {
  exit_status?: string[] | null;
  exit_name?: string | null;
  count?: number | null;
}): string[] {
  const statuses: string[] = [];
  const add = (token: string) => {
    const canon = canonicalizeExitStatus(token) || token.trim();
    if (canon && !statuses.includes(canon)) statuses.push(canon);
  };
  for (const raw of obj.exit_status || []) add(String(raw));
  const leftover: string[] = [];
  for (const part of (obj.exit_name || "").split(/[&,|/]+/)) {
    const token = part.trim();
    if (!token) continue;
    if (canonicalizeExitStatus(token)) add(token);
    else leftover.push(token);
  }
  let exitName = leftover[0] || "";
  if (exitName.includes("ExpBonus")) exitName = "";

  const lines: string[] = [];
  if (statuses.length) {
    const joined = statuses.map(tarkovExitStatusLabel).join("或");
    if (obj.count && obj.count > 1) {
      lines.push(`撤离 ${obj.count} 次，状态为：${joined}`);
    } else {
      lines.push(`以状态撤离：${joined}`);
    }
  }
  if (exitName) lines.push(`使用撤离点：${exitName}`);
  return lines;
}

export const TARKOV_BODY_PART_LABELS: Record<string, string> = {
  Head: "头部",
  Thorax: "胸腔",
  Stomach: "胃部",
  LeftArm: "左臂",
  RightArm: "右臂",
  LeftLeg: "左腿",
  RightLeg: "右腿",
};

export const TARKOV_SHOT_TYPE_LABELS: Record<string, string> = {
  Kill: "击杀",
  Damage: "造成伤害",
};

const COMPARE_SYMBOL: Record<string, string> = {
  ">=": "≥",
  "<=": "≤",
  ">": ">",
  "<": "<",
  "=": "=",
  "==": "=",
};

const ATTRIBUTE_LABELS: Record<string, string> = {
  ergonomics: "人机",
  recoil: "后坐",
  accuracy: "精度",
  muzzleVelocity: "初速",
};

const EFFECT_LABELS: Record<string, string> = {
  Pain: "疼痛",
  Fracture: "骨折",
  Contusion: "震荡",
  LightBleeding: "轻微出血",
  HeavyBleeding: "严重出血",
};

export type TaskCompareLike = {
  compare_method?: string | null;
  value?: number | null;
};

export type TaskHealthEffectLike = {
  body_parts?: string[] | null;
  effects?: string[] | null;
  time?: TaskCompareLike | null;
};

export type TaskAttributeLike = {
  name?: string | null;
  compare_method?: string | null;
  value?: number | null;
};

export type TaskNamedRefLike = {
  id?: string | null;
  slug?: string | null;
  name?: string | null;
};

export function formatTaskCompare(
  method?: string | null,
  value?: number | null,
): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  const n = Number(value);
  const shown = Number.isInteger(n) ? String(n) : String(n);
  const key = (method || "").trim();
  const op = COMPARE_SYMBOL[key] || key;
  return op ? `${op}${shown}` : shown;
}

export function tarkovBodyPartLabel(value: string): string {
  const key = value.trim();
  return TARKOV_BODY_PART_LABELS[key] || key;
}

export function formatTaskDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "";
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  if (seconds < 3600) {
    const mins = Math.round(seconds / 60);
    return `${mins} 分钟`;
  }
  const hours = Math.floor(seconds / 3600);
  const mins = Math.round((seconds % 3600) / 60);
  if (mins <= 0) return `${hours} 小时`;
  return `${hours} 小时 ${mins} 分钟`;
}

export function formatTaskDelay(
  min?: number | null,
  max?: number | null,
): string {
  const lo = min == null || min <= 0 ? 0 : min;
  const hi = max == null || max <= 0 ? 0 : max;
  if (!lo && !hi) return "";
  if (lo && hi && lo !== hi) {
    const a = formatTaskDuration(lo);
    const b = formatTaskDuration(hi);
    return a && b ? `完成后等待 ${a}–${b}` : "";
  }
  const text = formatTaskDuration(lo || hi);
  return text ? `完成后等待 ${text}` : "";
}

export function taskRequirementStatusLabel(status: string): string {
  const key = status.trim().toLowerCase();
  if (key === "complete" || key === "completed") return "需完成";
  if (key === "active" || key === "started") return "需进行中";
  if (key === "fail" || key === "failed") return "需失败";
  return status.trim();
}

export function taskUnlockStatusLabel(status: string): string {
  const key = status.trim().toLowerCase();
  if (key === "complete" || key === "completed") return "完成后可接";
  if (key === "active" || key === "started") return "进行中可接";
  if (key === "fail" || key === "failed") return "失败后可接";
  return status.trim();
}

function joinLabels(values: string[]): string {
  return values.filter(Boolean).join("、");
}

function healthEffectLine(prefix: string, raw?: TaskHealthEffectLike | null): string {
  if (!raw) return "";
  const parts = (raw.body_parts || []).map((row) => tarkovBodyPartLabel(String(row)));
  const effects = (raw.effects || []).map((row) => EFFECT_LABELS[row.trim()] || row.trim());
  const bits: string[] = [];
  if (parts.length) bits.push(joinLabels(parts));
  if (effects.length) bits.push(joinLabels(effects));
  const time = formatTaskCompare(raw.time?.compare_method, raw.time?.value);
  if (time) bits.push(`持续 ${time} 秒`);
  return bits.length ? `${prefix}${bits.join(" · ")}` : "";
}

function namedLabel(ref: TaskNamedRefLike | null | undefined): string {
  const name = (ref?.name || "").trim();
  const ident = (ref?.id || "").trim();
  if (name && name !== ident) return name;
  return name || ident;
}

export function formatTaskObjectiveExtraLines(obj: {
  count?: number | null;
  target_names?: string[] | null;
  body_parts?: string[] | null;
  shot_type?: string | null;
  distance?: TaskCompareLike | null;
  time_from_hour?: number | null;
  time_until_hour?: number | null;
  dog_tag_level?: number | null;
  min_durability?: number | null;
  max_durability?: number | null;
  skill_name?: string | null;
  skill_level?: number | null;
  player_level?: number | null;
  zone_names?: string[] | null;
  attributes?: TaskAttributeLike[] | null;
  health_effect?: TaskHealthEffectLike | null;
  player_health_effect?: TaskHealthEffectLike | null;
  enemy_health_effect?: TaskHealthEffectLike | null;
  contains_category?: TaskNamedRefLike[] | null;
}): string[] {
  const lines: string[] = [];
  if (obj.count != null && obj.count > 1) {
    lines.push(`数量 ×${obj.count}`);
  }
  const targets = (obj.target_names || []).map((row) => String(row).trim()).filter(Boolean);
  if (targets.length) lines.push(`目标：${joinLabels(targets)}`);
  const parts = (obj.body_parts || []).map((row) => tarkovBodyPartLabel(String(row)));
  if (parts.length) lines.push(`部位：${joinLabels(parts)}`);
  const shot = (obj.shot_type || "").trim();
  if (shot) lines.push(`方式：${TARKOV_SHOT_TYPE_LABELS[shot] || shot}`);
  const distance = formatTaskCompare(obj.distance?.compare_method, obj.distance?.value);
  if (distance) lines.push(`距离 ${distance} m`);
  if (obj.time_from_hour != null || obj.time_until_hour != null) {
    const from = obj.time_from_hour == null ? "?" : String(obj.time_from_hour).padStart(2, "0");
    const until = obj.time_until_hour == null ? "?" : String(obj.time_until_hour).padStart(2, "0");
    lines.push(`游戏内时段 ${from}:00–${until}:00`);
  }
  if (obj.dog_tag_level != null && obj.dog_tag_level > 0) {
    lines.push(`狗牌等级 ≥${obj.dog_tag_level}`);
  }
  if (obj.min_durability != null || obj.max_durability != null) {
    const lo = obj.min_durability == null ? "0" : String(obj.min_durability);
    const hi = obj.max_durability == null ? "" : String(obj.max_durability);
    lines.push(hi ? `耐久 ${lo}–${hi}%` : `耐久 ≥${lo}%`);
  }
  const skill = (obj.skill_name || "").trim();
  if (skill) {
    lines.push(
      obj.skill_level != null ? `技能 ${skill} ${obj.skill_level} 级` : `技能 ${skill}`,
    );
  }
  if (obj.player_level != null) lines.push(`PMC 等级 ${obj.player_level}`);
  const zones = (obj.zone_names || []).map((row) => String(row).trim()).filter(Boolean);
  if (zones.length) lines.push(`区域：${joinLabels(zones)}`);
  for (const attr of obj.attributes || []) {
    const name = ATTRIBUTE_LABELS[(attr.name || "").trim()] || (attr.name || "").trim();
    const cmp = formatTaskCompare(attr.compare_method, attr.value);
    if (name && cmp) lines.push(`${name} ${cmp}`);
  }
  const health = healthEffectLine("自身状态：", obj.health_effect || obj.player_health_effect);
  if (health) lines.push(health);
  const enemy = healthEffectLine("目标状态：", obj.enemy_health_effect);
  if (enemy) lines.push(enemy);
  const cats = (obj.contains_category || [])
    .map((row) => namedLabel(row))
    .filter(Boolean);
  if (cats.length) lines.push(`配件分类：${joinLabels(cats)}`);
  return lines;
}
