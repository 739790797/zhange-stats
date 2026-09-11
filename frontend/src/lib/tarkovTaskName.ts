/** 任务列表展示名：阵营后缀 + 同名线提示（第几转 / 前置分叉）。 */

export function factionTaskSuffix(value: string | undefined): string {
  const text = (value || "").trim();
  if (!text || text === "Any") return "";
  return ` (${text})`;
}

export function taskLineHintSuffix(
  hint: string | undefined,
  factionName?: string,
): string {
  const text = (hint || "").trim();
  if (!text) return "";
  const faction = (factionName || "").trim();
  if (faction && faction !== "Any" && text === faction) return "";
  return `（${text}）`;
}

export function displayTaskProgressName(task: {
  id: string;
  name?: string | null;
  faction_name?: string | null;
  line_hint?: string | null;
}): string {
  const name = (task.name || task.id).trim() || task.id;
  return `${name}${factionTaskSuffix(task.faction_name || "")}${taskLineHintSuffix(
    task.line_hint || "",
    task.faction_name || "",
  )}`;
}
