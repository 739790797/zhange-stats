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

/** 工作台中间配件示意图：dump 没有整枪照片坐标，按 nameId 落到侧视分区。枪口朝左。 */

export type WorkbenchIconInput = {
  slotId: string;
  nameId: string;
  itemId: string;
  icon: string;
  label: string;
  slotName: string;
  required: boolean;
  empty: boolean;
};

export type WorkbenchLaidIcon = WorkbenchIconInput & {
  x: number;
  y: number;
};

type Point = { x: number; y: number };

const ANCHORS: Array<{ test: (id: string) => boolean; point: Point }> = [
  { test: (id) => id.includes("muzzle"), point: { x: 10, y: 48 } },
  { test: (id) => id.includes("barrel"), point: { x: 24, y: 48 } },
  { test: (id) => id.includes("gas"), point: { x: 28, y: 32 } },
  { test: (id) => id.includes("sight_front") || id.includes("front_sight"), point: { x: 22, y: 34 } },
  { test: (id) => id.includes("handguard") || id.includes("foregrip"), point: { x: 34, y: 58 } },
  { test: (id) => id.includes("bipod"), point: { x: 30, y: 78 } },
  { test: (id) => id.includes("tactical") || id.includes("flashlight") || id.includes("laser"), point: { x: 32, y: 68 } },
  { test: (id) => id.includes("mount") && !id.includes("scope"), point: { x: 40, y: 36 } },
  { test: (id) => id.includes("magazine") || id.includes("mag_"), point: { x: 44, y: 78 } },
  { test: (id) => id.includes("pistol_grip") || id.includes("pistolgrip"), point: { x: 50, y: 72 } },
  { test: (id) => id.includes("charge"), point: { x: 50, y: 34 } },
  {
    test: (id) =>
      id.includes("scope") ||
      id.includes("sight_rear") ||
      id.includes("rear_sight") ||
      id.includes("sight"),
    point: { x: 52, y: 26 },
  },
  { test: (id) => id.includes("stock") || id.includes("buffer"), point: { x: 80, y: 48 } },
  { test: (id) => id === "receiver" || id.includes("reciever") || id.includes("receiver"), point: { x: 50, y: 48 } },
];

export function slotAnchor(nameId: string): Point {
  const id = (nameId || "").toLowerCase();
  for (const row of ANCHORS) {
    if (row.test(id)) return { ...row.point };
  }
  return unknownAnchor(id);
}

function unknownAnchor(nameId: string): Point {
  let hash = 0;
  for (let i = 0; i < nameId.length; i += 1) {
    hash = (hash * 33 + nameId.charCodeAt(i)) >>> 0;
  }
  const angle = ((hash % 360) * Math.PI) / 180;
  return {
    x: clamp(50 + Math.cos(angle) * 22, 8, 92),
    y: clamp(50 + Math.sin(angle) * 16, 12, 88),
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

type SlotHotspotNode = {
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

/** 含空槽：点枪图换配件时，未装的槽位也要能点。 */
export function collectSlotHotspots(nodes: SlotHotspotNode[]): WorkbenchIconInput[] {
  const out: WorkbenchIconInput[] = [];
  for (const node of nodes || []) {
    const itemId = node.installed?.id || "";
    const slotName = node.name || node.name_id || node.id;
    out.push({
      slotId: node.id,
      nameId: node.name_id || "",
      itemId,
      icon: node.installed?.icon_link || "",
      label: itemId
        ? node.installed?.short_name || node.installed?.name || itemId
        : slotName,
      slotName,
      required: Boolean(node.required),
      empty: !itemId,
    });
    if (node.children?.length) {
      out.push(
        ...collectSlotHotspots(node.children as SlotHotspotNode[]),
      );
    }
  }
  return out;
}

/** 同类槽位微偏，避免完全重叠。 */
export function layoutWorkbenchIcons(
  items: WorkbenchIconInput[],
): WorkbenchLaidIcon[] {
  const seen: Record<string, number> = {};
  return items.map((item) => {
    const family = slotFamily(item.nameId);
    const index = seen[family] || 0;
    seen[family] = index + 1;
    const base = slotAnchor(item.nameId);
    const dx = (index % 3) * 6;
    const dy = Math.floor(index / 3) * 8;
    return {
      ...item,
      x: clamp(base.x + dx, 6, 94),
      y: clamp(base.y + dy, 10, 90),
    };
  });
}

function slotFamily(nameId: string): string {
  const id = (nameId || "").toLowerCase();
  const hit = ANCHORS.find((row) => row.test(id));
  return hit ? hit.point.x + "," + hit.point.y : id || "unknown";
}

/** 点枪图空白时落到最近槽位；超出 maxDist 当没点中。 */
export function nearestWorkbenchSlot(
  pieces: Array<{ slotId: string; x: number; y: number }>,
  x: number,
  y: number,
  maxDist = 22,
): string | null {
  let bestId: string | null = null;
  let best = Infinity;
  for (const piece of pieces) {
    const dx = piece.x - x;
    const dy = piece.y - y;
    const dist = dx * dx + dy * dy;
    if (dist < best) {
      best = dist;
      bestId = piece.slotId;
    }
  }
  return best <= maxDist * maxDist ? bestId : null;
}
