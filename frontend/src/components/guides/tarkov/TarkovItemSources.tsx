import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import type { TarkovBarter, TarkovCraft, TarkovItemDetail } from "@/api/guidesApi";
import {
  tarkovHideoutHref,
  tarkovTaskHref,
  tarkovTraderHref,
  traderDisplayName,
  traderIconUrl,
} from "@/lib/tarkovHomeNav";
import { formatDurationSeconds, type VendorOffer } from "@/lib/tarkovItemFormat";
import {
  dropSourceHref,
  dropSourcePortrait,
  dropSourceSectionLabel,
  hasFleaQuote,
  itemHasSources,
  questKindChip,
  splitItemDropSources,
  type ItemFleaQuote,
  type TarkovItemDropSource,
} from "@/lib/tarkovItemSources";
import { TarkovGuideItemStack } from "@/components/guides/tarkov/TarkovGuideItemCell";
import {
  TarkovItemBlock,
  TarkovItemFleaQuote,
  TarkovItemOfferRow,
} from "@/components/guides/tarkov/TarkovItemOfferCards";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovItemSources.module.css";

type QuestReward = NonNullable<
  NonNullable<TarkovItemDetail["sources"]>["quest_rewards"]
>[number];

type Props = {
  detail: TarkovItemDetail;
  flea?: ItemFleaQuote | null;
  traderBuys?: VendorOffer[];
};

function kindClass(kind: string | undefined): string {
  if (kind === "finish") return styles.kindFinish;
  if (kind === "start") return styles.kindStart;
  return "";
}

export function TarkovItemSources({
  detail,
  flea,
  traderBuys = [],
}: Props) {
  const sources = detail.sources;
  const barters = sources?.barters || [];
  const crafts = sources?.crafts || [];
  const quests = sources?.quest_rewards || [];
  const drops = sources?.drops || [];
  const dropGroups = splitItemDropSources(drops);
  const showFlea = hasFleaQuote(flea);
  if (
    !showFlea &&
    !traderBuys.length &&
    !itemHasSources(sources)
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
        return (
          <span>
            {slug ? (
              <Link className={styles.traderCell} to={tarkovTraderHref(slug)}>
                {inner}
              </Link>
            ) : (
              <span className={styles.traderCell}>{inner}</span>
            )}
            {row.task_unlock ? (
              <Link className={styles.unlock} to={tarkovTaskHref(row.task_unlock)}>
                任务解锁
              </Link>
            ) : null}
          </span>
        );
      },
    },
    {
      title: "给出",
      key: "required",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.required_items} />
      ),
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
      title: "材料",
      key: "required",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.required_items} />
      ),
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
      <h2 className={styles.title}>来源</h2>

      {showFlea ? (
        <TarkovItemBlock
          title="跳蚤市场"
          extra={<span className={styles.blockTag}>买入</span>}
        >
          <TarkovItemFleaQuote flea={flea} />
        </TarkovItemBlock>
      ) : null}

      {traderBuys.length ? (
        <TarkovItemBlock title="从商人购买" count={traderBuys.length}>
          <TarkovItemOfferRow offers={traderBuys} />
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

      {crafts.length ? (
        <TarkovItemBlock title="藏身处制作" count={crafts.length}>
          <Table<TarkovCraft>
            className={`${tableStyles.table} ${styles.blockTable}`}
            size="small"
            rowKey={(row) => row.id || `${row.station_slug}-${row.level}`}
            columns={craftColumns}
            dataSource={crafts}
            pagination={false}
          />
        </TarkovItemBlock>
      ) : null}

      {drops.length ? (
        <TarkovItemBlock title="掉落" count={drops.length}>
          {(["boss", "other"] as const).map((section) => {
            const rows = dropGroups[section];
            if (!rows.length) return null;
            return (
              <div key={section} className={styles.dropGroup}>
                <h4 className={styles.dropGroupTitle}>
                  {dropSourceSectionLabel(section)}
                  <span className={styles.blockCount}>{rows.length}</span>
                </h4>
                <div className={styles.dropRow}>
                  {rows.map((row: TarkovItemDropSource) => {
                    const href = dropSourceHref(row);
                    const portrait = dropSourcePortrait(row);
                    const inner = (
                      <>
                        <span className={styles.dropIcon}>
                          {portrait ? (
                            <img
                              className={styles.dropImg}
                              src={portrait}
                              alt=""
                            />
                          ) : (
                            <span className={styles.dropFallback}>
                              {(row.name || "?").slice(0, 1)}
                            </span>
                          )}
                        </span>
                        <span className={styles.dropName}>
                          {row.name || row.slug || row.id}
                        </span>
                        {row.maps_label ? (
                          <span className={styles.dropMaps}>{row.maps_label}</span>
                        ) : null}
                      </>
                    );
                    const className = styles.drop;
                    if (href) {
                      return (
                        <Link
                          key={row.slug || row.id}
                          className={className}
                          to={href}
                          title={row.name || row.slug}
                        >
                          {inner}
                        </Link>
                      );
                    }
                    return (
                      <span key={row.slug || row.id} className={className}>
                        {inner}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </TarkovItemBlock>
      ) : null}

      {quests.length ? (
        <TarkovItemBlock title="任务奖励" count={quests.length}>
          <div className={styles.quests}>
            {quests.map((row: QuestReward) => {
              const slug = row.trader_slug || "";
              const trader = traderDisplayName(slug, row.trader_name || "");
              const count = Number(row.count || 1);
              const kind = row.kind;
              return (
                <Link
                  key={`${row.id}-${row.kind}`}
                  className={styles.quest}
                  to={tarkovTaskHref(row.id)}
                >
                  <span className={`${styles.questKind} ${kindClass(kind)}`}>
                    {questKindChip(kind)}
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
                </Link>
              );
            })}
          </div>
        </TarkovItemBlock>
      ) : null}
    </section>
  );
}
