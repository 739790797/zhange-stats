import { Pie } from "@ant-design/plots";
import { Card, Col, Row, Typography } from "antd";
import { useMemo, useState } from "react";
import type { components } from "@/api/generated/schema";
import { entityIconUrl } from "./minecraftEntityIcons";
import { entityTypeLabel } from "./minecraftEntityNames";
import styles from "./MinecraftLivePanel.module.css";

type Entities = components["schemas"]["MinecraftEntitiesOut"];
type EntityType = components["schemas"]["MinecraftEntityTypeOut"];
type EntityCategory = components["schemas"]["MinecraftEntityCategoryOut"];

type TypeChild = {
  id: string;
  label: string;
  count: number;
  iconUrl: string | null;
};

const CATEGORY_LABEL: Record<string, string> = {
  player: "玩家",
  drop: "掉落物",
  hostile: "敌对",
  passive: "友好",
  projectile: "弹射物",
  vehicle: "载具",
  display: "装饰",
  mod: "模组",
  other: "其它",
};

const CATEGORY_HEX: Record<string, string> = {
  player: "#1677ff",
  drop: "#faad14",
  hostile: "#f5222d",
  passive: "#52c41a",
  projectile: "#722ed1",
  vehicle: "#13c2c2",
  display: "#2f54eb",
  mod: "#597ef7",
  other: "#8c8c8c",
};

const WORLD_LABEL: Record<string, string> = {
  "minecraft:overworld": "主世界",
  "minecraft:the_nether": "下界",
  "minecraft:the_end": "末地",
};

const TOOLTIP_CHILD_CAP = 12;
const EMPTY_TYPES: EntityType[] = [];
const EMPTY_CATEGORIES: EntityCategory[] = [];

function categoryLabel(key: string) {
  return CATEGORY_LABEL[key] || key;
}

function categoryColor(key: string) {
  return CATEGORY_HEX[key] || CATEGORY_HEX.other;
}

function worldLabel(id: string) {
  return WORLD_LABEL[id] || id.replace("minecraft:", "");
}

function formatCount(n: number) {
  return n.toLocaleString("zh-CN");
}

function typeLabel(row: EntityType) {
  return entityTypeLabel(row.id, row.name);
}

function EntityIcon({
  url,
  label,
  size = 20,
}: {
  url: string | null;
  label: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) {
    return (
      <span
        className={styles.entityIconFallback}
        style={{ width: size, height: size }}
        title={label}
        aria-hidden
      />
    );
  }
  return (
    <img
      className={styles.entityIcon}
      src={url}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={() => setFailed(true)}
    />
  );
}

function CategoryTooltip({
  category,
  count,
  color,
  items,
}: {
  category: string;
  count: number;
  color: string;
  items: TypeChild[];
}) {
  const shown = items.slice(0, TOOLTIP_CHILD_CAP);
  const rest = items.length - shown.length;
  return (
    <div style={{ minWidth: 168, maxWidth: 240 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 6,
          fontWeight: 600,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: color,
            flexShrink: 0,
          }}
        />
        <span>
          {category} · {formatCount(count)}
        </span>
      </div>
      {shown.length ? (
        shown.map((row) => (
          <div
            key={row.id}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              lineHeight: 1.7,
              fontSize: 12,
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                minWidth: 0,
              }}
            >
              <EntityIcon url={row.iconUrl} label={row.label} size={16} />
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {row.label}
              </span>
            </span>
            <span style={{ fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
              {formatCount(row.count)}
            </span>
          </div>
        ))
      ) : (
        <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>
          暂无子类型明细
        </div>
      )}
      {rest > 0 ? (
        <div style={{ marginTop: 4, fontSize: 12, color: "rgba(0,0,0,0.45)" }}>
          及其他 {rest} 种
        </div>
      ) : null}
    </div>
  );
}

export function MinecraftEntitiesCard({
  entities,
}: {
  entities?: Entities | null;
}) {
  const categories = entities?.categories || EMPTY_CATEGORIES;
  const types = entities?.types || EMPTY_TYPES;
  const worlds = entities?.worlds || [];
  const total = entities?.total || 0;
  const hasData = Boolean(entities?.ok && total > 0);

  const typesByCategory = useMemo(() => {
    const map = new Map<string, TypeChild[]>();
    for (const row of types) {
      const key = row.category || "other";
      const list = map.get(key) || [];
      list.push({
        id: row.id,
        label: typeLabel(row),
        count: row.count,
        iconUrl: entityIconUrl(row.id),
      });
      map.set(key, list);
    }
    for (const list of map.values()) {
      list.sort(
        (a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh-CN"),
      );
    }
    return map;
  }, [types]);

  const pieData = useMemo(
    () =>
      categories
        .filter((row: EntityCategory) => row.count > 0)
        .map((row) => ({
          key: row.key,
          category: categoryLabel(row.key),
          count: row.count,
          color: categoryColor(row.key),
          children: typesByCategory.get(row.key) || [],
        })),
    [categories, typesByCategory],
  );

  const typeRows = useMemo(() => {
    const max = Math.max(1, ...types.map((row) => row.count));
    return [...types]
      .sort((a, b) => b.count - a.count)
      .map((row) => ({
        id: row.id,
        label: typeLabel(row),
        count: row.count,
        categoryKey: row.category || "other",
        category: categoryLabel(row.category),
        color: categoryColor(row.category || "other"),
        iconUrl: entityIconUrl(row.id),
        widthPct: Math.max(4, (row.count / max) * 100),
      }));
  }, [types]);

  return (
    <Card size="small" title="实体">
      {!entities?.ok && entities?.message ? (
        <Typography.Text type="secondary">{entities.message}</Typography.Text>
      ) : !hasData ? (
        <Typography.Text type="secondary">
          {entities?.message || "暂无实体数据（需要 NeoForge / Forge 的 entity list）"}
        </Typography.Text>
      ) : (
        <>
          {worlds.length > 1 ? (
            <Typography.Text type="secondary" className={styles.entityWorlds}>
              {worlds
                .map((row) => `${worldLabel(row.id)} ${formatCount(row.total)}`)
                .join(" · ")}
            </Typography.Text>
          ) : null}
          <Row gutter={[16, 16]}>
            <Col xs={24} md={10}>
              <Typography.Text type="secondary" className={styles.entityChartTitle}>
                分类占比
              </Typography.Text>
              <div className={styles.entityPieWrap}>
                <Pie
                  data={pieData}
                  angleField="count"
                  colorField="category"
                  height={260}
                  autoFit
                  innerRadius={0.62}
                  legend={false}
                  scale={{
                    color: {
                      type: "ordinal",
                      domain: pieData.map((d) => d.category),
                      range: pieData.map((d) => d.color),
                    },
                  }}
                  label={{
                    text: (d: { category: string; count: number }) =>
                      `${d.category} ${formatCount(d.count)}`,
                    position: "spider",
                    transform: [{ type: "overlapDodgeY" }],
                    style: { fontSize: 11 },
                  }}
                  tooltip={{
                    title: "category",
                    items: [{ field: "count", name: "数量" }],
                  }}
                  interaction={{
                    tooltip: {
                      render: (
                        _event: unknown,
                        {
                          title,
                          items,
                        }: {
                          title?: string;
                          items?: Array<{
                            name?: string;
                            value?: unknown;
                            color?: string;
                          }>;
                        },
                      ) => {
                        const category =
                          (typeof title === "string" && title) ||
                          String(items?.[0]?.name || "");
                        const row =
                          pieData.find((d) => d.category === category) || null;
                        const parsed = Number(
                          String(items?.[0]?.value ?? "").replace(/,/g, ""),
                        );
                        const count =
                          row?.count ??
                          (Number.isFinite(parsed) ? parsed : 0);
                        return (
                          <CategoryTooltip
                            category={category || "分类"}
                            count={count}
                            color={row?.color || items?.[0]?.color || "#8c8c8c"}
                            items={row?.children || []}
                          />
                        );
                      },
                    },
                  }}
                />
                <div className={styles.entityPieCenter} aria-hidden>
                  <span className={styles.entityPieCenterNum}>
                    {formatCount(total)}
                  </span>
                  <span className={styles.entityPieCenterLabel}>已加载</span>
                </div>
              </div>
            </Col>
            <Col xs={24} md={14}>
              <Typography.Text type="secondary" className={styles.entityChartTitle}>
                类型数量
              </Typography.Text>
              <div className={styles.entityTypeList}>
                {typeRows.map((row) => (
                  <div key={row.id} className={styles.entityTypeRow} title={row.id}>
                    <EntityIcon url={row.iconUrl} label={row.label} size={20} />
                    <span className={styles.entityTypeName}>{row.label}</span>
                    <div className={styles.entityTypeBarTrack}>
                      <div
                        className={styles.entityTypeBarFill}
                        style={{
                          width: `${row.widthPct}%`,
                          background: row.color,
                        }}
                      />
                    </div>
                    <span className={styles.entityTypeCount}>
                      {formatCount(row.count)}
                    </span>
                  </div>
                ))}
              </div>
            </Col>
          </Row>
          {(entities?.type_count || 0) > types.length ? (
            <Typography.Text type="secondary" style={{ display: "block", marginTop: 8 }}>
              仅列出前 {types.length} 种，共 {entities?.type_count} 种
            </Typography.Text>
          ) : null}
        </>
      )}
    </Card>
  );
}
