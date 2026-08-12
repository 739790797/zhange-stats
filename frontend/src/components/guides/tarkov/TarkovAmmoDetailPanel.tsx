import { Image, Descriptions, Spin, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovAmmoDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { formatCaliberLabel } from "@/lib/tarkovAmmoCategories";

type Props = {
  itemId: string;
};

const PROP_LABELS: Record<string, string> = {
  propertiesType: "属性类型",
  caliber: "口径",
  ammoType: "弹药类型",
  damage: "威力",
  penetrationPower: "穿透力",
  armorDamage: "对甲%",
  initialSpeed: "子弹初速",
  accuracyModifier: "精度修正",
  recoilModifier: "后座修正",
  lightBleedModifier: "小出血概率",
  heavyBleedModifier: "大出血概率",
  fragmentationChance: "碎弹率",
  ricochetChance: "跳弹率",
  penetrationChance: "穿透概率",
  penetrationPowerDeviation: "穿透偏差",
  projectileCount: "弹丸数",
  tracer: "曳光",
  tracerColor: "曳光颜色",
  stackMaxSize: "堆叠上限",
  staminaBurnPerDamage: "耐力消耗",
  durabilityBurnFactor: "耐久损耗",
  heatFactor: "积热",
  misfireChance: "哑火概率",
  failureToFeedChance: "卡弹概率",
  ballisticCoeficient: "弹道系数",
  bulletMassGrams: "弹头质量(g)",
  bulletDiameterMilimeters: "弹径(mm)",
};

const ITEM_LABELS: Record<string, string> = {
  id: "ID",
  name: "名称",
  shortName: "短名",
  description: "描述",
  normalizedName: "规范化名",
  weight: "重量(kg)",
  width: "宽",
  height: "高",
  backgroundColor: "背景色",
  basePrice: "基础价",
  avg24hPrice: "24h均价",
  lastLowPrice: "最近低价",
  low24hPrice: "24h最低",
  high24hPrice: "24h最高",
  changeLast48h: "48h涨跌",
  changeLast48hPercent: "48h涨跌%",
  lastOfferCount: "挂单数",
  lastScan: "上次扫描",
  updated: "更新时间",
  minLevelForFlea: "跳蚤等级",
  discardLimit: "丢弃上限",
  hasGrid: "有格仓",
  wikiLink: "Wiki",
  link: "tarkov.dev",
  iconLink: "icon",
  gridImageLink: "grid",
  baseImageLink: "base",
  inspectImageLink: "inspect",
  image512pxLink: "512",
  image8xLink: "8x",
  types: "类型",
  categories: "分类",
  handbookCategories: "手册分类",
  buyFromTrader: "商人买入",
  sellToTrader: "商人卖出",
  conflictingItems: "冲突物品",
  conflictingCategories: "冲突分类",
  conflictingSlotIds: "冲突槽位",
  containsItems: "包含物品",
  ammoType: "弹药类型",
  damage: "威力",
  penetrationPower: "穿透力",
  armorDamage: "对甲%",
  fragmentationChance: "碎弹率",
  ricochetChance: "跳弹率",
  projectileCount: "弹丸数",
  tracer: "曳光",
  tracerColor: "曳光颜色",
  stackMaxSize: "堆叠上限",
  recoil: "后座(旧)",
};

const SKIP_PROP_KEYS = new Set(["propertiesType", "ammoType"]);

const SKIP_ITEM_KEYS = new Set([
  "name",
  "shortName",
  "description",
  "iconLink",
  "gridImageLink",
  "baseImageLink",
  "inspectImageLink",
  "image512pxLink",
  "image8xLink",
]);

const CDN_SUFFIX_RE =
  /-(?:icon|grid-image|base-image|512|8x|image)\.webp(\?.*)?$/i;

/** 详情头图用 -grid-image.webp */
function toGridImageUrl(src: string | null | undefined): string {
  const url = (src || "").trim();
  if (!url) return "";
  if (CDN_SUFFIX_RE.test(url)) {
    return url.replace(CDN_SUFFIX_RE, "-grid-image.webp$1");
  }
  return url;
}

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (key === "caliber" && typeof value === "string") {
    return formatCaliberLabel(value);
  }
  if (
    typeof value === "number" &&
    (key.includes("Chance") ||
      key.includes("Modifier") ||
      key.includes("Modifier") ||
      key === "fragmentationChance" ||
      key === "ricochetChance" ||
      key === "penetrationChance" ||
      key === "accuracyModifier" ||
      key === "recoilModifier" ||
      key === "lightBleedModifier" ||
      key === "heavyBleedModifier" ||
      key === "staminaBurnPerDamage" ||
      key === "misfireChance" ||
      key === "failureToFeedChance")
  ) {
    if (
      key.endsWith("Chance") ||
      key.endsWith("Modifier") ||
      key === "staminaBurnPerDamage"
    ) {
      const pct = Math.round(Number(value) * 1000) / 10;
      const text = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
      return key.includes("Modifier") && !key.includes("Bleed")
        ? pct > 0
          ? `+${text}%`
          : `${text}%`
        : `${text}%`;
    }
  }
  if (Array.isArray(value)) {
    if (!value.length) return "—";
    if (value.every((x) => typeof x !== "object")) {
      return value.map(String).join(", ");
    }
    return JSON.stringify(value, null, 2);
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function entriesOf(
  obj: Record<string, unknown> | undefined,
  labels: Record<string, string>,
  skip?: Set<string>,
): Array<{ key: string; label: string; value: string }> {
  if (!obj) return [];
  const preferred = Object.keys(labels).filter((k) => k in obj && !skip?.has(k));
  const rest = Object.keys(obj)
    .filter((k) => !labels[k] && !skip?.has(k))
    .sort();
  return [...preferred, ...rest].map((key) => ({
    key,
    label: labels[key] || key,
    value: formatValue(key, obj[key]),
  }));
}

/** 弹药详情正文（页面用，非弹窗） */
export function TarkovAmmoDetailPanel({ itemId }: Props) {
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-ammo-detail", itemId],
    queryFn: () => fetchTarkovAmmoDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const detail = detailQuery.data;
  const image =
    toGridImageUrl(detail?.item?.gridImageLink as string | undefined) ||
    toGridImageUrl(detail?.item?.iconLink as string | undefined) ||
    toGridImageUrl(detail?.item?.baseImageLink as string | undefined);

  const propRows = entriesOf(
    detail?.properties as Record<string, unknown> | undefined,
    PROP_LABELS,
    SKIP_PROP_KEYS,
  );
  const itemRows = entriesOf(
    detail?.item as Record<string, unknown> | undefined,
    ITEM_LABELS,
    SKIP_ITEM_KEYS,
  );

  if (detailQuery.isLoading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="加载详情…" />
      </div>
    );
  }

  if (detailQuery.isError) {
    return (
      <Typography.Text type="danger">
        {apiError(detailQuery.error, "弹药详情加载失败")}
      </Typography.Text>
    );
  }

  if (!detail) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {image ? (
          <Image
            src={image}
            alt=""
            width={96}
            height={96}
            style={{ objectFit: "contain", flex: "0 0 96px" }}
          />
        ) : null}
        <div style={{ minWidth: 0, flex: 1 }}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            {detail.name}
          </Typography.Title>
          {detail.short_name ? (
            <Typography.Text type="secondary">{detail.short_name}</Typography.Text>
          ) : null}
          {detail.description ? (
            <Typography.Paragraph
              type="secondary"
              style={{ marginTop: 8, marginBottom: 0 }}
            >
              {detail.description}
            </Typography.Paragraph>
          ) : null}
        </div>
      </div>

      {propRows.length ? (
        <div>
          <Typography.Text strong>弹道属性</Typography.Text>
          <Descriptions
            size="small"
            bordered
            column={2}
            style={{ marginTop: 8 }}
            items={propRows.map((row) => ({
              key: row.key,
              label: row.label,
              children: (
                <span style={{ whiteSpace: "pre-wrap" }}>{row.value}</span>
              ),
            }))}
          />
        </div>
      ) : null}

      {itemRows.length ? (
        <div>
          <Typography.Text strong>物品字段</Typography.Text>
          <Descriptions
            size="small"
            bordered
            column={1}
            style={{ marginTop: 8 }}
            items={itemRows.map((row) => ({
              key: row.key,
              label: row.label,
              children: (
                <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                  {row.value}
                </span>
              ),
            }))}
          />
        </div>
      ) : null}
    </div>
  );
}

export function useTarkovAmmoDetailTitle(itemId: string): string {
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-ammo-detail", itemId],
    queryFn: () => fetchTarkovAmmoDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  return detailQuery.data?.name || detailQuery.data?.short_name || "弹药详情";
}
