import { useCallback, useState } from "react";

const STORAGE_KEY = "zhange.guides.tarkov.raidDock.v1";
export const TARKOV_RAID_DOCK_DESKTOP_MQ = "(min-width: 981px)";

export function parseTarkovRaidDockOpen(
  raw: string | null,
  fallback = true,
): boolean {
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false") return false;
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed === "boolean") return parsed;
    if (
      parsed &&
      typeof parsed === "object" &&
      !Array.isArray(parsed) &&
      typeof (parsed as { open?: unknown }).open === "boolean"
    ) {
      return (parsed as { open: boolean }).open;
    }
  } catch {
    /* ignore junk */
  }
  return fallback;
}

export function loadTarkovRaidDockOpen(): boolean {
  try {
    return parseTarkovRaidDockOpen(localStorage.getItem(STORAGE_KEY), true);
  } catch {
    return true;
  }
}

export function saveTarkovRaidDockOpen(open: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ open }));
  } catch {
    /* ignore quota / private mode */
  }
}

export function isTarkovRaidDockDesktop(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia(TARKOV_RAID_DOCK_DESKTOP_MQ).matches
  );
}

/** 桌面记住开关；窄屏仍默认收起（底部抽屉）。 */
export function initialTarkovRaidDockOpen(): boolean {
  if (typeof window === "undefined") return false;
  if (!isTarkovRaidDockDesktop()) return false;
  return loadTarkovRaidDockOpen();
}

export function persistTarkovRaidDockOpen(open: boolean) {
  if (!isTarkovRaidDockDesktop()) return;
  saveTarkovRaidDockOpen(open);
}

export function useTarkovRaidDockOpen() {
  const [dockOpen, setDockOpenState] = useState(initialTarkovRaidDockOpen);
  const setDockOpen = useCallback(
    (next: boolean | ((prev: boolean) => boolean)) => {
      setDockOpenState((prev) => {
        const value = typeof next === "function" ? next(prev) : next;
        persistTarkovRaidDockOpen(value);
        return value;
      });
    },
    [],
  );
  return [dockOpen, setDockOpen] as const;
}
