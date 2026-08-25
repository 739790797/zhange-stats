const STORAGE_KEY = "zhange.guides.minecraft.modTools.expanded.v1";

export function parseModToolExpandedMap(raw: string | null): Record<string, boolean> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: Record<string, boolean> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof key === "string" && key && typeof value === "boolean") {
        out[key] = value;
      }
    }
    return out;
  } catch {
    return {};
  }
}

export function resolveModToolExpanded(
  present: boolean,
  saved: boolean | undefined,
): boolean {
  if (!present) return false;
  if (saved === undefined) return true;
  return saved;
}

export function loadModToolExpandedMap(): Record<string, boolean> {
  try {
    return parseModToolExpandedMap(localStorage.getItem(STORAGE_KEY));
  } catch {
    return {};
  }
}

export function saveModToolExpanded(toolId: string, expanded: boolean) {
  const id = (toolId || "").trim();
  if (!id) return;
  const next = { ...loadModToolExpandedMap(), [id]: expanded };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota / private mode */
  }
}

export function readModToolExpanded(toolId: string, present: boolean): boolean {
  const saved = loadModToolExpandedMap()[toolId];
  return resolveModToolExpanded(present, saved);
}
