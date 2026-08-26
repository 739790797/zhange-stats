import { formatCaliberLabel } from "@/lib/tarkovAmmoCategories";
import {
  handbookHrefFromCategoryId,
  isGenericItemCategoryId,
  itemHrefFromTypes,
} from "@/lib/tarkovItemTypes";

export type CatalogPriceRow = {
  last_low_price?: number | null;
  avg24h_price?: number | null;
  base_price?: number | null;
  width?: number | null;
  height?: number | null;
  properties?: Record<string, unknown> | null;
};

export type CatalogColumnId =
  | "name"
  | "grid"
  | "slots"
  | "weight"
  | "slotRatio"
  | "pricePerSlot"
  | "class"
  | "zones"
  | "durability"
  | "ricochet"
  | "turnPenalty"
  | "blocksHeadset"
  | "blindness"
  | "distance"
  | "fuse"
  | "fragments"
  | "radius"
  | "grenadeType"
  | "energy"
  | "hydration"
  | "useTime"
  | "uses"
  | "ergo"
  | "recoil"
  | "loudness"
  | "hp"
  | "price";

const DEFAULT_COLUMNS: CatalogColumnId[] = [
  "name",
  "grid",
  "weight",
  "price",
];

/** 对齐 tarkov.dev 各分类 SmallItemTable 列。 */
const COLUMN_PRESETS: Record<string, CatalogColumnId[]> = {
  backpacks: ["name", "grid", "slots", "weight", "slotRatio", "pricePerSlot", "price"],
  containers: ["name", "grid", "slots", "weight", "slotRatio", "pricePerSlot", "price"],
  rigs: ["name", "grid", "slots", "class", "weight", "price"],
  armors: ["name", "class", "zones", "durability", "weight", "price"],
  helmets: [
    "name",
    "class",
    "zones",
    "ricochet",
    "turnPenalty",
    "blocksHeadset",
    "price",
  ],
  glasses: ["name", "class", "blindness", "price"],
  headsets: ["name", "distance", "weight", "price"],
  grenades: ["name", "grenadeType", "fuse", "fragments", "radius", "price"],
  provisions: ["name", "energy", "hydration", "useTime", "price"],
  keys: ["name", "uses", "grid", "price"],
  barter: ["name", "grid", "weight", "price"],
  meds: ["name", "hp", "useTime", "price"],
  "weapon-mods": ["name", "ergo", "recoil", "price"],
  "pistol-grips": ["name", "ergo", "price"],
  suppressors: ["name", "ergo", "recoil", "loudness", "price"],
  gear: ["name", "grid", "weight", "price"],
  money: ["name", "grid", "price"],
  maps: ["name", "grid", "price"],
  "quest-items": ["name", "grid", "weight", "price"],
  "info-items": ["name", "grid", "weight", "price"],
  "special-equipment": ["name", "grid", "weight", "price"],
  "battle-pass": ["name", "grid", "price"],
};

export const CATALOG_COLUMN_LABELS: Record<CatalogColumnId, string> = {
  name: "名称",
  grid: "格子",
  slots: "内部格",
  weight: "重量",
  slotRatio: "格效",
  pricePerSlot: "每格价",
  class: "等级",
  zones: "防护部位",
  durability: "耐久",
  ricochet: "跳弹",
  turnPenalty: "转向",
  blocksHeadset: "挡耳机",
  blindness: "闪光防护",
  distance: "听力",
  fuse: "引信",
  fragments: "破片",
  radius: "半径",
  grenadeType: "类型",
  energy: "能量",
  hydration: "水分",
  useTime: "使用",
  uses: "次数",
  ergo: "人机",
  recoil: "后座",
  loudness: "响度",
  hp: "生命",
  price: "价格",
};

const SKIP_PROP_KEYS = new Set([
  "grid",
  "__typename",
  "slots",
  "armorSlots",
  "content",
  "propertiesType",
  "pouches",
  "conflictingSlotIds",
  "defaultAmmo",
  "default",
]);

const PROP_LABELS: Record<string, string> = {
  weight: "重量",
  size: "尺寸",
  caliber: "口径",
  ammoType: "弹药类型",
  stackMaxSize: "堆叠",
  tracer: "曳光",
  tracerColor: "曳光色",
  projectileCount: "弹丸数",
  damage: "威力",
  penetrationPower: "穿透力",
  penetrationChance: "穿透概率",
  penetrationPowerDeviation: "穿透偏差",
  armorDamage: "对甲",
  initialSpeed: "初速",
  accuracyModifier: "精度",
  recoilModifier: "后座",
  lightBleedModifier: "小出血",
  heavyBleedModifier: "大出血",
  fragmentationChance: "碎弹率",
  ricochetChance: "跳弹率",
  durabilityBurnFactor: "耐久损耗",
  staminaBurnPerDamage: "耐力消耗",
  ballisticCoeficient: "弹道系数",
  bulletDiameterMilimeters: "弹径 mm",
  bulletMassGrams: "弹重 g",
  misfireChance: "哑火",
  failureToFeedChance: "卡弹",
  class: "护甲等级",
  durability: "耐久",
  maxDurability: "最大耐久",
  repairCost: "修理花费",
  ergoPenalty: "人机惩罚",
  speedPenalty: "移速惩罚",
  turnPenalty: "转向惩罚",
  bluntThroughput: "钝伤穿透",
  zones: "防护部位",
  headZones: "头部防护",
  material: "材质",
  armorType: "护甲类型",
  useTime: "使用时间",
  cures: "治疗",
  hitpoints: "生命",
  maxHealPerUse: "单次治疗",
  hpCostLightBleeding: "小出血耗血",
  hpCostHeavyBleeding: "大出血耗血",
  energyImpact: "能量",
  hydrationImpact: "水分",
  painkillerDuration: "止疼时长",
  minLimbHealth: "肢体最低生命",
  maxLimbHealth: "肢体最高生命",
  units: "份数",
  uses: "次数",
  function: "功能",
  ergonomics: "人机",
  recoil: "后座",
  capacity: "容量",
  grids: "格仓",
  loadModifier: "装填",
  ammoCheckModifier: "查弹",
  malfunctionChance: "故障率",
  allowedAmmo: "可用弹药",
  presets: "预设",
  conflictingItems: "冲突物品",
  conflictingCategories: "冲突分类",
  distanceModifier: "听力距离",
  distortion: "失真",
  ambientVolume: "环境音",
  compressorAttack: "压缩启动",
  compressorGain: "压缩增益",
  compressorRelease: "压缩释放",
  compressorThreshold: "压缩阈值",
  compressorVolume: "压缩音量",
  cutoffFrequency: "截止频率",
  dryVolume: "干音量",
  highFrequencyGain: "高频增益",
  resonance: "共振",
  blindnessProtection: "闪光防护",
  blocksHeadset: "挡住耳机",
  ricochetX: "跳弹 X",
  ricochetY: "跳弹",
  ricochetZ: "跳弹 Z",
  deafening: "听力影响",
  fuse: "引信",
  fragments: "破片数",
  fragmentation: "破片伤害",
  minExplosionDistance: "最小爆炸距离",
  maxExplosionDistance: "最大爆炸距离",
  contusionRadius: "震荡半径",
  type: "类型",
  energy: "能量",
  hydration: "水分",
  loudness: "响度",
  accuracy: "精度",
  velocity: "初速",
  heatFactor: "积热",
  coolingFactor: "散热",
  centerOfImpact: "散布",
  deviationCurve: "散布曲线",
  deviationMax: "最大散布",
  defaultAmmo: "默认弹药",
  fireRate: "射速",
  effectiveDistance: "有效距离",
  fireModes: "射击模式",
  recoilVertical: "垂直后座",
  recoilHorizontal: "水平后座",
  recoilDispersion: "后座散布",
  recoilAngle: "后座角度",
  cameraRecoil: "镜头后座",
  cameraSnap: "镜头回正",
  convergence: "收敛",
  sightingRange: "瞄具距离",
  sightModes: "瞄具模式",
  zoomLevels: "变倍",
  slashDamage: "劈砍伤害",
  stabDamage: "刺击伤害",
  hitRadius: "攻击距离",
  intensity: "亮度",
  noiseIntensity: "噪点强度",
  noiseScale: "噪点缩放",
  diffuseIntensity: "漫射",
  moa: "MOA",
  defaultWidth: "默认宽",
  defaultHeight: "默认高",
  defaultErgonomics: "默认人机",
  defaultRecoilVertical: "默认垂直后座",
  defaultRecoilHorizontal: "默认水平后座",
  defaultWeight: "默认重量",
  categories: "分类",
  usedOnMaps: "地图",
  stimEffects: "注射效果",
  baseItem: "基础物品",
  defaultPreset: "默认预设",
  bodyPartsHealth: "部位生命",
};

export type FormattedPropLink = {
  label: string;
  href: string;
  id?: string;
  icon?: string;
  types?: string[];
  count?: number;
  badge?: string;
};

export type FormattedProp = {
  key: string;
  label: string;
  value: string;
  large?: boolean;
  links?: FormattedPropLink[];
  note?: string;
};

/** 枪械可用弹药里「默认」角标的说明。不单独占一行属性。 */
export const DEFAULT_AMMO_HINT =
  "标「默认」的是参考弹：瞄具归零按它的初速算；商人默认预设和战局里刷出的枪，弹匣里通常也是它。游戏检视界面不会单独列出。";

export function catalogColumnsForSlug(slug: string): CatalogColumnId[] {
  return COLUMN_PRESETS[slug] || DEFAULT_COLUMNS;
}

export function propsOf(
  row: Pick<CatalogPriceRow, "properties">,
): Record<string, unknown> {
  return row.properties && typeof row.properties === "object"
    ? (row.properties as Record<string, unknown>)
    : {};
}

export function numProp(
  props: Record<string, unknown>,
  ...keys: string[]
): number | null {
  for (const key of keys) {
    const n = Number(props[key]);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function boolProp(
  props: Record<string, unknown>,
  ...keys: string[]
): boolean | null {
  for (const key of keys) {
    const v = props[key];
    if (typeof v === "boolean") return v;
  }
  return null;
}

export function strProp(
  props: Record<string, unknown>,
  ...keys: string[]
): string {
  for (const key of keys) {
    const v = props[key];
    if (typeof v === "string" && v.trim()) return v.trim();
  }
  return "";
}

export function innerSlots(props: Record<string, unknown>): number | null {
  const cap = numProp(props, "capacity");
  if (cap != null && cap > 0) return cap;
  const grids = props.grids;
  if (!Array.isArray(grids)) return null;
  let total = 0;
  for (const grid of grids) {
    if (!grid || typeof grid !== "object") continue;
    const row = grid as { width?: number; height?: number };
    const w = Number(row.width);
    const h = Number(row.height);
    if (Number.isFinite(w) && Number.isFinite(h)) total += w * h;
  }
  return total > 0 ? total : null;
}

export function itemGridSize(
  row: Pick<CatalogPriceRow, "width" | "height">,
): string {
  if (row.width == null || row.height == null) return "—";
  return `${row.width}×${row.height}`;
}

export function formatWeight(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 1000) / 1000} kg`;
}

export function formatDurationSeconds(
  value: number | null | undefined,
): string {
  if (value == null || !Number.isFinite(value) || value <= 0) return "即时";
  const total = Math.round(value);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const parts: string[] = [];
  if (h) parts.push(`${h} 小时`);
  if (m) parts.push(`${m} 分`);
  if (s && !h) parts.push(`${s} 秒`);
  return parts.join(" ") || "即时";
}

export function formatMoney(
  value: number | null | undefined,
  currency = "RUB",
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const code = (currency || "RUB").toUpperCase();
  const symbol = code === "USD" ? "$" : code === "EUR" ? "€" : "₽";
  return `${Math.round(value).toLocaleString("zh-CN")} ${symbol}`;
}

export function cheapestPrice(
  row: Pick<CatalogPriceRow, "last_low_price" | "avg24h_price" | "base_price">,
): number | null {
  for (const n of [row.last_low_price, row.avg24h_price, row.base_price]) {
    if (n != null && Number.isFinite(n) && n > 0) return n;
  }
  return null;
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 1000) / 10}%`;
}

export function formatSigned(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const n = Math.round(value * 100) / 100;
  return n > 0 ? `+${n}` : String(n);
}

function zonesFormat(value: unknown): string {
  if (!Array.isArray(value)) return typeof value === "string" ? value : "";
  return value
    .map((zone) => String(zone || "").trim())
    .filter(Boolean)
    .join(" · ");
}

function gridsFormat(value: unknown): string {
  if (!Array.isArray(value)) return "";
  const counts = new Map<string, number>();
  for (const grid of value) {
    if (!grid || typeof grid !== "object") continue;
    const row = grid as { width?: number; height?: number };
    const w = Number(row.width);
    const h = Number(row.height);
    if (!Number.isFinite(w) || !Number.isFinite(h)) continue;
    const label = `${w}×${h}`;
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, n]) => (n > 1 ? `${label} ×${n}` : label))
    .join(", ");
}

/** json.tarkov.dev / BSG 物品 id 多为 24 位 hex。 */
export function isBareTarkovId(value: string): boolean {
  return /^[a-f0-9]{24}$/i.test(value.trim());
}

function displayName(value: string | undefined | null): string {
  const text = String(value || "").trim();
  if (!text || isBareTarkovId(text)) return "";
  return text;
}

function namedList(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value
    .map((entry) => {
      if (typeof entry === "string") return displayName(entry);
      if (entry && typeof entry === "object" && "name" in entry) {
        const row = entry as { id?: string; name?: string };
        if (row.id && isGenericItemCategoryId(String(row.id))) return "";
        return displayName(row.name);
      }
      return "";
    })
    .filter(Boolean)
    .join(" · ");
}

export function formatPropValue(key: string, value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (SKIP_PROP_KEYS.has(key)) return null;
  if (typeof value === "boolean") return value ? "是" : "否";
  if (key === "caliber" && typeof value === "string") {
    return formatCaliberLabel(value);
  }
  if (key === "weight" && typeof value === "number") {
    return formatWeight(value);
  }
  if (
    (key === "speedPenalty" || key === "turnPenalty" || key === "ergoPenalty") &&
    typeof value === "number"
  ) {
    return formatPercent(value);
  }
  if (key === "armorDamage" && typeof value === "number") {
    return `${value}%`;
  }
  if (key === "zones" || key === "headZones") {
    const text = zonesFormat(value);
    return text || null;
  }
  if (key === "grids") {
    const text = gridsFormat(value);
    return text || null;
  }
  if (key === "material") {
    if (typeof value === "string") return value;
    if (value && typeof value === "object" && "name" in value) {
      return String((value as { name?: string }).name || "") || null;
    }
    return null;
  }
  if (key === "baseItem" || key === "defaultPreset") {
    if (value && typeof value === "object") {
      const row = value as { name?: string; shortName?: string };
      return displayName(row.name) || displayName(row.shortName) || null;
    }
    if (typeof value === "string") return displayName(value) || null;
    return null;
  }
  if (key === "categories" || key === "usedOnMaps" || key === "allowedAmmo" || key === "presets" || key === "conflictingItems" || key === "conflictingCategories") {
    const text = namedList(value);
    return text || null;
  }
  if (key === "zoomLevels" && Array.isArray(value)) {
    const zoom = new Set<string>();
    for (const levels of value) {
      if (!Array.isArray(levels)) continue;
      for (const n of levels) {
        if (Number.isFinite(Number(n))) zoom.add(String(n));
      }
    }
    return zoom.size ? [...zoom].join(", ") : null;
  }
  if (key === "bodyPartsHealth" && Array.isArray(value)) {
    const text = value
      .map((part) => {
        if (!part || typeof part !== "object") return "";
        const row = part as { bodyPart?: string; max?: number };
        const name = String(row.bodyPart || "").trim();
        if (!name) return "";
        return row.max != null ? `${name}: ${row.max}` : name;
      })
      .filter(Boolean)
      .join(" · ");
    return text || null;
  }
  if (key === "stimEffects" && Array.isArray(value)) {
    const text = value
      .map((effect) => {
        if (!effect || typeof effect !== "object") return "";
        const row = effect as {
          skillName?: string;
          type?: string;
          value?: number;
          percent?: boolean;
          chance?: number;
        };
        const name = row.skillName || row.type || "";
        if (!name) return "";
        const amount =
          row.value && row.value !== 0
            ? `${row.value > 0 ? "+" : ""}${row.value}${row.percent ? "%" : ""}`
            : "";
        const chance =
          row.chance != null && row.chance !== 1
            ? ` ${Math.round(row.chance * 100)}%`
            : "";
        return amount || chance ? `${name}: ${amount}${chance}` : name;
      })
      .filter(Boolean)
      .join("；");
    return text || null;
  }
  if (Array.isArray(value)) {
    if (!value.length) return null;
    if (value.every((x) => typeof x !== "object")) {
      const parts = value
        .map((entry) => displayName(String(entry)))
        .filter(Boolean);
      return parts.length ? parts.join(", ") : null;
    }
    return null;
  }
  if (typeof value === "object") return null;
  return displayName(String(value)) || null;
}

export function formatPropertyList(
  properties: Record<string, unknown> | undefined,
): FormattedProp[] {
  if (!properties) return [];
  const preferred = Object.keys(PROP_LABELS).filter(
    (key) => key in properties && !SKIP_PROP_KEYS.has(key),
  );
  const rest = Object.keys(properties)
    .filter((key) => !PROP_LABELS[key] && !SKIP_PROP_KEYS.has(key))
    .sort();
  const rows: FormattedProp[] = [];
  for (const key of [...preferred, ...rest]) {
    const value = formatPropValue(key, properties[key]);
    if (value == null) continue;
    const links = extractPropLinks(key, properties[key]);
    const itemChips = links.filter((link) => Boolean(link.id)).length;
    rows.push({
      key,
      label: PROP_LABELS[key] || key,
      value,
      large: itemChips > 1 || value.length >= 40 || links.length > 4,
      links: links.length ? links : undefined,
    });
  }
  return markDefaultAmmoInAllowed(rows, properties);
}

export function extractRefItemId(value: unknown): string {
  if (typeof value === "string") return value.trim();
  const row = asRecord(value);
  return row ? String(row.id || "").trim() : "";
}

function markDefaultAmmoInAllowed(
  rows: FormattedProp[],
  properties: Record<string, unknown>,
): FormattedProp[] {
  const defaultId = extractRefItemId(properties.defaultAmmo);
  if (!defaultId) return rows;
  const fallback = itemRefLink(properties.defaultAmmo, ["ammo"]);
  return rows.map((row) => {
    if (row.key !== "allowedAmmo") return row;
    let links = [...(row.links || [])];
    if (fallback && !links.some((link) => link.id === defaultId)) {
      links = [fallback, ...links];
    }
    const marked = links.map((link) =>
      link.id === defaultId ? { ...link, badge: "默认" } : link,
    );
    if (!marked.some((link) => link.badge)) return row;
    return {
      ...row,
      links: [
        ...marked.filter((link) => link.badge),
        ...marked.filter((link) => !link.badge),
      ],
      note: DEFAULT_AMMO_HINT,
      large: true,
    };
  });
}

function itemRefLink(
  value: unknown,
  fallbackTypes?: string[],
): FormattedPropLink | null {
  const row = asRecord(value);
  if (!row) return null;
  const id = String(row.id || "").trim();
  if (!id) return null;
  const label =
    displayName(String(row.name || "")) ||
    displayName(String(row.shortName || ""));
  if (!label) return null;
  const types = Array.isArray(row.types)
    ? row.types.map(String)
    : fallbackTypes || [];
  const icon = String(
    row.iconLink || row.baseImageLink || row.icon_link || "",
  ).trim();
  return {
    label,
    href: itemHrefFromTypes(id, types),
    id,
    types,
    ...(icon ? { icon } : {}),
  };
}

function extractPropLinks(key: string, value: unknown): FormattedPropLink[] {
  if (key === "defaultPreset") {
    const link = itemRefLink(value, ["preset", "gun"]);
    return link ? [link] : [];
  }
  if (key === "baseItem") {
    const link = itemRefLink(value, ["gun"]);
    return link ? [link] : [];
  }
  if (key === "allowedAmmo" && Array.isArray(value)) {
    return value
      .map((entry) => itemRefLink(entry, ["ammo"]))
      .filter((link): link is FormattedPropLink => Boolean(link));
  }
  if (key === "presets" && Array.isArray(value)) {
    return value
      .map((entry) => itemRefLink(entry, ["preset", "gun"]))
      .filter((link): link is FormattedPropLink => Boolean(link));
  }
  if (key === "conflictingItems" && Array.isArray(value)) {
    return value
      .map((entry) => itemRefLink(entry))
      .filter((link): link is FormattedPropLink => Boolean(link));
  }
  if (key === "conflictingCategories" && Array.isArray(value)) {
    const links: FormattedPropLink[] = [];
    for (const entry of value) {
      const row = asRecord(entry);
      if (!row) continue;
      const id = String(row.id || "");
      if (isGenericItemCategoryId(id)) continue;
      const href = handbookHrefFromCategoryId(id);
      const label = displayName(String(row.name || ""));
      if (!href || !label) continue;
      links.push({ label, href });
    }
    return links;
  }
  if (key === "usedOnMaps" && Array.isArray(value)) {
    const links: FormattedPropLink[] = [];
    for (const entry of value) {
      const row = asRecord(entry);
      if (!row) continue;
      const label = String(row.name || "").trim();
      if (!label) continue;
      const slug = String(row.normalizedName || row.id || "").trim();
      links.push({
        label,
        href: slug
          ? `/guides/tarkov/maps/${encodeURIComponent(slug)}`
          : "/guides/tarkov/maps",
      });
    }
    return links;
  }
  if (key === "categories" && Array.isArray(value)) {
    const links: FormattedPropLink[] = [];
    for (const entry of value) {
      const row = asRecord(entry);
      if (!row) continue;
      const id = String(row.id || "");
      if (isGenericItemCategoryId(id)) continue;
      const href = handbookHrefFromCategoryId(id);
      const label = displayName(String(row.name || ""));
      if (!href || !label) continue;
      links.push({ label, href });
    }
    return links;
  }
  return [];
}

export type VendorOffer = {
  vendor: string;
  vendorName: string;
  price: number | null;
  currency: string;
  priceRub: number | null;
  minLevel: number | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function parseVendorOffers(value: unknown): VendorOffer[] {
  if (!Array.isArray(value)) return [];
  const out: VendorOffer[] = [];
  for (const row of value) {
    const offer = asRecord(row);
    if (!offer) continue;
    const vendor = asRecord(offer.vendor) || {};
    const vendorKey = String(
      vendor.normalizedName || vendor.name || "",
    ).trim();
    const price = Number(offer.price);
    const priceRub = Number(offer.priceRUB ?? offer.price);
    out.push({
      vendor: vendorKey,
      vendorName: String(vendor.name || vendorKey || "—"),
      price: Number.isFinite(price) ? price : null,
      currency: String(offer.currency || "RUB"),
      priceRub: Number.isFinite(priceRub) ? priceRub : null,
      minLevel:
        Number.isFinite(Number(vendor.minTraderLevel))
          ? Number(vendor.minTraderLevel)
          : loyaltyLevel(offer),
    });
  }
  return out;
}

function loyaltyLevel(offer: Record<string, unknown>): number | null {
  const reqs = offer.requirements;
  if (!Array.isArray(reqs)) return null;
  for (const row of reqs) {
    const req = asRecord(row);
    if (!req) continue;
    if (String(req.type || "") !== "loyaltyLevel") continue;
    const n = Number(req.value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export function formatOfferPrice(offer: VendorOffer): string {
  if (offer.currency && offer.currency !== "RUB" && offer.price != null) {
    const symbol =
      offer.currency === "USD" ? "$" : offer.currency === "EUR" ? "€" : "";
    return `${symbol}${offer.price.toLocaleString("zh-CN")}`;
  }
  return formatMoney(offer.priceRub ?? offer.price);
}

export type LinkedItemRef = {
  id: string;
  name: string;
  icon: string;
  types: string[];
};

function linkedItem(value: unknown): LinkedItemRef | null {
  const row = asRecord(value);
  if (!row) return null;
  const id = String(row.id || "").trim();
  if (!id) return null;
  const name =
    displayName(String(row.name || "")) ||
    displayName(String(row.shortName || ""));
  if (!name) return null;
  const types = Array.isArray(row.types) ? row.types.map(String) : [];
  return {
    id,
    name,
    icon: String(row.iconLink || row.baseImageLink || ""),
    types,
  };
}

export type GridPocket = {
  width: number;
  height: number;
  col: number;
  row: number;
};

export function extractGridPockets(
  properties: Record<string, unknown> | undefined,
): GridPocket[] {
  const grids = properties?.grids;
  if (!Array.isArray(grids)) return [];
  const pockets: GridPocket[] = [];
  grids.forEach((grid, index) => {
    const row = asRecord(grid);
    if (!row) return;
    const width = Number(row.width);
    const height = Number(row.height);
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      return;
    }
    const col = Number(row.col);
    const pocketRow = Number(row.row);
    pockets.push({
      width,
      height,
      col: Number.isFinite(col) ? col : index,
      row: Number.isFinite(pocketRow) ? pocketRow : 0,
    });
  });
  return pockets;
}

export type PlateSlotGroup = {
  key: string;
  name: string;
  plates: LinkedItemRef[];
};

export function extractPlateSlots(
  properties: Record<string, unknown> | undefined,
): PlateSlotGroup[] {
  const slots = properties?.armorSlots;
  if (!Array.isArray(slots)) return [];
  const groups: PlateSlotGroup[] = [];
  slots.forEach((slot, index) => {
    const row = asRecord(slot);
    if (!row || !Array.isArray(row.allowedPlates)) return;
    const plates = row.allowedPlates
      .map(linkedItem)
      .filter((item): item is LinkedItemRef => Boolean(item));
    if (!plates.length) return;
    const zones = Array.isArray(row.zones)
      ? row.zones.map(String).filter(Boolean).join(" · ")
      : "";
    groups.push({
      key: `${index}-${String(row.name || zones || "plate")}`,
      name: String(row.name || zones || "插板槽"),
      plates,
    });
  });
  return groups;
}

export function extractContentLines(
  properties: Record<string, unknown> | undefined,
): string[] {
  const raw = properties?.content;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((line) => String(line || "").trim())
    .filter(
      (line) =>
        Boolean(line) &&
        !isBareTarkovId(line) &&
        !line.includes("_Note_Page"),
    );
}

export function itemHasFlea(item: Record<string, unknown> | undefined): boolean {
  const types = item?.types;
  if (!Array.isArray(types)) return true;
  return !types.map(String).includes("noFlea");
}
