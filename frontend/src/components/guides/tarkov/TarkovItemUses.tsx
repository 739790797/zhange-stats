import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import type { TarkovBarter, TarkovCraft, TarkovItemDetail } from "@/api/guidesApi";
import {
  TARKOV_HIDEOUT_PATH,
  tarkovHideoutHref,
  tarkovTaskHref,
  tarkovTraderHref,
  traderDisplayName,
  traderIconUrl,
} from "@/lib/tarkovHomeNav";
import {
  formatDurationSeconds,
  type VendorOffer,
} from "@/lib/tarkovItemFormat";
import {
  hasFleaQuote,
  itemHasUses,
  questKindChip,
  requiredItemCount,
  type ItemFleaQuote,
} from "@/lib/tarkovItemSources";
import { TarkovGuideItemCell } from "@/components/guides/tarkov/TarkovGuideItemCell";
import {
  TarkovItemBlock,
  TarkovItemFleaQuote,
  TarkovItemOfferRow,
} from "@/components/guides/tarkov/TarkovItemOfferCards";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovItemSources.module.css";

type HideoutUse = NonNullable<
  NonNullable<TarkovItemDetail["uses"]>["hideout"]
>[number];
type TaskUse = NonNullable<
  NonNullable<TarkovItemDetail["uses"]>["tasks"]
>[number];

type Props = {
  detail: TarkovItemDetail;
  flea?: ItemFleaQuote | null;
  traderSells?: VendorOffer[];
  bestSell?: VendorOffer | null;
};

export function TarkovItemUses({
  detail,
  flea,
  traderSells = [],
  bestSell = null,
}: Props) {
  const uses = detail.uses;
  const itemId = detail.id;
  const barters = uses?.barters || [];
  const crafts = uses?.crafts || [];
  const hideout = uses?.hideout || [];
  const tasks = uses?.tasks || [];
  const showFlea = hasFleaQuote(flea);
  if (
    !showFlea &&
    !traderSells.length &&
    !itemHasUses(uses)
  ) {
    return null;
  }

  const barterColumns: ColumnsType<TarkovBarter> = [
    {
      title: "商人",
      key: "trader",
      width: 180,
      render: (_: unknown, row) => {
        const slug = row.trader_slug || "";
        const label = traderDisplayName(slug, row.trader_name || slug);
        const inner = (
          <>
            {slug ? (
              <img className={styles.traderIcon} src={traderIconUrl(slug)} alt="" />
            ) : null}
            <span>
              {label}
              {row.min_trader_level ? (
                <span className={styles.level}> LL{row.min_trader_level}</span>
              ) : null}
            </span>
          </>
        );
        return slug ? (
          <Link className={styles.traderCell} to={tarkovTraderHref(slug)}>
            {inner}
          </Link>
        ) : (
          <span className={styles.traderCell}>{inner}</span>
        );
      },
    },
    {
      title: "得到",
      key: "offered",
      render: (_: unknown, row) =>
        row.offered_item ? (
          <TarkovGuideItemCell item={row.offered_item} showCount />
        ) : (
          "—"
        ),
    },
    {
      title: "用量",
      key: "count",
      width: 80,
      render: (_: unknown, row) => {
        const count = requiredItemCount(row.required_items, itemId);
        return count > 0 ? `×${count}` : "—";
      },
    },
  ];

  const craftColumns: ColumnsType<TarkovCraft> = [
    {
      title: "模块",
      key: "station",
      width: 180,
      render: (_: unknown, row) => (
        <span>
          {row.station_slug ? (
            <Link to={tarkovHideoutHref(row.station_slug)}>{row.station_name}</Link>
          ) : (
            row.station_name
          )}
          {row.level ? <span className={styles.level}> Lv.{row.level}</span> : null}
        </span>
      ),
    },
    {
      title: "产物",
      key: "product",
      render: (_: unknown, row) =>
        row.product_item ? (
          <TarkovGuideItemCell item={row.product_item} showCount />
        ) : (
          "—"
        ),
    },
    {
      title: "用量",
      key: "count",
      width: 80,
      render: (_: unknown, row) => {
        const count = requiredItemCount(row.required_items, itemId);
        return count > 0 ? `×${count}` : "—";
      },
    },
    {
      title: "时长",
      key: "duration",
      width: 120,
      render: (_: unknown, row) => formatDurationSeconds(row.duration),
    },
  ];

  return (
    <section className={styles.wrap}>
      <h2 className={styles.title}>用途</h2>

      {showFlea ? (
        <TarkovItemBlock
          title="跳蚤市场"
          extra={<span className={styles.blockTag}>卖出</span>}
        >
          <TarkovItemFleaQuote flea={flea} />
        </TarkovItemBlock>
      ) : null}

      {traderSells.length ? (
        <TarkovItemBlock title="出售给商人" count={traderSells.length}>
          <TarkovItemOfferRow offers={traderSells} best={bestSell} />
        </TarkovItemBlock>
      ) : null}

      {barters.length ? (
        <TarkovItemBlock title="以物易物" count={barters.length}>
          <Table<TarkovBarter>
            className={`${tableStyles.table} ${styles.blockTable}`}
            size="small"
            rowKey={(row) => row.id || `${row.trader_slug}-${row.min_trader_level}`}
            columns={barterColumns}
            dataSource={barters}
            pagination={false}
          />
        </TarkovItemBlock>
      ) : null}

      {crafts.length || hideout.length ? (
        <TarkovItemBlock
          title="藏身处制作"
          count={crafts.length + hideout.length}
          extra={
            hideout.length && !crafts.length ? (
              <Link className={styles.more} to={TARKOV_HIDEOUT_PATH}>
                藏身处
              </Link>
            ) : undefined
          }
        >
          {crafts.length ? (
            <Table<TarkovCraft>
              className={`${tableStyles.table} ${styles.blockTable}`}
              size="small"
              rowKey={(row) => row.id || `${row.station_slug}-${row.level}`}
              columns={craftColumns}
              dataSource={crafts}
              pagination={false}
            />
          ) : null}
          {hideout.length ? (
            <div className={styles.quests}>
              {hideout.map((row: HideoutUse) => {
                const count = Number(row.count || 1);
                const label = `${row.station_name || row.station_slug} Lv.${row.level}`;
                const inner = (
                  <>
                    <span className={`${styles.questKind} ${styles.kindBuild}`}>
                      {questKindChip("build")}
                    </span>
                    <span className={styles.questName}>{label}</span>
                    {count > 1 ? (
                      <span className={styles.questMeta}>
                        <span className={styles.questCount}>×{count}</span>
                      </span>
                    ) : (
                      <span />
                    )}
                  </>
                );
                return row.station_slug ? (
                  <Link
                    key={`${row.station_slug}-${row.level}`}
                    className={styles.quest}
                    to={tarkovHideoutHref(row.station_slug)}
                  >
                    {inner}
                  </Link>
                ) : (
                  <span
                    key={`${row.station_id}-${row.level}`}
                    className={styles.quest}
                  >
                    {inner}
                  </span>
                );
              })}
            </div>
          ) : null}
        </TarkovItemBlock>
      ) : null}

      {tasks.length ? (
        <TarkovItemBlock title="任务需求" count={tasks.length}>
          <div className={styles.quests}>
            {tasks.map((row: TaskUse) => {
              const slug = row.trader_slug || "";
              const trader = traderDisplayName(slug, row.trader_name || "");
              const count = Number(row.count || 0);
              const notes = (row.notes || []).filter(Boolean);
              return (
                <Link
                  key={row.id}
                  className={styles.quest}
                  to={tarkovTaskHref(row.id)}
                >
                  <span className={`${styles.questKind} ${styles.kindNeed}`}>
                    {questKindChip("require")}
                  </span>
                  <span className={styles.questName}>{row.name || row.id}</span>
                  <span className={styles.questMeta}>
                    {slug ? (
                      <img
                        className={styles.questTrader}
                        src={traderIconUrl(slug)}
                        alt=""
                      />
                    ) : null}
                    <span>{trader}</span>
                    {count > 1 ? (
                      <span className={styles.questCount}>×{count}</span>
                    ) : null}
                  </span>
                  {notes.length ? (
                    <span className={styles.questNote}>{notes.join(" · ")}</span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </TarkovItemBlock>
      ) : null}
    </section>
  );
}
