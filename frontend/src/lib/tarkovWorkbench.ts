import type { TarkovWorkbenchPair } from "@/api/guidesApi";

export type WorkbenchSlotWalkNode = {
  id: string;
  name?: string;
  installed?: {
    id?: string | null;
    name?: string;
    conflicting_ids?: string[] | null;
  } | null;
  children?: WorkbenchSlotWalkNode[];
};

export function pairsSignature(
  pairs: TarkovWorkbenchPair[] | undefined,
): string {
  return [...(pairs || [])]
    .filter((row) => row.slot_id && row.item_id)
    .map((row) => `${row.slot_id}:${row.item_id}`)
    .sort()
    .join(",");
}

export function pairsFromTree(
  nodes: WorkbenchSlotWalkNode[] | undefined,
): TarkovWorkbenchPair[] {
  const out: TarkovWorkbenchPair[] = [];
  for (const node of nodes || []) {
    const installedId = node.installed?.id;
    if (installedId) {
      out.push({ slot_id: node.id, item_id: installedId });
    }
    if (node.children?.length) {
      out.push(...pairsFromTree(node.children));
    }
  }
  return out;
}

export function findSlotNode<T extends WorkbenchSlotWalkNode>(
  nodes: T[] | undefined,
  slotId: string,
): T | null {
  for (const node of nodes || []) {
    if (node.id === slotId) return node;
    const hit = findSlotNode(node.children as T[] | undefined, slotId);
    if (hit) return hit;
  }
  return null;
}

export function collectSlotIds(
  nodes: WorkbenchSlotWalkNode[] | undefined,
): string[] {
  const out: string[] = [];
  for (const node of nodes || []) {
    if (node.id) out.push(node.id);
    if (node.children?.length) out.push(...collectSlotIds(node.children));
  }
  return out;
}

export function collectInstalledParts(
  nodes: WorkbenchSlotWalkNode[] | undefined,
): Array<{ id: string; conflicting_ids?: string[] | null }> {
  const out: Array<{ id: string; conflicting_ids?: string[] | null }> = [];
  for (const node of nodes || []) {
    const id = node.installed?.id;
    if (id) {
      out.push({
        id,
        conflicting_ids: node.installed?.conflicting_ids,
      });
    }
    if (node.children?.length) {
      out.push(...collectInstalledParts(node.children));
    }
  }
  return out;
}

export function replacePair(
  pairs: TarkovWorkbenchPair[],
  slotId: string,
  itemId: string | null,
  dropSlotIds: string[] = [],
): TarkovWorkbenchPair[] {
  const drop = new Set([slotId, ...dropSlotIds]);
  const next = pairs.filter((row) => !drop.has(row.slot_id));
  if (itemId) next.push({ slot_id: slotId, item_id: itemId });
  return next;
}

export function replaceSlotInstalled<T extends WorkbenchSlotWalkNode>(
  nodes: T[] | undefined,
  slotId: string,
  part: T["installed"] | null,
): T[] {
  return (nodes || []).map((node) => {
    if (node.id === slotId) {
      return { ...node, installed: part, children: [] };
    }
    return {
      ...node,
      children: replaceSlotInstalled(node.children as T[] | undefined, slotId, part),
    };
  });
}

export function partConflictsWith(
  part: { id: string; conflicting_ids?: string[] | null },
  installedIds: Iterable<string>,
  replacingId?: string | null,
  installedParts: Array<{ id: string; conflicting_ids?: string[] | null }> = [],
): boolean {
  const others = new Set(installedIds);
  others.delete(part.id);
  if (replacingId) others.delete(replacingId);
  if ((part.conflicting_ids || []).some((id) => others.has(id))) return true;
  return installedParts.some(
    (other) => others.has(other.id) && (other.conflicting_ids || []).includes(part.id),
  );
}

export function formatSignedStat(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value === 0) return "0";
  const rounded = Math.round(value * 100) / 100;
  return rounded > 0 ? `+${rounded}` : String(rounded);
}

export type WorkbenchPartSortKey =
  | "name"
  | "ergonomics"
  | "recoil"
  | "weight"
  | "price";

export type WorkbenchPartSortDir = "asc" | "desc";

export type WorkbenchPartSort = {
  key: WorkbenchPartSortKey;
  dir: WorkbenchPartSortDir;
};

export const DEFAULT_WORKBENCH_PART_SORT: WorkbenchPartSort = {
  key: "ergonomics",
  dir: "desc",
};

type WorkbenchSortablePart = {
  id: string;
  name?: string;
  short_name?: string;
  ergonomics?: number;
  recoil_modifier?: number;
  weight?: number;
  price_rub?: number | null;
};

export function filterWorkbenchParts<T extends WorkbenchSortablePart>(
  parts: T[],
  query: string,
): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return parts;
  return parts.filter((part) => {
    const name = (part.name || "").toLowerCase();
    const shortName = (part.short_name || "").toLowerCase();
    return name.includes(q) || shortName.includes(q);
  });
}

export function toggleWorkbenchPartSort(
  current: WorkbenchPartSort,
  nextKey: WorkbenchPartSortKey,
): WorkbenchPartSort {
  if (current.key === nextKey) {
    return { key: nextKey, dir: current.dir === "asc" ? "desc" : "asc" };
  }
  return { key: nextKey, dir: nextKey === "name" ? "asc" : "desc" };
}

export function sortWorkbenchParts<T extends WorkbenchSortablePart>(
  parts: T[],
  sort: WorkbenchPartSort,
): T[] {
  const sign = sort.dir === "asc" ? 1 : -1;
  return [...parts].sort((a, b) => {
    const cmp = compareWorkbenchPartField(a, b, sort.key) * sign;
    if (cmp !== 0) return cmp;
    return (a.name || a.short_name || a.id).localeCompare(
      b.name || b.short_name || b.id,
      "zh",
    );
  });
}

function compareWorkbenchPartField(
  a: WorkbenchSortablePart,
  b: WorkbenchSortablePart,
  key: WorkbenchPartSortKey,
): number {
  if (key === "name") {
    return (a.name || a.short_name || a.id).localeCompare(
      b.name || b.short_name || b.id,
      "zh",
    );
  }
  const left = workbenchPartSortValue(a, key);
  const right = workbenchPartSortValue(b, key);
  return left - right;
}

function workbenchPartSortValue(
  part: WorkbenchSortablePart,
  key: Exclude<WorkbenchPartSortKey, "name">,
): number {
  if (key === "ergonomics") return part.ergonomics || 0;
  if (key === "recoil") return part.recoil_modifier || 0;
  if (key === "weight") return part.weight || 0;
  return part.price_rub || 0;
}
