import { Button, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { TarkovBarter, TarkovCraft, TarkovItemDetail } from "@/api/guidesApi";
import {
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
  craftRecipeSourceLabel,
  dropSourceHref,
  dropSourcePortrait,
  dropSourceSectionLabel,
  hasFleaQuote,
  ITEM_RELATION_PREVIEW,
  itemHasBarterRelations,
  itemHasCraftRelations,
  itemHasDropRelations,
  itemHasHideoutRelations,
  itemHasQuestRelations,
  previewRows,
  questKindChip,
  questRelationSteps,
  questStepCountText,
  questStepPrimaryText,
  splitItemDropSources,
  type ItemFleaQuote,
  type QuestRelationStep,
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

type Props = {
  detail: TarkovItemDetail;
  flea?: ItemFleaQuote | null;
  traderBuys?: VendorOffer[];
  traderSells?: VendorOffer[];
  bestSell?: VendorOffer | null;
};

type QuestTableRow = {
  id: string;
  name?: string;
  trader_slug?: string;
  trader_name?: string;
  kind?: string;
  count?: number | null;
  found_in_raid?: boolean | null;
  steps?: QuestRelationStep[];
};

function FirMark({ show }: { show?: boolean | null }) {
  if (!show) return null;
  return (
    <span className={styles.fir} title="战局内找到">
      战局内
    </span>
  );
}

function ExpandButton({
  total,
  open,
  onToggle,
}: {
  total: number;
  open: boolean;
  onToggle: () => void;
}) {
  if (total <= ITEM_RELATION_PREVIEW) return null;
  return (
    <Button type="link" size="small" className={styles.expand} onClick={onToggle}>
      {open ? "收起" : `显示全部 ${total}`}
    </Button>
  );
}

function ExpandableBlock<T>({
  title,
  rows,
  extra,
  children,
}: {
  title: string;
  rows: T[];
  extra?: ReactNode;
  children: (visible: T[]) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  if (!rows.length) return null;
  const showExpand = rows.length > ITEM_RELATION_PREVIEW;
  return (
    <TarkovItemBlock
      title={title}
      count={rows.length}
      extra={
        extra || showExpand ? (
          <>
            {extra}
            {showExpand ? (
              <ExpandButton
                total={rows.length}
                open={open}
                onToggle={() => setOpen((value) => !value)}
              />
            ) : null}
          </>
        ) : undefined
      }
    >
      {children(previewRows(rows, open))}
    </TarkovItemBlock>
  );
}

function TraderCell({ row }: { row: TarkovBarter }) {
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
  if (slug) {
    return (
      <Link className={styles.traderCell} to={tarkovTraderHref(slug)}>
        {inner}
      </Link>
    );
  }
  return <span className={styles.traderCell}>{inner}</span>;
}

function StationCell({ row }: { row: TarkovCraft }) {
  return (
    <span>
      {row.station_slug ? (
        <Link to={tarkovHideoutHref(row.station_slug)}>{row.station_name}</Link>
      ) : (
        row.station_name
      )}
      {row.level ? <span className={styles.level}> Lv.{row.level}</span> : null}
    </span>
  );
}

function RecipeSourceCell({
  row,
}: {
  row: { task_unlock?: string | null; task_unlock_name?: string | null };
}) {
  const label = craftRecipeSourceLabel(row.task_unlock, row.task_unlock_name);
  if (!row.task_unlock) {
    return <span className={styles.muted}>{label}</span>;
  }
  return (
    <Link className={styles.sourceLink} to={tarkovTaskHref(row.task_unlock)}>
      {label}
    </Link>
  );
}

/** 两张交换表共用，固定列宽让表头对齐。 */
const BARTER_COL_WIDTH = {
  trader: "18%",
  source: "14%",
  required: "40%",
  offered: "28%",
} as const;

/** 两张制作表共用，固定列宽让表头对齐。 */
const CRAFT_COL_WIDTH = {
  station: "16%",
  source: "14%",
  required: "38%",
  product: "22%",
  duration: "10%",
} as const;

function barterColumns(itemId: string): ColumnsType<TarkovBarter> {
  return [
    {
      title: "商人",
      key: "trader",
      width: BARTER_COL_WIDTH.trader,
      render: (_: unknown, row) => <TraderCell row={row} />,
    },
    {
      title: "配方来源",
      key: "source",
      width: BARTER_COL_WIDTH.source,
      render: (_: unknown, row) => <RecipeSourceCell row={row} />,
    },
    {
      title: "消耗物品",
      key: "required",
      width: BARTER_COL_WIDTH.required,
      render: (_: unknown, row) => (
        <TarkovGuideItemStack
          items={row.required_items}
          highlightId={itemId}
          alwaysCount
        />
      ),
    },
    {
      title: "获得物品",
      key: "offered",
      width: BARTER_COL_WIDTH.offered,
      render: (_: unknown, row) => (
        <TarkovGuideItemStack
          items={row.offered_item ? [row.offered_item] : []}
          highlightId={itemId}
          alwaysCount
        />
      ),
    },
  ];
}

function craftColumns(itemId: string): ColumnsType<TarkovCraft> {
  return [
    {
      title: "模块",
      key: "station",
      width: CRAFT_COL_WIDTH.station,
      render: (_: unknown, row) => <StationCell row={row} />,
    },
    {
      title: "配方来源",
      key: "source",
      width: CRAFT_COL_WIDTH.source,
      render: (_: unknown, row) => <RecipeSourceCell row={row} />,
    },
    {
      title: "材料",
      key: "required",
      width: CRAFT_COL_WIDTH.required,
      render: (_: unknown, row) => (
        <TarkovGuideItemStack
          items={row.required_items}
          highlightId={itemId}
          alwaysCount
        />
      ),
    },
    {
      title: "产品",
      key: "product",
      width: CRAFT_COL_WIDTH.product,
      render: (_: unknown, row) => (
        <TarkovGuideItemStack
          items={row.product_item ? [row.product_item] : []}
          highlightId={itemId}
          alwaysCount
        />
      ),
    },
    {
      title: "时长",
      key: "duration",
      width: CRAFT_COL_WIDTH.duration,
      render: (_: unknown, row) => formatDurationSeconds(row.duration),
    },
  ];
}

function TradeTable<T extends object>({
  columns,
  rows,
  rowKey,
}: {
  columns: ColumnsType<T>;
  rows: T[];
  rowKey: (row: T) => string;
}) {
  return (
    <Table<T>
      className={`${tableStyles.table} ${styles.blockTable}`}
      size="small"
      tableLayout="fixed"
      rowKey={rowKey}
      columns={columns}
      dataSource={rows}
      pagination={false}
    />
  );
}

function QuestTraderCell({
  slug,
  name,
}: {
  slug?: string;
  name?: string;
}) {
  const key = slug || "";
  const label = traderDisplayName(key, name || key);
  const inner = (
    <>
      {key ? (
        <img className={styles.traderIcon} src={traderIconUrl(key)} alt="" />
      ) : null}
      <span>{label || "—"}</span>
    </>
  );
  if (!key) return <span className={styles.traderCell}>{inner}</span>;
  return (
    <Link className={styles.traderCell} to={tarkovTraderHref(key)}>
      {inner}
    </Link>
  );
}

function QuestStepsCell({ row }: { row: QuestTableRow }) {
  const steps = questRelationSteps(row);
  if (!steps.length) return "—";
  return (
    <div className={styles.questSteps}>
      {steps.map((step, index) => {
        const count = questStepCountText(step.count);
        return (
          <div
            key={step.id || `${step.type || "step"}-${index}`}
            className={styles.questStep}
          >
            <span className={styles.questStepText}>
              {questStepPrimaryText(step)}
            </span>
            {count ? (
              <span className={styles.questStepCount}>{count}</span>
            ) : null}
            <FirMark show={step.found_in_raid} />
          </div>
        );
      })}
    </div>
  );
}

function questColumns(): ColumnsType<QuestTableRow> {
  return [
    {
      title: "商人",
      key: "trader",
      width: 180,
      render: (_: unknown, row) => (
        <QuestTraderCell slug={row.trader_slug} name={row.trader_name} />
      ),
    },
    {
      title: "任务",
      key: "name",
      width: 180,
      render: (_: unknown, row) => (
        <Link className={styles.taskLink} to={tarkovTaskHref(row.id)}>
          {row.name || row.id}
        </Link>
      ),
    },
    {
      title: "相关步骤",
      key: "steps",
      render: (_: unknown, row) => <QuestStepsCell row={row} />,
    },
  ];
}

function TradeSection({
  detail,
  flea,
  traderBuys,
  traderSells,
  bestSell,
}: Props) {
  const itemId = detail.id;
  const sourceBarters = detail.sources?.barters || [];
  const useBarters = detail.uses?.barters || [];
  const showFlea = hasFleaQuote(flea);
  if (
    !showFlea &&
    !traderBuys?.length &&
    !traderSells?.length &&
    !itemHasBarterRelations(detail.sources, detail.uses)
  ) {
    return null;
  }
  return (
    <section className={styles.wrap}>
      <h2 className={styles.title}>交易</h2>
      {showFlea ? (
        <TarkovItemBlock title="跳蚤市场">
          <TarkovItemFleaQuote flea={flea} />
        </TarkovItemBlock>
      ) : null}
      {traderBuys?.length ? (
        <TarkovItemBlock title="从商人购买" count={traderBuys.length}>
          <TarkovItemOfferRow offers={traderBuys} />
        </TarkovItemBlock>
      ) : null}
      {traderSells?.length ? (
        <TarkovItemBlock title="出售给商人" count={traderSells.length}>
          <TarkovItemOfferRow offers={traderSells} best={bestSell} />
        </TarkovItemBlock>
      ) : null}
      <ExpandableBlock title="换到此物" rows={sourceBarters}>
        {(rows) => (
          <TradeTable<TarkovBarter>
            columns={barterColumns(itemId)}
            rows={rows}
            rowKey={(row) =>
              row.id || `${row.trader_slug}-${row.min_trader_level}`
            }
          />
        )}
      </ExpandableBlock>
      <ExpandableBlock title="用此物换" rows={useBarters}>
        {(rows) => (
          <TradeTable<TarkovBarter>
            columns={barterColumns(itemId)}
            rows={rows}
            rowKey={(row) =>
              row.id || `${row.trader_slug}-${row.min_trader_level}`
            }
          />
        )}
      </ExpandableBlock>
    </section>
  );
}

function QuestSection({ detail }: { detail: TarkovItemDetail }) {
  const rewards = detail.sources?.quest_rewards || [];
  const tasks = detail.uses?.tasks || [];
  if (!itemHasQuestRelations(detail.sources, detail.uses)) return null;
  return (
    <section className={styles.wrap}>
      <h2 className={styles.title}>任务</h2>
      <ExpandableBlock title="任务奖励" rows={rewards}>
        {(rows) => (
          <TradeTable<QuestTableRow>
            columns={questColumns()}
            rows={rows}
            rowKey={(row) => row.id}
          />
        )}
      </ExpandableBlock>
      <ExpandableBlock title="任务需求" rows={tasks}>
        {(rows) => (
          <TradeTable<QuestTableRow>
            columns={questColumns()}
            rows={rows}
            rowKey={(row) => row.id}
          />
        )}
      </ExpandableBlock>
    </section>
  );
}

function CraftSection({ detail }: { detail: TarkovItemDetail }) {
  const products = detail.sources?.crafts || [];
  const materials = detail.uses?.crafts || [];
  if (!itemHasCraftRelations(detail.sources, detail.uses)) return null;
  const itemId = detail.id;
  return (
    <section className={styles.wrap}>
      <h2 className={styles.title}>制作</h2>
      <ExpandableBlock title="作为产品" rows={products}>
        {(rows) => (
          <TradeTable<TarkovCraft>
            columns={craftColumns(itemId)}
            rows={rows}
            rowKey={(row) => row.id || `${row.station_slug}-${row.level}`}
          />
        )}
      </ExpandableBlock>
      <ExpandableBlock title="作为材料" rows={materials}>
        {(rows) => (
          <TradeTable<TarkovCraft>
            columns={craftColumns(itemId)}
            rows={rows}
            rowKey={(row) => row.id || `${row.station_slug}-${row.level}`}
          />
        )}
      </ExpandableBlock>
    </section>
  );
}

function HideoutSection({ detail }: { detail: TarkovItemDetail }) {
  const hideout = detail.uses?.hideout || [];
  if (!itemHasHideoutRelations(detail.uses)) return null;
  return (
    <section className={styles.wrap}>
      <h2 className={styles.title}>藏身处</h2>
      <ExpandableBlock
        title="建造"
        rows={hideout}
        extra={
          <Link className={styles.more} to={tarkovHideoutHref()}>
            藏身处
          </Link>
        }
      >
        {(rows) => (
          <div className={styles.quests}>
            {rows.map((row) => {
              const count = Number(row.count || 1);
              const label = `${row.station_name || row.station_slug} Lv.${row.level}`;
              const inner = (
                <>
                  <span className={`${styles.questKind} ${styles.kindBuild}`}>
                    {questKindChip("build")}
                  </span>
                  <span className={styles.questName}>{label}</span>
                  <span className={styles.questMeta}>
                    {count > 1 ? (
                      <span className={styles.questCount}>×{count}</span>
                    ) : null}
                    <FirMark show={row.found_in_raid} />
                  </span>
                </>
              );
              const key = `${row.station_slug || row.station_id}-${row.level}-${row.found_in_raid ? "fir" : "any"}`;
              return row.station_slug ? (
                <Link
                  key={key}
                  className={styles.quest}
                  to={tarkovHideoutHref(row.station_slug)}
                >
                  {inner}
                </Link>
              ) : (
                <span key={key} className={styles.quest}>
                  {inner}
                </span>
              );
            })}
          </div>
        )}
      </ExpandableBlock>
    </section>
  );
}

function DropGroup({
  section,
  rows,
}: {
  section: "boss" | "other";
  rows: TarkovItemDropSource[];
}) {
  const [open, setOpen] = useState(false);
  if (!rows.length) return null;
  const visible = previewRows(rows, open);
  return (
    <div className={styles.dropGroup}>
      <h4 className={styles.dropGroupTitle}>
        {dropSourceSectionLabel(section)}
        <span className={styles.blockCount}>{rows.length}</span>
        <ExpandButton
          total={rows.length}
          open={open}
          onToggle={() => setOpen((value) => !value)}
        />
      </h4>
      <div className={styles.dropRow}>
        {visible.map((row) => {
          const href = dropSourceHref(row);
          const portrait = dropSourcePortrait(row);
          const inner = (
            <>
              <span className={styles.dropIcon}>
                {portrait ? (
                  <img className={styles.dropImg} src={portrait} alt="" />
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
          if (href) {
            return (
              <Link
                key={row.slug || row.id}
                className={styles.drop}
                to={href}
                title={row.name || row.slug}
              >
                {inner}
              </Link>
            );
          }
          return (
            <span key={row.slug || row.id} className={styles.drop}>
              {inner}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function DropSection({ detail }: { detail: TarkovItemDetail }) {
  const drops = detail.sources?.drops || [];
  if (!itemHasDropRelations(detail.sources)) return null;
  const groups = splitItemDropSources(drops);
  return (
    <section className={styles.wrap}>
      <h2 className={styles.title}>掉落</h2>
      <div className={styles.block}>
        {(["boss", "other"] as const).map((section) => (
          <DropGroup key={section} section={section} rows={groups[section]} />
        ))}
      </div>
    </section>
  );
}

export function TarkovItemRelations({
  detail,
  flea,
  traderBuys = [],
  traderSells = [],
  bestSell = null,
}: Props) {
  return (
    <>
      <TradeSection
        detail={detail}
        flea={flea}
        traderBuys={traderBuys}
        traderSells={traderSells}
        bestSell={bestSell}
      />
      <QuestSection detail={detail} />
      <CraftSection detail={detail} />
      <HideoutSection detail={detail} />
      <DropSection detail={detail} />
    </>
  );
}
