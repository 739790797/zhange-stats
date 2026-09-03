import {
  parseFilterGroupsCollapsed,
  type TarkovMapFilterGroupId,
} from "./tarkovMapFilterGroups";
import {
  defaultExtractKindFlags,
  TARKOV_EXTRACT_KINDS,
  type TarkovExtractKind,
  type TarkovExtractKindFlags,
} from "./tarkovMapExtracts";
import {
  defaultTarkovMapKindFlags,
  parseKindFlags,
  type TarkovMapKindFlags,
} from "./tarkovMapMarkers";
import {
  defaultSpawnKindFlags,
  TARKOV_SPAWN_KINDS,
  type TarkovSpawnKind,
  type TarkovSpawnKindFlags,
} from "./tarkovMapSpawns";

const STORAGE_KEY = "zhange.guides.tarkov.mapViewer.v1";

export type TarkovMapOverlayMode = "all" | "boss-spawns";

export function overlayFlagsForMode(
  prefs: TarkovMapViewerPrefs,
  overlayMode: TarkovMapOverlayMode = "all",
): Pick<
  TarkovMapViewerPrefs,
  | "extractKinds"
  | "spawnKinds"
  | "showLabels"
  | "showQuests"
  | "showLocks"
  | "showHazards"
  | "showSwitches"
  | "showStationary"
  | "showBtrStops"
  | "showLootContainers"
  | "showLootLoose"
  | "hazardKinds"
  | "lootContainerKinds"
  | "lootLooseKinds"
> {
  if (overlayMode === "boss-spawns") {
    return {
      extractKinds: defaultExtractKindFlags(false),
      spawnKinds: { pmc: false, scav: false, sniper: false, boss: true },
      showLabels: false,
      showQuests: false,
      showLocks: false,
      showHazards: false,
      showSwitches: false,
      showStationary: false,
      showBtrStops: false,
      showLootContainers: false,
      showLootLoose: false,
      hazardKinds: prefs.hazardKinds,
      lootContainerKinds: prefs.lootContainerKinds,
      lootLooseKinds: prefs.lootLooseKinds,
    };
  }
  return {
    extractKinds: prefs.extractKinds,
    spawnKinds: prefs.spawnKinds,
    showLabels: prefs.showLabels,
    showQuests: prefs.showQuests,
    showLocks: prefs.showLocks,
    showHazards: prefs.showHazards,
    showSwitches: prefs.showSwitches,
    showStationary: prefs.showStationary,
    showBtrStops: prefs.showBtrStops,
    showLootContainers: prefs.showLootContainers,
    showLootLoose: prefs.showLootLoose,
    hazardKinds: prefs.hazardKinds,
    lootContainerKinds: prefs.lootContainerKinds,
    lootLooseKinds: prefs.lootLooseKinds,
  };
}

export type TarkovMapViewerStyle = "svg" | "tile";

export type TarkovMapViewerPrefs = {
  style: TarkovMapViewerStyle;
  /** 左上角图层筛选面板是否展开。 */
  filterPanelOpen: boolean;
  /** 有子项的大类是否收起；缺省展开。 */
  filterGroupsCollapsed: Partial<Record<TarkovMapFilterGroupId, boolean>>;
  floorsByMap: Record<string, string>;
  /** 按阵营分类的撤离点显隐；对齐 tarkov.dev Extracts 子图层。 */
  extractKinds: TarkovExtractKindFlags;
  /** 出生点：PMC / Scav / 狙击 Scav / Boss；对齐 tarkov.dev Spawns。 */
  spawnKinds: TarkovSpawnKindFlags;
  showLabels: boolean;
  showQuests: boolean;
  showLocks: boolean;
  showHazards: boolean;
  showSwitches: boolean;
  showStationary: boolean;
  showBtrStops: boolean;
  showLootContainers: boolean;
  showLootLoose: boolean;
  hazardKinds: TarkovMapKindFlags;
  lootContainerKinds: TarkovMapKindFlags;
  lootLooseKinds: TarkovMapKindFlags;
};

export const DEFAULT_TARKOV_MAP_VIEWER_PREFS: TarkovMapViewerPrefs = {
  style: "svg",
  filterPanelOpen: true,
  filterGroupsCollapsed: {},
  floorsByMap: {},
  extractKinds: defaultExtractKindFlags(true),
  spawnKinds: defaultSpawnKindFlags(true),
  showLabels: true,
  showQuests: true,
  showLocks: true,
  showHazards: true,
  showSwitches: true,
  showStationary: true,
  showBtrStops: true,
  showLootContainers: false,
  showLootLoose: false,
  hazardKinds: defaultTarkovMapKindFlags(),
  lootContainerKinds: defaultTarkovMapKindFlags(),
  lootLooseKinds: defaultTarkovMapKindFlags(),
};

function asStyle(value: unknown): TarkovMapViewerStyle | null {
  return value === "svg" || value === "tile" ? value : null;
}

function asBool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function parseFloorsByMap(raw: unknown): Record<string, string> {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!key || typeof value !== "string") continue;
    out[key] = value;
  }
  return out;
}

function parseExtractKinds(
  raw: unknown,
  legacyShowExtracts: unknown,
): TarkovExtractKindFlags {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const row = raw as Record<string, unknown>;
    const out = defaultExtractKindFlags(true);
    for (const kind of TARKOV_EXTRACT_KINDS) {
      out[kind] = asBool(row[kind], out[kind]);
    }
    return out;
  }
  /* 旧版 showExtracts:boolean → 四类同开同关 */
  return defaultExtractKindFlags(asBool(legacyShowExtracts, true));
}

function parseSpawnKinds(
  raw: unknown,
  legacyShowBosses: unknown,
): TarkovSpawnKindFlags {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const row = raw as Record<string, unknown>;
    const out = defaultSpawnKindFlags(true);
    for (const kind of TARKOV_SPAWN_KINDS) {
      out[kind] = asBool(row[kind], out[kind]);
    }
    return out;
  }
  /* 旧版 showBosses:boolean → 只迁 Boss，PMC/Scav 默认开 */
  const out = defaultSpawnKindFlags(true);
  out.boss = asBool(legacyShowBosses, true);
  return out;
}

function emptyPrefs(): TarkovMapViewerPrefs {
  return {
    ...DEFAULT_TARKOV_MAP_VIEWER_PREFS,
    filterGroupsCollapsed: {},
    floorsByMap: {},
    extractKinds: defaultExtractKindFlags(true),
    spawnKinds: defaultSpawnKindFlags(true),
    hazardKinds: defaultTarkovMapKindFlags(),
    lootContainerKinds: defaultTarkovMapKindFlags(),
    lootLooseKinds: defaultTarkovMapKindFlags(),
  };
}

export function parseTarkovMapViewerPrefs(
  raw: string | null,
): TarkovMapViewerPrefs {
  if (!raw) return emptyPrefs();
  try {
    const parsed = JSON.parse(raw) as Partial<TarkovMapViewerPrefs> & {
      showExtracts?: unknown;
      showBosses?: unknown;
    };
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return emptyPrefs();
    }
    return {
      style: asStyle(parsed.style) ?? DEFAULT_TARKOV_MAP_VIEWER_PREFS.style,
      filterPanelOpen: asBool(
        parsed.filterPanelOpen,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.filterPanelOpen,
      ),
      filterGroupsCollapsed: parseFilterGroupsCollapsed(
        parsed.filterGroupsCollapsed,
      ),
      floorsByMap: parseFloorsByMap(parsed.floorsByMap),
      extractKinds: parseExtractKinds(
        parsed.extractKinds,
        parsed.showExtracts,
      ),
      spawnKinds: parseSpawnKinds(parsed.spawnKinds, parsed.showBosses),
      showLabels: asBool(
        parsed.showLabels,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showLabels,
      ),
      showQuests: asBool(
        parsed.showQuests,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showQuests,
      ),
      showLocks: asBool(
        parsed.showLocks,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showLocks,
      ),
      showHazards: asBool(
        parsed.showHazards,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showHazards,
      ),
      showSwitches: asBool(
        parsed.showSwitches,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showSwitches,
      ),
      showStationary: asBool(
        parsed.showStationary,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showStationary,
      ),
      showBtrStops: asBool(
        parsed.showBtrStops,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showBtrStops,
      ),
      showLootContainers: asBool(
        parsed.showLootContainers,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showLootContainers,
      ),
      showLootLoose: asBool(
        parsed.showLootLoose,
        DEFAULT_TARKOV_MAP_VIEWER_PREFS.showLootLoose,
      ),
      hazardKinds: parseKindFlags(parsed.hazardKinds),
      lootContainerKinds: parseKindFlags(parsed.lootContainerKinds),
      lootLooseKinds: parseKindFlags(parsed.lootLooseKinds),
    };
  } catch {
    return emptyPrefs();
  }
}

export function loadTarkovMapViewerPrefs(): TarkovMapViewerPrefs {
  try {
    return parseTarkovMapViewerPrefs(localStorage.getItem(STORAGE_KEY));
  } catch {
    return emptyPrefs();
  }
}

export function saveTarkovMapViewerPrefs(prefs: TarkovMapViewerPrefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore quota / private mode */
  }
}

export function resolveMapStyle(
  saved: TarkovMapViewerStyle,
  canSvg: boolean,
  canTile: boolean,
): TarkovMapViewerStyle {
  if (saved === "svg" && canSvg) return "svg";
  if (saved === "tile" && canTile) return "tile";
  if (canSvg) return "svg";
  return "tile";
}

/** `undefined` = 这张图还没选过；空字符串 = 地面 */
export function resolveMapFloor(
  saved: string | undefined,
  floorNames: string[],
): string {
  if (!saved) return "";
  return floorNames.includes(saved) ? saved : "";
}

export function withMapFloor(
  prefs: TarkovMapViewerPrefs,
  mapKey: string,
  floor: string,
): TarkovMapViewerPrefs {
  if (!mapKey) return prefs;
  return {
    ...prefs,
    floorsByMap: { ...prefs.floorsByMap, [mapKey]: floor },
  };
}

export function withExtractKind(
  prefs: TarkovMapViewerPrefs,
  kind: TarkovExtractKind,
  on: boolean,
): TarkovMapViewerPrefs {
  return {
    ...prefs,
    extractKinds: { ...prefs.extractKinds, [kind]: on },
  };
}

export function withSpawnKind(
  prefs: TarkovMapViewerPrefs,
  kind: TarkovSpawnKind,
  on: boolean,
): TarkovMapViewerPrefs {
  return {
    ...prefs,
    spawnKinds: { ...prefs.spawnKinds, [kind]: on },
  };
}

export function withHazardKind(
  prefs: TarkovMapViewerPrefs,
  kind: string,
  on: boolean,
): TarkovMapViewerPrefs {
  return {
    ...prefs,
    showHazards: on ? true : prefs.showHazards,
    hazardKinds: { ...prefs.hazardKinds, [kind]: on },
  };
}

export function withLootContainerKind(
  prefs: TarkovMapViewerPrefs,
  kind: string,
  on: boolean,
): TarkovMapViewerPrefs {
  return {
    ...prefs,
    showLootContainers: on ? true : prefs.showLootContainers,
    lootContainerKinds: { ...prefs.lootContainerKinds, [kind]: on },
  };
}

export function withLootLooseKind(
  prefs: TarkovMapViewerPrefs,
  kind: string,
  on: boolean,
): TarkovMapViewerPrefs {
  return {
    ...prefs,
    showLootLoose: on ? true : prefs.showLootLoose,
    lootLooseKinds: { ...prefs.lootLooseKinds, [kind]: on },
  };
}
