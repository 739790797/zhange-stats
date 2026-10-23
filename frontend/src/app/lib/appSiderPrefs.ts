const STORAGE_KEY = "zhange.app.sider.v1";

export function parseAppSiderCollapsed(raw: string | null): boolean {
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false" || !raw) return false;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed === "boolean") return parsed;
    if (
      parsed &&
      typeof parsed === "object" &&
      !Array.isArray(parsed) &&
      typeof (parsed as { collapsed?: unknown }).collapsed === "boolean"
    ) {
      return (parsed as { collapsed: boolean }).collapsed;
    }
  } catch {
    /* ignore junk */
  }
  return false;
}

export function loadAppSiderCollapsed(): boolean {
  try {
    return parseAppSiderCollapsed(localStorage.getItem(STORAGE_KEY));
  } catch {
    return false;
  }
}

export function saveAppSiderCollapsed(collapsed: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ collapsed }));
  } catch {
    /* ignore quota / private mode */
  }
}
