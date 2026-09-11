/** 个人中心 PMC 阵营：本机按 PVP/PVE 记住，任务列表只显示 Any + 本阵营。 */

import { useCallback, useSyncExternalStore } from "react";
import {
  getTarkovGameMode,
  useTarkovGameMode,
  type TarkovGameMode,
} from "@/lib/tarkovGameMode";

export const TARKOV_PMC_FACTION_STORAGE_KEY =
  "zhange.guides.tarkov.pmcFaction.v1";

export const TARKOV_PMC_FACTIONS = ["bear", "usec"] as const;

export type TarkovPmcFaction = (typeof TARKOV_PMC_FACTIONS)[number];

export type TarkovPmcFactionChoice = TarkovPmcFaction | "";

const FACTION_LABEL: Record<TarkovPmcFaction, string> = {
  bear: "BEAR",
  usec: "USEC",
};

type FactionMap = Partial<Record<TarkovGameMode, TarkovPmcFaction>>;

let cachedRaw: string | null = null;
let cachedMap: FactionMap = {};
const listeners = new Set<() => void>();

export function parseTarkovPmcFaction(raw: unknown): TarkovPmcFactionChoice {
  const text = String(raw || "")
    .trim()
    .toLowerCase();
  if (text === "bear" || text === "usec") return text;
  return "";
}

export function tarkovPmcFactionLabel(
  faction: TarkovPmcFactionChoice,
): string {
  if (!faction) return "";
  return FACTION_LABEL[faction];
}

export function taskVisibleForFaction(
  factionName: string | null | undefined,
  selected: TarkovPmcFactionChoice,
): boolean {
  if (!selected) return true;
  const name = (factionName || "").trim().toLowerCase();
  if (!name || name === "any") return true;
  return name === selected;
}

export function filterTasksByFaction<
  T extends { faction_name?: string | null },
>(rows: readonly T[], selected: TarkovPmcFactionChoice): T[] {
  if (!selected) return [...rows];
  return rows.filter((row) => taskVisibleForFaction(row.faction_name, selected));
}

function parseMap(raw: string | null): FactionMap {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      const single = parseTarkovPmcFaction(parsed);
      return single ? { pvp: single, pve: single } : {};
    }
    const record = parsed as Record<string, unknown>;
    const out: FactionMap = {};
    const pvp = parseTarkovPmcFaction(record.pvp);
    const pve = parseTarkovPmcFaction(record.pve);
    if (pvp) out.pvp = pvp;
    if (pve) out.pve = pve;
    return out;
  } catch {
    const single = parseTarkovPmcFaction(raw);
    return single ? { pvp: single, pve: single } : {};
  }
}

function readMap(): FactionMap {
  if (typeof window === "undefined") return cachedMap;
  try {
    const raw = window.localStorage.getItem(TARKOV_PMC_FACTION_STORAGE_KEY);
    if (raw === cachedRaw) return cachedMap;
    cachedRaw = raw;
    cachedMap = parseMap(raw);
    return cachedMap;
  } catch {
    return cachedMap;
  }
}

function writeMap(next: FactionMap) {
  cachedMap = next;
  cachedRaw = JSON.stringify(next);
  if (typeof window === "undefined") return;
  try {
    if (!next.pvp && !next.pve) {
      window.localStorage.removeItem(TARKOV_PMC_FACTION_STORAGE_KEY);
      cachedRaw = null;
    } else {
      window.localStorage.setItem(TARKOV_PMC_FACTION_STORAGE_KEY, cachedRaw);
    }
  } catch {
    /* ignore quota / private mode */
  }
}

function emitFactionChange() {
  listeners.forEach((listener) => listener());
}

export function loadTarkovPmcFaction(
  mode: TarkovGameMode = getTarkovGameMode(),
): TarkovPmcFactionChoice {
  return readMap()[mode] || "";
}

export function persistTarkovPmcFaction(
  mode: TarkovGameMode,
  faction: TarkovPmcFactionChoice,
): TarkovPmcFactionChoice {
  const parsed = parseTarkovPmcFaction(faction);
  const current = { ...readMap() };
  if (!parsed) delete current[mode];
  else current[mode] = parsed;
  writeMap(current);
  emitFactionChange();
  return parsed;
}

export function subscribeTarkovPmcFaction(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

/** 单测重置进程内缓存。 */
export function resetTarkovPmcFactionRuntime() {
  cachedRaw = null;
  cachedMap = {};
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event: StorageEvent) => {
    if (event.key && event.key !== TARKOV_PMC_FACTION_STORAGE_KEY) return;
    cachedRaw = null;
    emitFactionChange();
  });
}

export function useTarkovPmcFaction(): {
  faction: TarkovPmcFactionChoice;
  setFaction: (next: TarkovPmcFactionChoice) => void;
} {
  const mode = useTarkovGameMode();
  const faction = useSyncExternalStore<TarkovPmcFactionChoice>(
    subscribeTarkovPmcFaction,
    () => loadTarkovPmcFaction(mode),
    () => "",
  );
  const setFaction = useCallback(
    (next: TarkovPmcFactionChoice) => {
      persistTarkovPmcFaction(mode, next);
    },
    [mode],
  );
  return { faction, setFaction };
}
