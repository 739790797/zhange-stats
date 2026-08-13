/** 对齐 tarkov.dev 任务目标：撤离状态文案、不把 ExpBonus* 当撤离点。 */

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
