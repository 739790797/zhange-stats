import rawLayouts from "@/data/tarkov-item-grids.json";

/** tarkov-dev 容器口袋坐标；col/row 可为半格（如 0.5）。 */
export type GridPocket = {
  width: number;
  height: number;
  col: number;
  row: number;
};

export type GridOccupancy = {
  width: number;
  height: number;
  cells: boolean[];
};

/** mapped=社区布局；coordinates=dump 自带坐标；stacked=无坐标时分口袋展示。 */
export type GridLayoutKind = "mapped" | "coordinates" | "stacked";

export type ItemGridLayout = {
  pockets: GridPocket[];
  kind: GridLayoutKind;
};

type LayoutPocket = {
  row?: number;
  col?: number;
  width?: number;
  height?: number;
};

const LAYOUTS = rawLayouts as Record<string, LayoutPocket[]>;

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function positiveInt(value: unknown): number | null {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.floor(n);
}

function parseLayoutPockets(rows: LayoutPocket[] | undefined): GridPocket[] {
  if (!Array.isArray(rows)) return [];
  const out: GridPocket[] = [];
  for (const raw of rows) {
    const width = Number(raw.width);
    const height = Number(raw.height);
    const col = Number(raw.col);
    const row = Number(raw.row);
    if (
      !Number.isFinite(width) ||
      !Number.isFinite(height) ||
      width <= 0 ||
      height <= 0 ||
      !Number.isFinite(col) ||
      !Number.isFinite(row) ||
      col < 0 ||
      row < 0
    ) {
      continue;
    }
    out.push({ width, height, col, row });
  }
  return out;
}

function layoutPockets(itemId: string | null | undefined): GridPocket[] {
  const key = (itemId || "").trim();
  if (!key) return [];
  return parseLayoutPockets(LAYOUTS[key]);
}

function pocketSignature(
  pockets: Array<{ width: number; height: number }>,
): string {
  return pockets
    .map((pocket) => `${pocket.width}x${pocket.height}`)
    .sort()
    .join("|");
}

function pocketPlacementKey(pockets: GridPocket[]): string {
  return pockets
    .map((pocket) => `${pocket.row},${pocket.col},${pocket.width}x${pocket.height}`)
    .sort()
    .join("|");
}

/** 口袋尺寸组合唯一、或同尺寸各条目坐标一致时，才能给未收录 id 套用。 */
const LAYOUT_BY_SIGNATURE: Map<string, GridPocket[] | null> = (() => {
  const groups = new Map<string, GridPocket[][]>();
  for (const rows of Object.values(LAYOUTS)) {
    const pockets = parseLayoutPockets(rows);
    if (!pockets.length) continue;
    const key = pocketSignature(pockets);
    const list = groups.get(key);
    if (list) list.push(pockets);
    else groups.set(key, [pockets]);
  }
  const out = new Map<string, GridPocket[] | null>();
  for (const [key, list] of groups) {
    const placements = new Set(list.map(pocketPlacementKey));
    out.set(key, placements.size === 1 ? list[0] : null);
  }
  return out;
})();

function dumpPockets(
  properties: Record<string, unknown> | undefined,
): Array<{
  width: number;
  height: number;
  col: number | null;
  row: number | null;
}> {
  const grids = properties?.grids ?? properties?.pouches;
  if (!Array.isArray(grids)) return [];
  const out: Array<{
    width: number;
    height: number;
    col: number | null;
    row: number | null;
  }> = [];
  for (const grid of grids) {
    const row = asRecord(grid);
    if (!row) continue;
    const width = Number(row.width);
    const height = Number(row.height);
    if (
      !Number.isFinite(width) ||
      !Number.isFinite(height) ||
      width <= 0 ||
      height <= 0
    ) {
      continue;
    }
    out.push({
      width,
      height,
      col: positiveInt(row.col ?? row.x),
      row: positiveInt(row.row ?? row.y),
    });
  }
  return out;
}

/** 缺坐标时按行堆叠，避免用 index 当 col 导致口袋重叠。 */
export function packGridPockets(
  pockets: Array<{ width: number; height: number }>,
): GridPocket[] {
  if (!pockets.length) return [];
  const total = pockets.reduce((sum, pocket) => sum + pocket.width * pocket.height, 0);
  const wrapAt = Math.max(
    ...pockets.map((pocket) => pocket.width),
    Math.ceil(Math.sqrt(total)),
  );
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  const out: GridPocket[] = [];
  for (const pocket of pockets) {
    if (x > 0 && x + pocket.width > wrapAt) {
      y += rowHeight;
      x = 0;
      rowHeight = 0;
    }
    out.push({ width: pocket.width, height: pocket.height, col: x, row: y });
    x += pocket.width;
    rowHeight = Math.max(rowHeight, pocket.height);
  }
  return out;
}

export function resolveItemGridLayout(
  properties: Record<string, unknown> | undefined,
  itemId?: string | null,
): ItemGridLayout {
  const mapped = layoutPockets(itemId);
  if (mapped.length) return { pockets: mapped, kind: "mapped" };
  const dumped = dumpPockets(properties);
  if (!dumped.length) return { pockets: [], kind: "stacked" };
  const bySignature = LAYOUT_BY_SIGNATURE.get(pocketSignature(dumped));
  if (bySignature?.length) return { pockets: bySignature, kind: "mapped" };
  if (dumped.every((pocket) => pocket.col != null && pocket.row != null)) {
    return {
      pockets: dumped.map((pocket) => ({
        width: pocket.width,
        height: pocket.height,
        col: pocket.col as number,
        row: pocket.row as number,
      })),
      kind: "coordinates",
    };
  }
  return { pockets: packGridPockets(dumped), kind: "stacked" };
}

export function extractGridPockets(
  properties: Record<string, unknown> | undefined,
  itemId?: string | null,
): GridPocket[] {
  return resolveItemGridLayout(properties, itemId).pockets;
}

function halfCells(value: number): number {
  return Math.round(value * 2);
}

export function composeGridOccupancy(
  pockets: GridPocket[],
): GridOccupancy | null {
  if (!pockets.length) return null;
  let width = 0;
  let height = 0;
  for (const pocket of pockets) {
    width = Math.max(width, halfCells(pocket.col) + halfCells(pocket.width));
    height = Math.max(height, halfCells(pocket.row) + halfCells(pocket.height));
  }
  if (width <= 0 || height <= 0) return null;
  const cells = Array.from({ length: width * height }, () => false);
  for (const pocket of pockets) {
    const originX = halfCells(pocket.col);
    const originY = halfCells(pocket.row);
    const pocketW = halfCells(pocket.width);
    const pocketH = halfCells(pocket.height);
    for (let y = 0; y < pocketH; y += 1) {
      for (let x = 0; x < pocketW; x += 1) {
        cells[(originY + y) * width + (originX + x)] = true;
      }
    }
  }
  return { width, height, cells };
}

export function gridOccupancyCaption(
  pockets: GridPocket[],
  capacity?: number | null,
): string {
  const filled = pockets.reduce(
    (sum, pocket) => sum + pocket.width * pocket.height,
    0,
  );
  const parts: string[] = [`${filled} 格`];
  if (
    capacity != null &&
    Number.isFinite(capacity) &&
    capacity > 0 &&
    capacity !== filled
  ) {
    parts.push(`容量 ${capacity}`);
  }
  if (pockets.length) {
    parts.push(pockets.map((pocket) => `${pocket.width}×${pocket.height}`).join(" · "));
  }
  return parts.join(" · ");
}
