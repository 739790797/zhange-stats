import {
  EnvironmentOutlined,
  EyeOutlined,
  HeartOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import { Alert, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovBossDetail,
  type TarkovBossLoot,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { traderPortraitUrl } from "@/lib/tarkovHomeNav";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import tableStyles from "./TarkovDarkTable.module.css";
import catalogStyles from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovBossPanel.module.css";

type Props = {
  slug: string;
};

function formatChance(chance: number | undefined): string {
  if (chance == null || !Number.isFinite(chance)) return "—";
  return `${Math.round(chance * 100)}%`;
}

export function TarkovBossPanel({ slug }: Props) {
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-boss", slug],
    queryFn: () => fetchTarkovBossDetail(slug),
    staleTime: 60_000,
    retry: 1,
    enabled: Boolean(slug),
  });
  useTarkovDocumentTitle(detailQuery.data?.name || "");

  if (detailQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (detailQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="BOSS 页加载失败"
        description={apiError(detailQuery.error, "BOSS 页加载失败")}
      />
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  const lootColumns: ColumnsType<TarkovBossLoot> = [
    {
      title: "名称",
      key: "name",
      render: (_: unknown, row) => (
        <span className={styles.itemCell}>
          {row.icon_link ? (
            <img src={row.icon_link} alt="" width={36} height={36} />
          ) : (
            <span style={{ width: 36, height: 36 }} />
          )}
          <Link
            className={catalogStyles.nameLink}
            to={itemHrefFromTypes(row.item_id, row.types)}
          >
            {row.name}
          </Link>
        </span>
      ),
    },
    {
      title: "出售给跳蚤市场",
      key: "flea",
      width: 180,
      align: "right",
      render: (_: unknown, row) => (
        <span className={styles.money}>{formatMoney(row.flea_price)}</span>
      ),
    },
    {
      title: "出售给商人",
      key: "trader",
      width: 220,
      render: (_: unknown, row) =>
        row.trader_slug ? (
          <span className={styles.traderCell}>
            <img
              className={styles.traderAvatar}
              src={traderPortraitUrl(row.trader_slug)}
              alt=""
              width={22}
              height={22}
            />
            <span className={styles.money}>
              {formatMoney(row.trader_price, row.trader_currency)}
            </span>
          </span>
        ) : (
          "—"
        ),
    },
  ];

  const spawnColumns = [
    { title: "地图", dataIndex: "map", key: "map" },
    { title: "刷新点", dataIndex: "name", key: "name" },
    {
      title: "概率",
      key: "chance",
      render: (_: unknown, row: { chance?: number }) => formatChance(row.chance),
    },
  ];

  const escortColumns = [
    { title: "地图", dataIndex: "map", key: "map" },
    {
      title: "名称",
      key: "name",
      render: (_: unknown, row: { name?: string; nickname?: string }) =>
        row.nickname ? `${row.name}（${row.nickname}）` : row.name,
    },
    { title: "数量", dataIndex: "count", key: "count" },
    {
      title: "概率",
      key: "chance",
      render: (_: unknown, row: { chance?: number }) => formatChance(row.chance),
    },
  ];

  return (
    <div className={styles.stack}>
      <section className={styles.hero}>
        <div>
          <div className={styles.headRow}>
            <span className={styles.badge}>BOSS</span>
            <h2 className={styles.name}>{detail.name}</h2>
            {detail.nickname ? (
              <span className={styles.nickname}>{detail.nickname}</span>
            ) : null}
            {detail.wiki_link ? (
              <a
                className={styles.wiki}
                href={detail.wiki_link}
                target="_blank"
                rel="noreferrer"
              >
                Wiki
              </a>
            ) : null}
          </div>
          {detail.bio ? <p className={styles.bio}>{detail.bio}</p> : null}
          {detail.description ? (
            <>
              <span className={styles.sectionLabel}>行为</span>
              <p className={styles.desc}>{detail.description}</p>
            </>
          ) : null}
          <div className={styles.stats}>
            <div>
              <div className={styles.statLabel}>
                <EyeOutlined className={styles.statIcon} />
                行为
              </div>
              <div className={styles.statValue}>{detail.behavior_zh || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <EnvironmentOutlined className={styles.statIcon} />
                地图
              </div>
              <div className={styles.statValue}>{detail.maps_label || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <LineChartOutlined className={styles.statIcon} />
                刷新概率
              </div>
              <div className={styles.statValue}>{detail.spawn_label || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <HeartOutlined className={styles.statIcon} />
                生命值
              </div>
              <div className={styles.statValue}>
                <div className={styles.healthTotal}>
                  {detail.health_total || "—"}
                </div>
                {detail.health?.length ? (
                  <div className={styles.healthParts}>
                    {detail.health
                      .map((part) => `${part.name} ${part.max}`)
                      .join(" · ")}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
        <div className={styles.posterWrap}>
          {detail.poster_link || detail.portrait_link ? (
            <img
              className={styles.poster}
              src={detail.poster_link || detail.portrait_link}
              alt=""
            />
          ) : null}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.lootHead}>
          <span className={styles.diamond} aria-hidden>
            ◆
          </span>
          BOSS 特殊战利品
        </div>
        <Table
          className={tableStyles.table}
          rowKey={(row) => row.item_id}
          columns={lootColumns}
          dataSource={detail.unique_loot ?? []}
          pagination={false}
          locale={{ emptyText: "暂无高价值特殊战利品" }}
        />
      </section>

      {detail.spawn_locations?.length ? (
        <section className={styles.section}>
          <div className={styles.lootHead}>刷新点</div>
          <Table
            className={tableStyles.table}
            rowKey={(row, index) =>
              `${row.map_slug}-${row.name}-${index ?? 0}`
            }
            columns={spawnColumns}
            dataSource={detail.spawn_locations}
            pagination={false}
            size="small"
          />
        </section>
      ) : null}

      {detail.escorts?.length ? (
        <section className={styles.section}>
          <div className={styles.lootHead}>保镖</div>
          <Table
            className={tableStyles.table}
            rowKey={(row, index) =>
              `${row.map_slug}-${row.slug}-${row.count}-${index ?? 0}`
            }
            columns={escortColumns}
            dataSource={detail.escorts}
            pagination={false}
            size="small"
          />
        </section>
      ) : null}
    </div>
  );
}
