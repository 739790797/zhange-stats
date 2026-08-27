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
