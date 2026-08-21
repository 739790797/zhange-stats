import { Card, Table, Tag, Typography } from "antd";
import type { components } from "@/api/generated/schema";
import styles from "./MinecraftLivePanel.module.css";

type Entities = components["schemas"]["MinecraftEntitiesOut"];
type EntityType = components["schemas"]["MinecraftEntityTypeOut"];
type EntityCategory = components["schemas"]["MinecraftEntityCategoryOut"];

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

const CATEGORY_COLOR: Record<string, string> = {
  player: "blue",
  drop: "gold",
  hostile: "red",
  passive: "green",
  projectile: "purple",
  vehicle: "cyan",
  display: "default",
  mod: "geekblue",
  other: "default",
};

const WORLD_LABEL: Record<string, string> = {
  "minecraft:overworld": "主世界",
  "minecraft:the_nether": "下界",
  "minecraft:the_end": "末地",
};

function categoryLabel(key: string) {
  return CATEGORY_LABEL[key] || key;
}

function worldLabel(id: string) {
  return WORLD_LABEL[id] || id.replace("minecraft:", "");
}

function formatCount(n: number) {
  return n.toLocaleString("zh-CN");
}

export function MinecraftEntitiesCard({
  entities,
}: {
  entities?: Entities | null;
}) {
  const categories = entities?.categories || [];
  const types = entities?.types || [];
  const worlds = entities?.worlds || [];
  const total = entities?.total || 0;
  const hasData = Boolean(entities?.ok && total > 0);

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
          <div className={styles.entitySummary}>
            <div className={styles.entityTotal}>
              <span className={styles.entityTotalNum}>{formatCount(total)}</span>
              <span className={styles.entityTotalLabel}>已加载</span>
            </div>
            <div className={styles.entityCats}>
              {categories.map((row: EntityCategory) => (
                <Tag
                  key={row.key}
                  color={CATEGORY_COLOR[row.key] || "default"}
                  style={{ marginInlineEnd: 8, marginBottom: 8 }}
                >
                  {categoryLabel(row.key)} {formatCount(row.count)}
                </Tag>
              ))}
            </div>
          </div>
          {worlds.length > 1 ? (
            <Typography.Text type="secondary" className={styles.entityWorlds}>
              {worlds
                .map((row) => `${worldLabel(row.id)} ${formatCount(row.total)}`)
                .join(" · ")}
            </Typography.Text>
          ) : null}
          <Table<EntityType>
            size="small"
            pagination={false}
            rowKey="id"
            dataSource={types}
            columns={[
              {
                title: "类型",
                dataIndex: "id",
                ellipsis: true,
                render: (_: string, row) => (
                  <span title={row.id}>
                    {row.id.startsWith("minecraft:") ? row.name : row.id}
                  </span>
                ),
              },
              {
                title: "分类",
                dataIndex: "category",
                width: 88,
                render: (key: string) => categoryLabel(key),
              },
              {
                title: "数量",
                dataIndex: "count",
                width: 88,
                align: "right",
                render: (n: number) => formatCount(n),
              },
            ]}
          />
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
