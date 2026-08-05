import { ROLE_UID_STORAGE_KEY } from "./constants";

export function loadRoleUidByMember(): Record<number, string> {
  try {
    const raw = localStorage.getItem(ROLE_UID_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const out: Record<number, string> = {};
    for (const [key, value] of Object.entries(parsed)) {
      const id = Number(key);
      if (!Number.isFinite(id) || typeof value !== "string" || !value.trim()) {
        continue;
      }
      out[id] = value.trim();
    }
    return out;
  } catch {
    return {};
  }
}

export function saveRoleUidByMember(map: Record<number, string>) {
  try {
    localStorage.setItem(ROLE_UID_STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore quota / private mode */
  }
}
