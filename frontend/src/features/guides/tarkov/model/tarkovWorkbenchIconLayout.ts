/** 底板用 dump 枪图：有配件时优先工厂预设图，裸机匣用机匣静图。 */
export function workbenchGunArtSource(opts: {
  imageLink?: string | null;
  presetImageLink?: string | null;
  hasInstalled: boolean;
}): string {
  const image = (opts.imageLink || "").trim();
  const preset = (opts.presetImageLink || "").trim();
  return opts.hasInstalled ? preset || image : image || preset;
}

/** 工作台中间：10 列示意图。枪占 7–9 列，槽位按 nameId 落在周围。 */

export const WORKBENCH_GRID_COLS = 10;
export const WORKBENCH_GUN_COL = 7;
export const WORKBENCH_GUN_COL_SPAN = 3;
export const WORKBENCH_STOCK_COL = 10;

export type WorkbenchSlotFamily =
  | "muzzle"
  | "barrel"
  | "gas"
  | "handguard"
  | "catch"
  | "receiver"
  | "stock"
  | "charge"
  | "front_sight"
  | "rear_sight"
  | "scope"
  | "mount"
  | "magazine"
  | "pistol_grip"
  | "foregrip"
  | "bipod"
  | "tactical"
  | "ubgl"
  | "grip"
  | "shroud"
  | "trigger"
  | "chamber"
  | "hammer"
  | "unknown";

export type WorkbenchGridSlot = {
  slotId: string;
  nameId: string;
  family: WorkbenchSlotFamily;
  slotName: string;
  itemId: string;
  icon: string;
  shortName: string;
  required: boolean;
  empty: boolean;
  depth: number;
  parentSlotId: string | null;
  parentFamily: WorkbenchSlotFamily | null;
  isBase: boolean;
};

export type WorkbenchLaidCell = WorkbenchGridSlot & {
  col: number | null;
  row: number | null;
  extras: boolean;
};

export type WorkbenchGridLayout = {
  cells: WorkbenchLaidCell[];
  gunRow: number;
  totalRows: number;
};

const LEFT_ORDER: WorkbenchSlotFamily[] = [
  "receiver",
  "handguard",
  "catch",
  "barrel",
  "gas",
  "muzzle",
];

const TOP_COL: Partial<Record<WorkbenchSlotFamily, number>> = {
  scope: WORKBENCH_GUN_COL + 1,
  mount: WORKBENCH_GUN_COL + 1,
  rear_sight: WORKBENCH_GUN_COL + 2,
};

const BOTTOM_COL: Partial<Record<WorkbenchSlotFamily, number>> = {
  magazine: WORKBENCH_GUN_COL + 1,
  pistol_grip: WORKBENCH_GUN_COL + 2,
};

const BOTTOM_LEFT = new Set<WorkbenchSlotFamily>([
  "bipod",
  "foregrip",
  "ubgl",
]);

const EXTRAS = new Set<WorkbenchSlotFamily>([
  "grip",
  "shroud",
  "trigger",
  "chamber",
  "hammer",
]);

type SlotWalkNode = {
  id: string;
  name?: string;
  name_id?: string;
  required?: boolean;
  installed?: {
    id?: string | null;
    name?: string;
    short_name?: string;
    icon_link?: string;
  } | null;
  children?: unknown[];
};

export function slotFamily(nameId: string): WorkbenchSlotFamily {
  const id = (nameId || "").toLowerCase();
  if (id.includes("muzzle")) return "muzzle";
  if (id.includes("barrel")) return "barrel";
  if (id.includes("gas")) return "gas";
  if (id.includes("handguard")) return "handguard";
  if (id.includes("catch")) return "catch";
  if (id.includes("charge")) return "charge";
  if (id.includes("sight_front") || id.includes("front_sight")) {
    return "front_sight";
  }
  if (id.includes("sight_rear") || id.includes("rear_sight")) {
    return "rear_sight";
  }
  if (id.includes("scope")) return "scope";
  if (id.includes("sight")) return "scope";
  if (id.includes("mount")) return "mount";
  if (id.includes("magazine") || id.includes("mag_")) return "magazine";
  if (id.includes("pistol_grip") || id.includes("pistolgrip")) {
    return "pistol_grip";
  }
  if (id.includes("foregrip")) return "foregrip";
  if (id.includes("bipod")) return "bipod";
  if (id.includes("tactical") || id.includes("flashlight") || id.includes("laser")) {
    return "tactical";
  }
  if (id.includes("launcher") || id.includes("ubgl")) return "ubgl";
  if (id.includes("stock") || id.includes("buffer")) return "stock";
  if (id === "receiver" || id.includes("reciever") || id.includes("receiver")) {
    return "receiver";
  }
  if (id.includes("trigger")) return "trigger";
  if (id.includes("hammer")) return "hammer";
  if (id.includes("chamber")) return "chamber";
  if (id.includes("shroud")) return "shroud";
  if (id.includes("grip")) return "grip";
  return "unknown";
}

export function collectWorkbenchGridSlots(
  nodes: SlotWalkNode[],
  parentSlotId: string | null = null,
  parentFamily: WorkbenchSlotFamily | null = null,
  depth = 0,
): WorkbenchGridSlot[] {
  const out: WorkbenchGridSlot[] = [];
  for (const node of nodes || []) {
    const itemId = node.installed?.id || "";
    const slotName = node.name || node.name_id || node.id;
    const family = slotFamily(node.name_id || "");
    out.push({
      slotId: node.id,
      nameId: node.name_id || "",
      family,
      slotName,
      itemId,
      icon: node.installed?.icon_link || "",
      shortName: itemId
        ? node.installed?.short_name || node.installed?.name || itemId
        : "",
      required: Boolean(node.required),
      empty: !itemId,
      depth,
      parentSlotId,
      parentFamily,
      isBase: depth === 0,
    });
    if (node.children?.length) {
      out.push(
        ...collectWorkbenchGridSlots(
          node.children as SlotWalkNode[],
          node.id,
          family,
          depth + 1,
        ),
      );
    }
  }
  return out;
}

type Point = { col: number; vrow: number };

export function layoutWorkbenchGrid(
  slots: WorkbenchGridSlot[],
): WorkbenchGridLayout {
  const occupied = new Set<string>();
  const virtual: Array<Point | null> = [];

  for (let col = WORKBENCH_GUN_COL; col < WORKBENCH_GUN_COL + WORKBENCH_GUN_COL_SPAN; col += 1) {
    occupied.add(cellKey(col, 0));
  }

  const placeAt = (col: number, vrow: number): Point | null => {
    if (col < 1 || col > WORKBENCH_GRID_COLS) return null;
    const key = cellKey(col, vrow);
    if (occupied.has(key)) return null;
    occupied.add(key);
    return { col, vrow };
  };

  const placeUp = (col: number, startVrow: number): Point | null => {
    for (let v = startVrow; v >= startVrow - 20; v -= 1) {
      const hit = placeAt(col, v);
      if (hit) return hit;
    }
    return null;
  };

  const placeDown = (col: number, startVrow: number): Point | null => {
    for (let v = startVrow; v <= startVrow + 20; v += 1) {
      const hit = placeAt(col, v);
      if (hit) return hit;
    }
    return null;
  };

  const placeDiagonalDown = (col: number): Point | null => {
    for (let vrow = 1; vrow <= 10; vrow += 1) {
      for (const next of [col - 1, col + 1]) {
        if (next >= 1 && next < WORKBENCH_GUN_COL) {
          const hit = placeAt(next, vrow);
          if (hit) return hit;
        }
      }
    }
    return null;
  };

  const presentFamilies = new Set(slots.map((row) => row.family));
  const leftQueue = LEFT_ORDER.filter((name) => presentFamilies.has(name));
  const leftColMap: Partial<Record<WorkbenchSlotFamily, number>> = {};
  leftQueue.forEach((name, index) => {
    leftColMap[name] = WORKBENCH_GUN_COL - 1 - index;
  });

  let muzzleCol = leftColMap.muzzle;
  if (muzzleCol == null) {
    if (leftQueue.length) {
      const outermost = leftColMap[leftQueue[leftQueue.length - 1]];
      muzzleCol = Math.max(1, (outermost || WORKBENCH_GUN_COL - 1) - 1);
    } else {
      muzzleCol = WORKBENCH_GUN_COL - 1;
    }
  }

  let tacticalCount = 0;
  let bottomLeftCol = WORKBENCH_GUN_COL;
  let stockChildVrow = 1;
  const installPos = new Map<string, Point>();

  for (const slot of slots) {
    const placed = ((): Point | null => {
      if (EXTRAS.has(slot.family)) return null;

      if (slot.family in leftColMap) {
        const col = leftColMap[slot.family];
        if (col != null) {
          const hit = placeAt(col, 0);
          if (hit) return hit;
        }
      }

      if (slot.family === "charge") {
        const primary = placeAt(WORKBENCH_STOCK_COL, -1);
        if (primary) return primary;
        return placeAt(bottomLeftCol--, 1);
      }

      if (slot.parentFamily === "stock") {
        return placeAt(WORKBENCH_STOCK_COL, stockChildVrow++);
      }

      if (slot.family === "stock") {
        return placeAt(WORKBENCH_STOCK_COL, 0);
      }

      if (slot.family === "tactical" && slot.isBase) {
        tacticalCount += 1;
        return placeAt(WORKBENCH_GUN_COL, -tacticalCount);
      }

      if (
        slot.family in TOP_COL &&
        (slot.isBase || slot.parentFamily === "receiver")
      ) {
        const col = TOP_COL[slot.family];
        if (col != null) return placeUp(col, -1);
      }

      if (slot.isBase && slot.family in BOTTOM_COL) {
        const col = BOTTOM_COL[slot.family];
        if (col != null) return placeDown(col, 1);
      }

      if (slot.isBase && BOTTOM_LEFT.has(slot.family)) {
        return placeAt(bottomLeftCol--, 1);
      }

      if (slot.family === "front_sight") {
        return placeAt(muzzleCol, -1);
      }

      const parent = slot.parentSlotId
        ? installPos.get(slot.parentSlotId)
        : undefined;
      if (parent) {
        if (parent.vrow < 0) return placeUp(parent.col, parent.vrow - 1);
        if (parent.vrow > 0) return placeDown(parent.col, parent.vrow + 1);
        if (parent.col < WORKBENCH_GUN_COL) {
          if (slot.family === "mount") return placeDiagonalDown(parent.col);
          if (slot.family === "scope" || slot.family === "tactical") {
            return placeUp(parent.col, -1);
          }
          return placeDown(parent.col, 1);
        }
        return placeDown(parent.col, 1);
      }

      return null;
    })();

    virtual.push(placed);
    if (placed && !slot.empty) {
      installPos.set(slot.slotId, placed);
    }
  }

  const vrows = virtual.filter((row): row is Point => Boolean(row)).map((row) => row.vrow);
  const minVrow = vrows.length ? Math.min(...vrows, 0) : 0;
  const maxVrow = vrows.length ? Math.max(...vrows, 0) : 0;
  const totalRows = maxVrow - minVrow + 1;
  const gunRow = 0 - minVrow + 1;

  const cells = slots.map((slot, index) => {
    const pos = virtual[index];
    if (!pos) {
      return { ...slot, col: null, row: null, extras: true };
    }
    return {
      ...slot,
      col: pos.col,
      row: pos.vrow - minVrow + 1,
      extras: false,
    };
  });

  return { cells, gunRow, totalRows };
}

function cellKey(col: number, vrow: number): string {
  return `${col},${vrow}`;
}
