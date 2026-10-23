/**
 * dump 护甲枚举没有 items_zh 词条（Collider Type / Armor Zone / Front_plate）。
 * 展示层按碰撞体、插板槽、材质、护甲类型做中文映射；上游 locale 已译成中文时不再覆盖。
 */

const PREFIX_RE =
  /^(collider\s*type|armor\s*zone|ebodypartcollidertype)[.\s:_-]*/i;
const CJK_RE = /[\u3400-\u9fff]/;

/** 碰撞体 / 简化部位 / 插板槽 */
const ZONE_LABELS: Record<string, string> = {
  head: "头部",
  headcommon: "头部",
  parietalhead: "头顶",
  backhead: "后脑",
  ears: "耳朵",
  eyes: "眼睛",
  jaw: "下颌",
  neckfront: "喉咙",
  neckback: "后颈",
  throat: "喉咙",
  ribcageup: "上胸",
  ribcagelow: "下胸",
  spinetop: "上背",
  spinedown: "下背",
  leftsidechestup: "左上侧胸",
  leftsidechestdown: "左下侧胸",
  rightsidechestup: "右上侧胸",
  rightsidechestdown: "右下侧胸",
  pelvis: "骨盆",
  pelvisback: "臀部",
  leftupperarm: "左上臂",
  leftforearm: "左前臂",
  rightupperarm: "右上臂",
  rightforearm: "右前臂",
  leftthigh: "左大腿",
  leftcalf: "左小腿",
  rightthigh: "右大腿",
  rightcalf: "右小腿",
  chest: "胸部",
  thorax: "胸部",
  stomach: "腹部",
  groin: "裆部",
  back: "背部",
  sides: "侧面",
  arms: "手臂",
  leftarm: "左臂",
  rightarm: "右臂",
  leftleg: "左腿",
  rightleg: "右腿",
  front_plate: "前胸",
  back_plate: "后背",
  left_side_plate: "左侧",
  right_side_plate: "右侧",
  front: "前胸",
  frontplate: "前胸",
  backplate: "后背",
  helmet_top: "盔顶",
  helmet_back: "盔后",
  helmet_eyes: "眼部",
  helmet_jaw: "下颌",
  helmet_ears: "耳部",
  shoulder_l: "左肩",
  shoulder_r: "右肩",
  collar: "衣领",
};

const PLATE_ZONE_SUFFIXES: Array<[RegExp, string]> = [
  [/_side_left_high$/i, "左侧插板（高）"],
  [/_side_right_high$/i, "右侧插板（高）"],
  [/_side_left$/i, "左侧插板"],
  [/_side_right$/i, "右侧插板"],
  [/_chest$/i, "前胸插板"],
  [/_back$/i, "后背插板"],
];

const MATERIAL_LABELS: Record<string, string> = {
  aramid: "芳纶",
  uhmwpe: "聚乙烯",
  combined: "复合材料",
  titan: "钛",
  titanium: "钛",
  aluminium: "铝",
  aluminum: "铝",
  armoredsteel: "装甲钢",
  steel: "钢",
  ceramic: "陶瓷",
  glass: "玻璃",
};

const ARMOR_TYPE_LABELS: Record<string, string> = {
  light: "轻型",
  heavy: "重型",
};

function lookup(map: Record<string, string>, raw: string): string | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const compact = trimmed.toLowerCase().replace(/[\s-]+/g, "_");
  return (
    map[trimmed] ||
    map[trimmed.toLowerCase()] ||
    map[compact] ||
    map[compact.replace(/_/g, "")]
  );
}

function stripDumpPrefix(raw: string): string {
  return raw.trim().replace(PREFIX_RE, "").trim();
}

function plateZoneLabel(token: string): string | undefined {
  for (const [pattern, label] of PLATE_ZONE_SUFFIXES) {
    if (pattern.test(token)) return label;
  }
  return undefined;
}

/** 已是上游译名（含汉字）时不要再套本地表。 */
function keepUpstreamLabel(raw: string): boolean {
  return CJK_RE.test(raw);
}

/** 单条 dump 部位 / 槽位名 → 中文；未知则去掉 Collider Type 等前缀。 */
export function formatArmorZoneLabel(raw: string): string {
  const text = String(raw || "").trim();
  if (!text) return "";
  if (keepUpstreamLabel(text)) return text;
  const token = stripDumpPrefix(text);
  const mapped =
    lookup(ZONE_LABELS, token) ||
    plateZoneLabel(token) ||
    lookup(ZONE_LABELS, text);
  if (mapped) return mapped;
  return token || text;
}

/** 防护部位 / 软甲槽：去重、保序。 */
export function formatArmorZoneList(value: unknown): string {
  const parts = Array.isArray(value) ? value : value == null ? [] : [value];
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const part of parts) {
    const label = formatArmorZoneLabel(String(part || ""));
    if (!label || seen.has(label)) continue;
    seen.add(label);
    labels.push(label);
  }
  return labels.join(" · ");
}

export function formatArmorSlotLabel(raw: string): string {
  return formatArmorZoneLabel(raw) || raw.trim() || "插板槽";
}

function materialKey(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value && typeof value === "object") {
    const row = value as { name?: unknown; id?: unknown };
    return String(row.name || row.id || "").trim();
  }
  return "";
}

export function formatArmorMaterial(value: unknown): string {
  const key = materialKey(value);
  if (!key) return "";
  if (keepUpstreamLabel(key)) return key;
  return lookup(MATERIAL_LABELS, key) || key;
}

export function formatArmorType(value: unknown): string {
  const key = typeof value === "string" ? value.trim() : "";
  if (!key) return "";
  if (keepUpstreamLabel(key)) return key;
  return lookup(ARMOR_TYPE_LABELS, key) || key;
}
