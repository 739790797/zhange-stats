import { useMemo } from "react";
import { Alert, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovBosses,
  type TarkovBossListItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  groupBossesByKind,
  TARKOV_BOSS_KIND_LABELS,
  TARKOV_BOSS_KINDS,
} from "@/lib/tarkovBossKinds";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovBossHref, tarkovMapMarkByName } from "@/lib/tarkovHomeNav";
import tableStyles from "./TarkovDarkTable.module.css";
import catalogStyles from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovBossPanel.module.css";

function dash(value: string | undefined): string {
  const text = (value || "").trim();
  return text || "—";
}

function mapsWithChance(row: TarkovBossListItem): { map: string; chance: string }[] {
  const label = (row.spawn_label || "").trim();
  if (label) {
    const parsed = label.split("，").flatMap((part) => {
      const match = part.trim().match(/^(\d+(?:–\d+)?%)[（(](.+)[）)]$/);
      return match ? [{ chance: match[1], map: match[2] }] : [];
    });
    if (parsed.length) return parsed;
  }
  return (row.maps_label || "")
    .split("、")
    .map((name) => name.trim())
    .filter(Boolean)
    .map((map) => ({ map, chance: "" }));
}

const columns: ColumnsType<TarkovBossListItem> = [
  {
    title: "名称",
    key: "name",
    width: 240,
    fixed: "left",
    render: (_: unknown, row) => (
      <span className={styles.itemCell}>
        {row.portrait_link ? (
          <img
            className={styles.listAvatar}
            src={row.portrait_link}
            alt=""
            width={40}
            height={40}
          />
        ) : (
          <span className={styles.listAvatar} />
        )}
        <Link className={catalogStyles.nameLink} to={tarkovBossHref(row.slug)}>
          {row.name || row.slug}
        </Link>
      </span>
    ),
  },
  {
    title: "昵称",
    dataIndex: "nickname",
    key: "nickname",
    width: 120,
    render: (value: string) => dash(value),
  },
  {
    title: "地图（加概率）",
    key: "maps",
    render: (_: unknown, row) => {
      const items = mapsWithChance(row);
      if (!items.length) return "—";
      return (
        <span className={styles.mapsCell}>
          {items.map((item) => {
            const mark = tarkovMapMarkByName(item.map);
            const label = mark?.label || item.map;
            return (
              <span
                key={`${item.map}-${item.chance}`}
                className={styles.mapChip}
              >
                {mark?.icon ? (
                  <svg
                    className={styles.mapIcon}
                    viewBox="0 0 24 24"
                    width={16}
                    height={16}
                    aria-hidden
                  >
                    <path d={mark.icon} fill="currentColor" />
                  </svg>
                ) : null}
                <span>{label}</span>
                {item.chance ? (
                  <span className={styles.mapChance}>（{item.chance}）</span>
                ) : null}
              </span>
            );
          })}
        </span>
      );
    },
  },
  {
    title: "行为模式",
    key: "behavior",
    width: 200,
    render: (_: unknown, row) => dash(row.behavior_zh || row.behavior),
  },
];

export function TarkovBossesHubPanel() {
  const gameMode = useTarkovGameMode();
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-bosses", gameMode],
    queryFn: fetchTarkovBosses,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const rows = catalogQuery.data?.items ?? [];
  const groups = useMemo(() => groupBossesByKind(rows), [rows]);

  if (catalogQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="BOSS 列表加载失败"
        description={apiError(catalogQuery.error, "BOSS 列表加载失败")}
      />
    );
  }

  const sections = TARKOV_BOSS_KINDS.filter((kind) => groups[kind].length);

  return (
    <div className={catalogStyles.stack}>
      {sections.length ? (
        sections.map((kind) => (
          <section key={kind} className={catalogStyles.panel}>
            <div className={styles.listSection}>
              <h2 className={styles.listSectionHead}>
                {TARKOV_BOSS_KIND_LABELS[kind]}
                <span className={styles.listSectionCount}>
                  {groups[kind].length}
                </span>
              </h2>
              <Table<TarkovBossListItem>
                className={tableStyles.table}
                size="small"
                rowKey={(row) => row.id || row.slug}
                columns={columns}
                dataSource={groups[kind]}
                pagination={false}
                scroll={{ x: 720 }}
                locale={{ emptyText: "暂无数据" }}
              />
            </div>
          </section>
        ))
      ) : (
        <div className={catalogStyles.panel}>暂无 BOSS 数据</div>
      )}
    </div>
  );
}
