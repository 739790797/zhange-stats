import {
  cheapestPrice,
  extractRefItemId,
  type CatalogPriceRow,
} from "@/lib/tarkovItemFormat";
import {
  formatArmorMaterial,
  formatArmorSlotLabel,
  formatArmorType,
  formatArmorZoneList,
} from "@/lib/tarkovArmorLabels";
import {
  itemDetailHref,
  itemSlugFromTypes,
} from "@/lib/tarkovItemTypes";

export type PlatePresetKind = "default" | "stripped";

export type PlateTableRow = {
  key: string;
  id: string;
  name: string;
  icon: string;
  types: string[];
  slot: string;
  class: number | null;
  material: string;
  armorType: string;
  ergoPenalty: number | null;
  speedPenalty: number | null;
  turnPenalty: number | null;
  durability: number | null;
  weight: number | null;
  price: number | null;
  badges: PlatePresetKind[];
};

export type PlateFilterKey = "slot" | "class" | "material" | "armorType";

export type PlatePresetMark = {
  kind: PlatePresetKind;
  name: string;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function finiteNumber(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function displayName(value: unknown): string {
  return String(value || "").trim();
}

function itemTypesOf(value: unknown): string[] {
  const row = asRecord(value);
  return stringList(row?.types);
}

function isGunTypes(types: string[]): boolean {
  return types.includes("gun");
}

/** 枪预设要留独立页（机匣 wiki）；胸挂 / 护甲预设折回本体。 */
export function isCollapsedItemPreset(
  types: string[],
  baseTypes: string[],
): boolean {
  if (!types.includes("preset")) return false;
  if (isGunTypes(types) || isGunTypes(baseTypes)) return false;
  return true;
}

export function collapsedPresetHref(
  detail: {
    id?: string;
    item?: unknown;
    properties?: unknown;
  } | null | undefined,
): string | null {
  if (!detail) return null;
  const item = asRecord(detail.item);
  const properties = asRecord(detail.properties);
  const types = stringList(item?.types);
  const base = properties?.baseItem ?? item?.baseItem;
  const baseId = extractRefItemId(base);
  const selfId = String(detail.id || "").trim();
  if (!baseId || !selfId || baseId === selfId) return null;
  const baseTypes = itemTypesOf(base);
  if (!isCollapsedItemPreset(types, baseTypes)) return null;
  return itemDetailHref(itemSlugFromTypes(baseTypes), baseId);
}

export function presetKindFromName(
  name: string,
  isDefault?: boolean,
): PlatePresetKind | null {
  if (isDefault) return "default";
  const text = name.trim().toLowerCase();
  if (!text) return null;
  if (/\bstripped\b/.test(text) || text.includes("剥离")) return "stripped";
  if (text.endsWith("默认") || text.includes(" default")) return "default";
  return null;
}

function presetLabel(kind: PlatePresetKind): string {
  return kind === "default" ? "默认" : "Stripped";
}

function containedIds(preset: Record<string, unknown>): Set<string> {
  const out = new Set<string>();
  const rows = Array.isArray(preset.containsItems) ? preset.containsItems : [];
  for (const entry of rows) {
    const row = asRecord(entry);
    const item = row?.item ?? entry;
    const id = extractRefItemId(item);
    if (!id) continue;
    out.add(id);
  }
  return out;
}

function collectPresetMarks(
  properties: Record<string, unknown> | undefined,
): Array<{ kind: PlatePresetKind; name: string; plateIds: Set<string> }> {
  if (!properties) return [];
  const seen = new Set<string>();
  const out: Array<{
    kind: PlatePresetKind;
    name: string;
    plateIds: Set<string>;
  }> = [];
  const presets: unknown[] = [];
  if (properties.defaultPreset) presets.push(properties.defaultPreset);
  if (Array.isArray(properties.presets)) presets.push(...properties.presets);
  for (const entry of presets) {
    const row = asRecord(entry);
    if (!row) continue;
    const id = extractRefItemId(row);
    const name =
      displayName(row.name) || displayName(row.shortName) || id;
    const kind = presetKindFromName(name, row.default === true);
    if (!kind) continue;
    const key = `${kind}:${id || name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ kind, name, plateIds: containedIds(row) });
  }
  return out;
}

export function platePresetMarks(
  properties: Record<string, unknown> | undefined,
): PlatePresetMark[] {
  const seen = new Set<PlatePresetKind>();
  const out: PlatePresetMark[] = [];
  for (const row of collectPresetMarks(properties)) {
    if (seen.has(row.kind)) continue;
    seen.add(row.kind);
    out.push({ kind: row.kind, name: presetLabel(row.kind) });
  }
  return out;
}

function plateMaterial(value: unknown): string {
  return formatArmorMaterial(value);
}

function plateArmorType(value: unknown): string {
  return formatArmorType(value);
}

function plateFilterValue(
  row: PlateTableRow,
  key: PlateFilterKey,
): string {
  const raw = row[key];
  if (raw == null || raw === "") return "";
  return String(raw);
}

export function plateColumnFilters(
  rows: PlateTableRow[],
  key: PlateFilterKey,
): Array<{ text: string; value: string }> {
  const seen = new Set<string>();
  const out: Array<{ text: string; value: string }> = [];
  for (const row of rows) {
    const value = plateFilterValue(row, key);
    if (seen.has(value)) continue;
    seen.add(value);
    out.push({ text: value || "—", value });
  }
  out.sort((left, right) => {
    if (!left.value) return 1;
    if (!right.value) return -1;
    if (key === "class") return Number(left.value) - Number(right.value);
    return left.text.localeCompare(right.text, "zh");
  });
  return out;
}

export function plateColumnMatch(
  row: PlateTableRow,
  key: PlateFilterKey,
  value: boolean | string | number | bigint,
): boolean {
  return plateFilterValue(row, key) === String(value);
}

function platePrice(row: Record<string, unknown>): number | null {
  return cheapestPrice({
    last_low_price: finiteNumber(row.lastLowPrice ?? row.last_low_price),
    avg24h_price: finiteNumber(row.avg24hPrice ?? row.avg24h_price),
    base_price: finiteNumber(row.basePrice ?? row.base_price),
  } satisfies CatalogPriceRow);
}

export function extractPlateTableRows(
  properties: Record<string, unknown> | undefined,
): PlateTableRow[] {
  const slots = properties?.armorSlots;
  if (!Array.isArray(slots)) return [];
  const marks = collectPresetMarks(properties);
  const rows: PlateTableRow[] = [];
  slots.forEach((slot, slotIndex) => {
    const rec = asRecord(slot);
    if (!rec || !Array.isArray(rec.allowedPlates)) return;
    const zones = formatArmorZoneList(rec.zones);
    const slotName =
      formatArmorSlotLabel(String(rec.name || "").trim()) ||
      zones ||
      "插板槽";
    rec.allowedPlates.forEach((plate, plateIndex) => {
      const row = asRecord(plate);
      if (!row) return;
      const id = String(row.id || "").trim();
      const name =
        displayName(row.name) || displayName(row.shortName);
      if (!id || !name) return;
      const durability =
        finiteNumber(row.durability) ?? finiteNumber(row.maxDurability);
      const badges: PlatePresetKind[] = [];
      for (const mark of marks) {
        if (mark.plateIds.has(id) && !badges.includes(mark.kind)) {
          badges.push(mark.kind);
        }
      }
      rows.push({
        key: `${slotIndex}-${plateIndex}-${id}`,
        id,
        name,
        icon: String(row.iconLink || row.baseImageLink || row.icon_link || ""),
        types: stringList(row.types),
        slot: slotName,
        class: finiteNumber(row.class),
        material: plateMaterial(row.material),
        armorType: plateArmorType(row.armorType),
        ergoPenalty: finiteNumber(row.ergoPenalty),
        speedPenalty: finiteNumber(row.speedPenalty),
        turnPenalty: finiteNumber(row.turnPenalty),
        durability,
        weight: finiteNumber(row.weight),
        price: platePrice(row),
        badges,
      });
    });
  });
  return rows;
}

export function plateBadgeLabel(kind: PlatePresetKind): string {
  return presetLabel(kind);
}
