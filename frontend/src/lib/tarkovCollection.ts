/** 个人中心收藏家（3×4收集）：拖进格子即已收集；格子网按占位自动扩展。 */

import type { QueryClient } from "@tanstack/react-query";
import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import { textMatchesQuery } from "@/lib/tarkovHomeNav";

export const TARKOV_COLLECTION_OWNS_STORAGE_KEY =
  "zhange.guides.tarkov.collectionOwns.v1";
export const TARKOV_COLLECTION_LAYOUT_STORAGE_KEY =
  "zhange.guides.tarkov.collectionLayout.v2";
const TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY =
  "zhange.guides.tarkov.collectionLayout.v3";
export const COLLECTION_GRID_MIN_WIDTH = 3;
export const COLLECTION_GRID_MIN_HEIGHT = 3;
/** T H I C C 物品箱 / Lucky Scav Junkbox 内格：14×14 = 196。 */
export const COLLECTION_GRID_MAX_WIDTH = 14;
export const COLLECTION_GRID_MAX_HEIGHT = 14;

/** 规划网固定按最大箱格展示，不随占位缩小。 */
export function collectionViewGridSize(): CollectionGridSize {
  return {
    cols: COLLECTION_GRID_MAX_WIDTH,
    rows: COLLECTION_GRID_MAX_HEIGHT,
  };
}

export const COLLECTION_GRID_PAD = 1;
export const COLLECTION_CELL_MIN_PX = 32;
export const COLLECTION_CELL_MAX_PX = 80;
export const COLLECTION_CELL_GAP_PX = 2;
export const COLLECTION_CELL_PAD_PX = 4;
export const COLLECTION_CAD_PX = 22;

/** 规划网格宽：按可用宽高比例缩放，14×14 必须完整放下、不撑出滚动条。 */
export function collectionBoardCellSize(
  availWidth: number,
  availHeight: number,
  cols: number,
  rows: number,
): number {
  const c = Math.max(1, Math.trunc(Number(cols) || 1));
  const r = Math.max(1, Math.trunc(Number(rows) || 1));
  const extraW = COLLECTION_CAD_PX + 8 + COLLECTION_CELL_PAD_PX * 2 + 2;
  const extraH = COLLECTION_CAD_PX + COLLECTION_CELL_PAD_PX * 2 + 2;
  const innerW = Math.max(0, Number(availWidth) || 0) - extraW;
  const innerH = Math.max(0, Number(availHeight) || 0) - extraH;
  const byW = (innerW - COLLECTION_CELL_GAP_PX * (c - 1)) / c;
  const byH = (innerH - COLLECTION_CELL_GAP_PX * (r - 1)) / r;
  if (!Number.isFinite(byW) || !Number.isFinite(byH)) {
    return COLLECTION_CELL_MAX_PX;
  }
  return Math.max(1, Math.min(COLLECTION_CELL_MAX_PX, Math.floor(Math.min(byW, byH))));
}

export type TarkovCollectionItem = {
  id: string;
  name?: string;
  short_name?: string;
  icon_link?: string;
  types?: string[] | null;
  handbook_ids?: string[] | null;
  width?: number | null;
  height?: number | null;
  found_in_raid?: boolean | null;
  count?: number | null;
  objective_id?: string;
};

export type CollectionTrayGroup = {
  key: string;
  label: string;
  items: TarkovCollectionItem[];
};

export type TarkovCollectionOwnsState = {
  v: 1;
  pvp?: string[];
  pve?: string[];
  migrated?: { pvp?: boolean; pve?: boolean };
};

export type CollectionSlot = {
  item: TarkovCollectionItem;
  col: number;
  row: number;
  width: number;
  height: number;
  rotated?: boolean;
};

export type CollectionPlacement = {
  itemId: string;
  col: number;
  row: number;
  rotated?: boolean;
};

export type CollectionLayout = {
  v: 2;
  placements: CollectionPlacement[];
};

export type CollectionDrop =
  | { kind: "grid"; col: number; row: number }
  | { kind: "tray" };

export type CollectionBounds = {
  width: number;
  height: number;
  used: number;
  col0: number;
  row0: number;
};

export type CollectionGridSize = {
  cols: number;
  rows: number;
};

function asIdList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of value) {
    if (typeof raw !== "string") continue;
    const ident = raw.trim();
    if (!ident || seen.has(ident)) continue;
    seen.add(ident);
    out.push(ident);
  }
  return out;
}

function emptyOwnsState(): TarkovCollectionOwnsState {
  return { v: 1, pvp: [], pve: [] };
}

export function parseOwnsState(
  raw: string | null | undefined,
): TarkovCollectionOwnsState {
  if (!raw) return emptyOwnsState();
  try {
    const parsed = JSON.parse(raw) as Partial<TarkovCollectionOwnsState> & {
      owned?: unknown;
    };
    if (!parsed || parsed.v !== 1) return emptyOwnsState();
    return {
      v: 1,
      pvp: asIdList(parsed.pvp ?? parsed.owned),
      pve: asIdList(parsed.pve),
      migrated: parsed.migrated,
    };
  } catch {
    return emptyOwnsState();
  }
}

export function loadOwnedIds(mode: TarkovGameMode): string[] {
  try {
    const state = parseOwnsState(
      localStorage.getItem(TARKOV_COLLECTION_OWNS_STORAGE_KEY),
    );
    return mode === "pve" ? state.pve || [] : state.pvp || [];
  } catch {
    return [];
  }
}

export function saveOwnedIds(
  mode: TarkovGameMode,
  ids: string[],
  migrated = false,
): void {
  let state = emptyOwnsState();
  try {
    state = parseOwnsState(
      localStorage.getItem(TARKOV_COLLECTION_OWNS_STORAGE_KEY),
    );
  } catch {
    /* keep empty */
  }
  if (mode === "pve") state.pve = asIdList(ids);
  else state.pvp = asIdList(ids);
  if (migrated) {
    state.migrated = { ...state.migrated, [mode]: true };
  }
  try {
    localStorage.setItem(
      TARKOV_COLLECTION_OWNS_STORAGE_KEY,
      JSON.stringify(state),
    );
  } catch {
    /* ignore quota / private mode */
  }
}

export function markOwnsMigrated(mode: TarkovGameMode, ids: string[]): void {
  saveOwnedIds(mode, ids, true);
}

export const TARKOV_COLLECTION_OWNS_QUERY_KEY = [
  "guides-tarkov-collection-owns",
] as const;

export function collectionOwnsQueryKey(mode: TarkovGameMode) {
  return [...TARKOV_COLLECTION_OWNS_QUERY_KEY, mode] as const;
}

export const TARKOV_COLLECTION_LAYOUT_QUERY_KEY = [
  "guides-tarkov-collection-layout",
] as const;

export function collectionLayoutQueryKey(mode: TarkovGameMode) {
  return [...TARKOV_COLLECTION_LAYOUT_QUERY_KEY, mode] as const;
}

export function applyTarkovCollectionOwnsCache(
  queryClient: QueryClient,
  mode: TarkovGameMode,
  ids: string[],
): void {
  markOwnsMigrated(mode, ids);
  queryClient.setQueryData(collectionOwnsQueryKey(mode), { item_ids: ids });
}

export function ownsDiff(
  current: readonly string[],
  next: readonly string[],
): { add: string[]; remove: string[] } {
  const have = new Set(current);
  const want = new Set(next);
  return {
    add: next.filter((id) => !have.has(id)),
    remove: current.filter((id) => !want.has(id)),
  };
}

export function collectionOwnedCount(
  items: readonly TarkovCollectionItem[],
  collected: Set<string>,
): { have: number; total: number } {
  let have = 0;
  for (const item of items) {
    if (collected.has(item.id)) have += 1;
  }
  return { have, total: items.length };
}

export function collectionItemSize(
  item: TarkovCollectionItem,
  rotated = false,
): {
  width: number;
  height: number;
} {
  const rawW = Math.max(1, Math.trunc(Number(item.width) || 1));
  const rawH = Math.max(1, Math.trunc(Number(item.height) || 1));
  return rotated
    ? { width: rawH, height: rawW }
    : { width: rawW, height: rawH };
}

export function collectionItemCells(item: TarkovCollectionItem): number {
  const { width, height } = collectionItemSize(item);
  return width * height;
}

export function sortCollectionItemsByCells(
  items: readonly TarkovCollectionItem[],
): TarkovCollectionItem[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      const diff = collectionItemCells(b.item) - collectionItemCells(a.item);
      return diff !== 0 ? diff : a.index - b.index;
    })
    .map((row) => row.item);
}

export function collectionItemCategory(item: TarkovCollectionItem): {
  key: string;
  label: string;
  order: number;
} {
  const cells = collectionItemCells(item);
  return {
    key: `cells:${cells}`,
    label: `${cells}格`,
    order: -cells,
  };
}

export function groupCollectionTrayItems(
  items: readonly TarkovCollectionItem[],
): CollectionTrayGroup[] {
  const groups = new Map<
    string,
    CollectionTrayGroup & { order: number }
  >();
  for (const item of sortCollectionItemsByCells(items)) {
    const cat = collectionItemCategory(item);
    const existing = groups.get(cat.key);
    if (existing) existing.items.push(item);
    else {
      groups.set(cat.key, {
        key: cat.key,
        label: cat.label,
        items: [item],
        order: cat.order,
      });
    }
  }
  return [...groups.values()]
    .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label, "zh"))
    .map((group) => ({
      key: group.key,
      label: group.label,
      items: group.items,
    }));
}

export function filterCollectionItems(
  items: readonly TarkovCollectionItem[],
  q: string,
): TarkovCollectionItem[] {
  const query = q.trim();
  return sortCollectionItemsByCells(
    items.filter((item) => {
      if (!query) return true;
      return textMatchesQuery(query, item.name, item.short_name, item.id);
    }),
  );
}

function emptyLayout(): CollectionLayout {
  return { v: 2, placements: [] };
}

function asInt(value: unknown, fallback = 0): number {
  const n = Math.trunc(Number(value));
  return Number.isFinite(n) ? n : fallback;
}

function itemsByIdMap(
  items: readonly TarkovCollectionItem[],
): Map<string, TarkovCollectionItem> {
  const map = new Map<string, TarkovCollectionItem>();
  for (const item of items) map.set(item.id, item);
  return map;
}

function occupyKey(col: number, row: number): string {
  return `${col},${row}`;
}

export function parseCollectionLayout(raw: unknown): CollectionLayout | null {
  if (!raw || typeof raw !== "object") return null;
  const parsed = raw as Partial<CollectionLayout> & {
    boxIds?: unknown;
    placements?: unknown;
  };
  if (parsed.v !== 2 || !Array.isArray(parsed.placements)) return null;
  const seen = new Set<string>();
  const placements: CollectionPlacement[] = [];
  for (const row of parsed.placements) {
    if (!row || typeof row !== "object") continue;
    const rec = row as { itemId?: unknown; item_id?: unknown; rotated?: unknown };
    const itemId = String(rec.itemId || rec.item_id || "").trim();
    const col = asInt(row.col, -1);
    const rowN = asInt(row.row, -1);
    if (!itemId || seen.has(itemId) || col < 0 || rowN < 0) continue;
    seen.add(itemId);
    placements.push({
      itemId,
      col,
      row: rowN,
      ...(rec.rotated ? { rotated: true } : {}),
    });
  }
  return { v: 2, placements };
}

export type CollectionLayoutApi = {
  placements?: Array<{
    item_id?: string;
    col?: number;
    row?: number;
    rotated?: boolean;
  }>;
  saved?: boolean;
};

export function pickCollectionLayoutSource(input: {
  saved?: boolean;
  remote: CollectionLayout | null;
  local: CollectionLayout | null;
}): { layout: CollectionLayout; migrateLocal: boolean } {
  if (input.saved) {
    return {
      layout: input.remote ?? emptyLayout(),
      migrateLocal: false,
    };
  }
  if (input.local?.placements.length) {
    return {
      layout: input.local,
      migrateLocal: input.saved === false,
    };
  }
  return {
    layout: input.remote ?? input.local ?? emptyLayout(),
    migrateLocal: false,
  };
}

export function layoutFromApi(raw: CollectionLayoutApi | null | undefined): CollectionLayout | null {
  if (!raw || !Array.isArray(raw.placements)) return null;
  return parseCollectionLayout({ v: 2, placements: raw.placements });
}

export function layoutToApi(layout: CollectionLayout): {
  placements: Array<{
    item_id: string;
    col: number;
    row: number;
    rotated: boolean;
  }>;
} {
  return {
    placements: layout.placements.map((row) => ({
      item_id: row.itemId,
      col: row.col,
      row: row.row,
      rotated: Boolean(row.rotated),
    })),
  };
}

type LayoutStore = {
  v: 2;
  pvp?: CollectionLayout;
  pve?: CollectionLayout;
};

function parseLayoutStore(raw: string | null | undefined): LayoutStore {
  if (!raw) return { v: 2 };
  try {
    const parsed = JSON.parse(raw) as Partial<LayoutStore>;
    if (!parsed || parsed.v !== 2) return { v: 2 };
    return {
      v: 2,
      pvp: parseCollectionLayout(parsed.pvp) || undefined,
      pve: parseCollectionLayout(parsed.pve) || undefined,
    };
  } catch {
    return { v: 2 };
  }
}

function parseV3AsV2(raw: unknown): CollectionLayout | null {
  if (!raw || typeof raw !== "object") return null;
  const parsed = raw as { v?: unknown; placements?: unknown };
  if (parsed.v !== 3 || !Array.isArray(parsed.placements)) return null;
  return parseCollectionLayout({ v: 2, placements: parsed.placements });
}

function loadV3Layout(mode: TarkovGameMode): CollectionLayout | null {
  try {
    const raw = localStorage.getItem(TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { v?: unknown; pvp?: unknown; pve?: unknown };
    if (!parsed || parsed.v !== 3) return null;
    return parseV3AsV2(mode === "pve" ? parsed.pve : parsed.pvp);
  } catch {
    return null;
  }
}

export function loadCollectionLayout(
  mode: TarkovGameMode,
): CollectionLayout | null {
  try {
    const store = parseLayoutStore(
      localStorage.getItem(TARKOV_COLLECTION_LAYOUT_STORAGE_KEY),
    );
    const current = mode === "pve" ? store.pve : store.pvp;
    if (current) return current;
    return loadV3Layout(mode);
  } catch {
    return null;
  }
}

export function saveCollectionLayout(
  mode: TarkovGameMode,
  layout: CollectionLayout,
): void {
  let store: LayoutStore = { v: 2 };
  try {
    store = parseLayoutStore(
      localStorage.getItem(TARKOV_COLLECTION_LAYOUT_STORAGE_KEY),
    );
  } catch {
    /* keep empty */
  }
  const next = parseCollectionLayout(layout) || emptyLayout();
  if (mode === "pve") store.pve = next;
  else store.pvp = next;
  try {
    localStorage.setItem(
      TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
      JSON.stringify(store),
    );
  } catch {
    /* ignore quota / private mode */
  }
  clearV3Layout(mode);
}

function clearV3Layout(mode: TarkovGameMode): void {
  try {
    const raw = localStorage.getItem(TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as {
      v?: unknown;
      pvp?: unknown;
      pve?: unknown;
    };
    if (!parsed || parsed.v !== 3) return;
    if (mode === "pve") delete parsed.pve;
    else delete parsed.pvp;
    if (!parsed.pvp && !parsed.pve) {
      localStorage.removeItem(TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY);
      return;
    }
    localStorage.setItem(
      TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY,
      JSON.stringify(parsed),
    );
  } catch {
    /* ignore quota / private mode */
  }
}

export function collectedIdsFromLayout(layout: CollectionLayout): string[] {
  return layout.placements.map((row) => row.itemId);
}

export function layoutOccupancy(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  exceptItemId?: string,
): Set<string> {
  const byId = itemsByIdMap(items);
  const cells = new Set<string>();
  for (const place of layout.placements) {
    if (exceptItemId && place.itemId === exceptItemId) continue;
    const item = byId.get(place.itemId);
    if (!item) continue;
    const rotated = Boolean(place.rotated);
    if (place.col < 0 || place.row < 0) continue;
    const { width, height } = collectionItemSize(item, rotated);
    for (let y = place.row; y < place.row + height; y += 1) {
      for (let x = place.col; x < place.col + width; x += 1) {
        cells.add(occupyKey(x, y));
      }
    }
  }
  return cells;
}

export function canPlaceCollectionItem(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  itemId: string,
  col: number,
  row: number,
  rotated = false,
): boolean {
  const item = itemsByIdMap(items).get(itemId);
  if (!item || col < 0 || row < 0) return false;
  const { width, height } = collectionItemSize(item, rotated);
  if (
    col + width > COLLECTION_GRID_MAX_WIDTH ||
    row + height > COLLECTION_GRID_MAX_HEIGHT
  ) {
    return false;
  }
  const cells = layoutOccupancy(layout, items, itemId);
  for (let y = row; y < row + height; y += 1) {
    for (let x = col; x < col + width; x += 1) {
      if (cells.has(occupyKey(x, y))) return false;
    }
  }
  return true;
}

export function collectionOccupiedBounds(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
): CollectionBounds {
  const byId = itemsByIdMap(items);
  let minC = Number.POSITIVE_INFINITY;
  let minR = Number.POSITIVE_INFINITY;
  let maxC = Number.NEGATIVE_INFINITY;
  let maxR = Number.NEGATIVE_INFINITY;
  let used = 0;
  for (const place of layout.placements) {
    const item = byId.get(place.itemId);
    if (!item || place.col < 0 || place.row < 0) continue;
    const { width, height } = collectionItemSize(item, Boolean(place.rotated));
    minC = Math.min(minC, place.col);
    minR = Math.min(minR, place.row);
    maxC = Math.max(maxC, place.col + width);
    maxR = Math.max(maxR, place.row + height);
    used += width * height;
  }
  if (!used) {
    return { width: 0, height: 0, used: 0, col0: 0, row0: 0 };
  }
  return {
    width: maxC - minC,
    height: maxR - minR,
    used,
    col0: minC,
    row0: minR,
  };
}

export function collectionGridSize(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  pad: number = COLLECTION_GRID_PAD,
): CollectionGridSize {
  const byId = itemsByIdMap(items);
  let maxC = 0;
  let maxR = 0;
  const ring = Number.isFinite(pad) ? Math.max(0, pad) : 0;
  for (const place of layout.placements) {
    const item = byId.get(place.itemId);
    if (!item || place.col < 0 || place.row < 0) continue;
    const { width, height } = collectionItemSize(item, Boolean(place.rotated));
    maxC = Math.max(maxC, place.col + width);
    maxR = Math.max(maxR, place.row + height);
  }
  return {
    cols: Math.min(
      COLLECTION_GRID_MAX_WIDTH,
      Math.max(COLLECTION_GRID_MIN_WIDTH, maxC + ring),
    ),
    rows: Math.min(
      COLLECTION_GRID_MAX_HEIGHT,
      Math.max(COLLECTION_GRID_MIN_HEIGHT, maxR + ring),
    ),
  };
}

/** 合法落点若比当前网更大，预览就扩到放下后的尺寸，把底部多出来的格露出来。 */
export function collectionGridSizeForPreview(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  drop?: CollectionDrop | null,
  draggingId?: string,
  rotated = false,
): CollectionGridSize {
  if (drop?.kind === "grid" && draggingId) {
    const next = moveCollectionItem(layout, items, draggingId, drop, rotated);
    if (next) return collectionGridSize(next, items);
  }
  return collectionGridSize(layout, items);
}

/** 合法落点若比当前网更大，返回扩大后的尺寸，供绿色边框提示。 */
export function collectionExpandPreview(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  drop: CollectionDrop | null,
  itemId: string,
  rotated = false,
): CollectionGridSize | null {
  if (!drop || drop.kind !== "grid") return null;
  const next = moveCollectionItem(layout, items, itemId, drop, rotated);
  if (!next) return null;
  const base = collectionGridSize(layout, items);
  const size = collectionGridSize(next, items);
  if (size.cols <= base.cols && size.rows <= base.rows) return null;
  return size;
}

export function sanitizeCollectionLayout(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
): CollectionLayout {
  const byId = itemsByIdMap(items);
  const next: CollectionLayout = { v: 2, placements: [] };
  for (const place of layout.placements) {
    const item = byId.get(place.itemId);
    if (!item) continue;
    const rotated = Boolean(place.rotated);
    if (
      !canPlaceCollectionItem(
        next,
        items,
        item.id,
        place.col,
        place.row,
        rotated,
      )
    ) {
      continue;
    }
    next.placements.push({
      itemId: item.id,
      col: place.col,
      row: place.row,
      ...(rotated ? { rotated: true } : {}),
    });
  }
  return next;
}

export function reconcileCollectionLayout(
  layout: CollectionLayout | null,
  items: readonly TarkovCollectionItem[],
): CollectionLayout {
  if (!layout || layout.v !== 2) return emptyLayout();
  return sanitizeCollectionLayout(layout, items);
}

export function layoutToCollectionSlots(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
): { slots: CollectionSlot[]; uncollected: TarkovCollectionItem[] } {
  const byId = itemsByIdMap(items);
  const placed = new Set<string>();
  const slots: CollectionSlot[] = [];
  for (const place of layout.placements) {
    const item = byId.get(place.itemId);
    if (!item) continue;
    const rotated = Boolean(place.rotated);
    const { width, height } = collectionItemSize(item, rotated);
    slots.push({
      item,
      col: place.col,
      row: place.row,
      width,
      height,
      rotated,
    });
    placed.add(item.id);
  }
  return {
    slots,
    uncollected: sortCollectionItemsByCells(
      items.filter((item) => !placed.has(item.id)),
    ),
  };
}

export function moveCollectionItem(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  itemId: string,
  dest: CollectionDrop | null,
  rotated?: boolean,
): CollectionLayout | null {
  const id = itemId.trim();
  if (!id) return null;
  const current = layout.placements.find((row) => row.itemId === id);
  const nextRotated =
    rotated !== undefined ? rotated : Boolean(current?.rotated);
  const stripped: CollectionLayout = {
    v: 2,
    placements: layout.placements.filter((row) => row.itemId !== id),
  };
  if (!dest || dest.kind === "tray") return stripped;
  if (
    !canPlaceCollectionItem(
      stripped,
      items,
      id,
      dest.col,
      dest.row,
      nextRotated,
    )
  ) {
    return null;
  }
  return {
    v: 2,
    placements: [
      ...stripped.placements,
      {
        itemId: id,
        col: dest.col,
        row: dest.row,
        ...(nextRotated ? { rotated: true } : {}),
      },
    ],
  };
}

export function findCollectionFit(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  itemId: string,
  rotated = false,
): { col: number; row: number; rotated: boolean } | null {
  const item = itemsByIdMap(items).get(itemId.trim());
  if (!item) return null;
  const orientations = rotated ? [true, false] : [false, true];
  for (const rot of orientations) {
    for (let row = 0; row < COLLECTION_GRID_MAX_HEIGHT; row += 1) {
      for (let col = 0; col < COLLECTION_GRID_MAX_WIDTH; col += 1) {
        if (canPlaceCollectionItem(layout, items, item.id, col, row, rot)) {
          return { col, row, rotated: rot };
        }
      }
    }
  }
  return null;
}

export function toggleCollectionItem(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  itemId: string,
  rotated = false,
): CollectionLayout | null {
  const id = itemId.trim();
  if (!id || !itemsByIdMap(items).has(id)) return null;
  if (layout.placements.some((row) => row.itemId === id)) {
    return moveCollectionItem(layout, items, id, { kind: "tray" });
  }
  const fit = findCollectionFit(layout, items, id, rotated);
  if (!fit) return null;
  return moveCollectionItem(
    layout,
    items,
    id,
    { kind: "grid", col: fit.col, row: fit.row },
    fit.rotated,
  );
}

export function rotateCollectionItem(
  layout: CollectionLayout,
  items: readonly TarkovCollectionItem[],
  itemId: string,
): CollectionLayout | null {
  const current = layout.placements.find((row) => row.itemId === itemId);
  if (!current) return layout;
  return moveCollectionItem(
    layout,
    items,
    itemId,
    { kind: "grid", col: current.col, row: current.row },
    !current.rotated,
  );
}

export function clearCollectionLayout(): CollectionLayout {
  return emptyLayout();
}

export function rotateCollectionDragGrab(
  width: number,
  height: number,
  anchorCol: number,
  anchorRow: number,
  grabX: number,
  grabY: number,
  stride: number,
): {
  width: number;
  height: number;
  anchorCol: number;
  anchorRow: number;
  grabX: number;
  grabY: number;
} {
  const w = Math.max(1, Math.trunc(width) || 1);
  const h = Math.max(1, Math.trunc(height) || 1);
  const step = stride > 0 ? stride : 1;
  const ax = Math.max(0, Math.min(w - 1, Math.trunc(anchorCol) || 0));
  const ay = Math.max(0, Math.min(h - 1, Math.trunc(anchorRow) || 0));
  const intraX = grabX - ax * step;
  const intraY = grabY - ay * step;
  const nextAnchorCol = h - 1 - ay;
  const nextAnchorRow = ax;
  return {
    width: h,
    height: w,
    anchorCol: nextAnchorCol,
    anchorRow: nextAnchorRow,
    grabX: nextAnchorCol * step + intraY,
    grabY: nextAnchorRow * step + intraX,
  };
}

export function collectionDropCell(
  localX: number,
  localY: number,
  cell: number,
  gap: number,
  pad: number,
  anchorCol: number,
  anchorRow: number,
  cols: number,
  rows: number,
  hitCols = cols,
  hitRows = rows,
): { col: number; row: number } | null {
  if (cell <= 0 || cols <= 0 || rows <= 0) return null;
  const stride = cell + gap;
  const hoverCol = Math.floor((localX - pad) / stride);
  const hoverRow = Math.floor((localY - pad) / stride);
  const colLimit = Math.max(cols, hitCols);
  const rowLimit = Math.max(rows, hitRows);
  if (
    hoverCol < 0 ||
    hoverRow < 0 ||
    hoverCol >= colLimit ||
    hoverRow >= rowLimit
  ) {
    return null;
  }
  return {
    col: hoverCol - anchorCol,
    row: hoverRow - anchorRow,
  };
}
