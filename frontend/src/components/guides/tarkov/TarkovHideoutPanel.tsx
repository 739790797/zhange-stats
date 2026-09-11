import { Alert, Button, Spin, Table, Tooltip, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovCrafts,
  fetchTarkovHideout,
  fetchTarkovHideoutLevels,
  setTarkovHideoutLevel,
  type TarkovCraft,
  type TarkovHideoutLevel,
  type TarkovHideoutStation,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  traderDisplayName,
  traderIconUrl,
} from "@/lib/tarkovHomeNav";
import { formatDurationSeconds, formatMoney } from "@/lib/tarkovItemFormat";
import {
  guideItemFleaCost,
  type TarkovGuideItemRef,
} from "@/lib/tarkovGuideItemCost";
import { TarkovGuideItemStack } from "@/components/guides/tarkov/TarkovGuideItemCell";
import {
  applyHideoutLevel,
  canSetHideoutLevel,
  currentHideoutLevelSpec,
  filledHideoutLevels,
  formatHideoutBonusValue,
  hideoutDefaultLevel,
  hideoutLevelsFromRows,
  hideoutMaxLevel,
  hideoutReqStatus,
  indexHideoutStations,
  itemReqMet,
  nextHideoutLevelSpec,
  skillReqMet,
  stationReqMet,
  traderReqMet,
  type HideoutReqStatus,
  type HideoutStationSpec,
} from "@/lib/tarkovHideoutProgress";
import tableStyles from "./TarkovDarkTable.module.css";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovHideoutPanel.module.css";

type Station = TarkovHideoutStation & HideoutStationSpec;
type Level = TarkovHideoutLevel & {
  bonuses?: Array<{
    type?: string;
    name?: string;
    value?: number;
    skill?: string;
    slot_items?: NonNullable<TarkovHideoutLevel["item_requirements"]>;
  }>;
};
type Craft = TarkovCraft;

const EMPTY_STATIONS: Station[] = [];

async function fetchStationCrafts(station: string) {
  const pageSize = 100;
  const first = await fetchTarkovCrafts({ station, page: 1, pageSize });
  const items = [...(first.items || [])];
  const total = Number(first.total || items.length);
  let page = 2;
  while (items.length < total && page <= 20) {
    const more = await fetchTarkovCrafts({ station, page, pageSize });
    const batch = more.items || [];
    if (!batch.length) break;
    items.push(...batch);
    page += 1;
  }
  return { ...first, items };
}

function statusClass(status: HideoutReqStatus): string {
  if (status === "met") return styles.met;
  if (status === "unmet") return styles.unmet;
  return styles.unset;
}

function HideoutReqList({
  spec,
  levels,
  byId,
  showItems = true,
  title,
  showFooter = true,
}: {
  spec: Level;
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
  showItems?: boolean;
  title?: string;
  showFooter?: boolean;
}) {
  const stations = spec.station_requirements || [];
  const traders = spec.trader_requirements || [];
  const skills = spec.skill_requirements || [];
  const items = showItems ? spec.item_requirements || [] : [];
  const noReqs =
    !stations.length &&
    !traders.length &&
    !skills.length &&
    !(spec.item_requirements || []).length;
  return (
    <div className={styles.reqList}>
      {title ? <div className={styles.reqTitle}>{title}</div> : null}
      {noReqs ? <div className={styles.unset}>无前置</div> : null}
      {stations.map((req) => {
        const other = byId.get((req.station_id || "").trim());
        const status = hideoutReqStatus(stationReqMet(req, levels, byId));
        return (
          <div
            key={`${req.station_id}-${req.level}`}
            className={`${styles.reqRow} ${statusClass(status)}`}
          >
            {other?.image_link ? (
              <img src={other.image_link} alt="" />
            ) : null}
            <span>
              {req.station_name || other?.name || req.station_slug} Lv.
              {req.level}
            </span>
          </div>
        );
      })}
      {traders.map((req) => {
        const status = hideoutReqStatus(traderReqMet(req, undefined));
        const slug = req.slug || req.id || "";
        return (
          <div
            key={`${req.id}-${req.level}`}
            className={`${styles.reqRow} ${statusClass(status)}`}
          >
            {slug ? <img src={traderIconUrl(slug)} alt="" /> : null}
            <span>
              {traderDisplayName(req.slug, req.name)} LL{req.level}
              {status === "unset" ? " · 未维护" : ""}
            </span>
          </div>
        );
      })}
      {skills.map((req) => {
        const status = hideoutReqStatus(skillReqMet(req, undefined));
        return (
          <div
            key={`${req.skill_id || req.skill}-${req.level}`}
            className={`${styles.reqRow} ${statusClass(status)}`}
          >
            <span>
              {req.skill || req.skill_id} {req.level}
              {status === "unset" ? " · 未维护" : ""}
            </span>
          </div>
        );
      })}
      {items.map((req) => {
        const status = hideoutReqStatus(itemReqMet(req, undefined));
        const label = [req.name || req.id, req.found_in_raid ? "战局内" : ""]
          .filter(Boolean)
          .join(" · ");
        return (
          <div
            key={`${req.id}-${req.count}`}
            className={`${styles.reqRow} ${statusClass(status)}`}
          >
            {req.icon_link ? <img src={req.icon_link} alt="" /> : null}
            <span>
              {req.count && req.count !== 1 ? `${req.count}× ` : ""}
              {label}
              {status === "unset" ? " · 未登记仓库" : ""}
            </span>
          </div>
        );
      })}
      {showFooter && spec.construction_time ? (
        <div className={styles.reqNote}>
          建造 {formatDurationSeconds(spec.construction_time)}
        </div>
      ) : null}
      {showFooter ? (
        <div className={styles.reqNote}>
          商人好感与技能将在个人资料可维护后计入绿灯。
        </div>
      ) : null}
    </div>
  );
}

function HideoutReqTooltip({
  station,
  current,
  levels,
  byId,
}: {
  station: Station;
  current: number;
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
}) {
  const next = nextHideoutLevelSpec(station, current) as Level | undefined;
  if (!next) {
    return <div className={styles.reqTitle}>已满级</div>;
  }
  return (
    <HideoutReqList
      spec={next}
      levels={levels}
      byId={byId}
      title={`升到 Lv.${next.level} 需要`}
    />
  );
}

function StationDetail({
  station,
  current,
  levels,
  byId,
}: {
  station: Station;
  current: number;
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
}) {
  const gameMode = useTarkovGameMode();
  const currentSpec = currentHideoutLevelSpec(station, current) as
    | Level
    | undefined;
  const nextSpec = nextHideoutLevelSpec(station, current) as Level | undefined;
  const craftsQuery = useQuery({
    queryKey: ["guides-tarkov-crafts", gameMode, station.slug || station.id],
    queryFn: () => fetchStationCrafts(station.slug || station.id),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(station.slug || station.id),
  });
  const crafts = useMemo(() => {
    const rows = (craftsQuery.data?.items || []) as Craft[];
    return [...rows].sort(
      (a, b) => Number(a.level || 0) - Number(b.level || 0),
    );
  }, [craftsQuery.data]);
  const bonuses = currentSpec?.bonuses || [];
  const nextCost = nextSpec ? guideItemFleaCost(nextSpec.item_requirements) : null;

  const craftColumns: ColumnsType<Craft> = [
    {
      title: "产物",
      key: "product",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.product_item ? [row.product_item] : []} />
      ),
    },
    {
      title: "材料",
      key: "need",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.required_items} />
      ),
    },
    {
      title: "模块",
      dataIndex: "level",
      width: 72,
      render: (level: number) => `Lv.${level}`,
    },
    {
      title: "时长",
      dataIndex: "duration",
      width: 88,
      render: (duration: number) => formatDurationSeconds(duration),
    },
  ];

  return (
    <div className={styles.detail}>
      <div className={styles.detailHead}>
        {station.image_link ? (
          <img className={styles.detailIcon} src={station.image_link} alt="" />
        ) : null}
        <div>
          <h3 className={styles.detailName}>{station.name}</h3>
          <div className={styles.detailSub}>
            当前 Lv.{current}
            {hideoutMaxLevel(station)
              ? ` / ${hideoutMaxLevel(station)}`
              : ""}
            {currentSpec?.description ? ` · ${currentSpec.description}` : ""}
          </div>
        </div>
      </div>

      {bonuses.length ? (
        <section>
          <h4 className={styles.sectionTitle}>当前功能</h4>
          <div className={styles.bonusList}>
            {bonuses.map((bonus, index) => (
              <div
                key={`${bonus.type}-${index}`}
                className={styles.bonusRow}
              >
                <span className={styles.bonusName}>
                  {bonus.name || bonus.type}
                  {bonus.skill ? `（${bonus.skill}）` : ""}
                </span>
                <span className={styles.bonusValue}>
                  {formatHideoutBonusValue(bonus.type || "", Number(bonus.value || 0))}
                </span>
              </div>
            ))}
          </div>
          {bonuses.some((bonus) => bonus.slot_items?.length) ? (
            <TarkovGuideItemStack
              items={bonuses.flatMap((bonus) => bonus.slot_items || [])}
            />
          ) : null}
        </section>
      ) : current > 0 ? (
        <div className={styles.detailSub}>该等级没有列出加成。</div>
      ) : (
        <div className={styles.detailSub}>尚未建造。</div>
      )}

      {nextSpec ? (
        <section>
          <h4 className={styles.sectionTitle}>
            升到 Lv.{nextSpec.level}
            {nextSpec.construction_time
              ? ` · ${formatDurationSeconds(nextSpec.construction_time)}`
              : ""}
            {nextCost != null ? ` · ${formatMoney(nextCost)}` : ""}
          </h4>
          {nextSpec.description ? (
            <div className={styles.detailSub}>{nextSpec.description}</div>
          ) : null}
          <HideoutReqList
            spec={nextSpec}
            levels={levels}
            byId={byId}
            showItems={false}
            showFooter={false}
          />
          <div className={styles.detailSub}>
            商人好感、技能与仓库材料本期只展示，不挡升级。
          </div>
          {nextSpec.item_requirements?.length ? (
            <div className={tableStyles.table}>
              <Table<TarkovGuideItemRef>
                rowKey={(row) => row.id}
                columns={[
                  {
                    title: "材料",
                    key: "item",
                    render: (_: unknown, row) => (
                      <TarkovGuideItemStack items={[row]} />
                    ),
                  },
                  {
                    title: "跳蚤",
                    key: "flea",
                    width: 120,
                    align: "right" as const,
                    render: (_: unknown, row) => formatMoney(row.flea_price),
                  },
                ]}
                dataSource={nextSpec.item_requirements}
                pagination={false}
                size="small"
              />
            </div>
          ) : (
            <div className={styles.detailSub}>无额外材料。</div>
          )}
        </section>
      ) : null}

      {craftsQuery.isLoading ? (
        <Spin />
      ) : crafts.length ? (
        <section>
          <h4 className={styles.sectionTitle}>制作</h4>
          <div className={styles.detailSub}>
            本设施全部配方；高于当前等级的行灰显预告。
          </div>
          <div className={tableStyles.table}>
            <Table<Craft>
              rowKey={(row) => row.id}
              columns={craftColumns}
              dataSource={crafts}
              pagination={false}
              size="small"
              rowClassName={(row) =>
                Number(row.level || 0) > current ? styles.craftLocked : ""
              }
            />
          </div>
        </section>
      ) : null}
    </div>
  );
}

export function TarkovHideoutPanel({ stationSlug }: { stationSlug?: string }) {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedKey =
    (stationSlug || searchParams.get("station") || "").trim();

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-hideout", gameMode],
    queryFn: fetchTarkovHideout,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const levelsQuery = useQuery({
    queryKey: ["guides-tarkov-hideout-levels", gameMode],
    queryFn: fetchTarkovHideoutLevels,
    staleTime: 30_000,
    retry: 1,
  });

  const stations = (catalogQuery.data?.items || EMPTY_STATIONS) as Station[];
  const byId = useMemo(() => indexHideoutStations(stations), [stations]);
  const levels = useMemo(
    () =>
      filledHideoutLevels(
        stations,
        hideoutLevelsFromRows(levelsQuery.data?.levels),
      ),
    [stations, levelsQuery.data],
  );
  const selected =
    stations.find(
      (row) => row.slug === selectedKey || row.id === selectedKey,
    ) || null;

  const mutation = useMutation({
    mutationFn: ({ stationId, level }: { stationId: string; level: number }) =>
      setTarkovHideoutLevel(stationId, level),
    onSuccess: (data) => {
      queryClient.setQueryData(
        ["guides-tarkov-hideout-levels", gameMode],
        data,
      );
    },
    onError: (error) => {
      message.error(apiError(error, "藏身处等级保存失败"));
    },
  });

  const setSelected = (slug: string) => {
    if (stationSlug) return;
    const next = new URLSearchParams(searchParams);
    if (!slug) next.delete("station");
    else next.set("station", slug);
    setSearchParams(next, { replace: true });
  };

  const changeLevel = (station: Station, delta: 1 | -1) => {
    const ident = (station.id || "").trim();
    if (!ident || mutation.isPending) return;
    const current = levels[ident] ?? hideoutDefaultLevel(station);
    const target = current + delta;
    try {
      applyHideoutLevel(stations, levels, ident, target);
    } catch {
      return;
    }
    mutation.mutate({ stationId: ident, level: target });
  };

  if (catalogQuery.isLoading || levelsQuery.isLoading) {
    return (
      <div className={trade.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="藏身处加载失败"
        description={apiError(catalogQuery.error, "藏身处加载失败")}
      />
    );
  }

  if (levelsQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="藏身处进度加载失败"
        description={apiError(levelsQuery.error, "藏身处进度加载失败")}
      />
    );
  }

  return (
    <div className={trade.stack}>
      <div className={styles.grid}>
        {stations.map((station) => {
          const ident = station.id || "";
          const current = levels[ident] ?? hideoutDefaultLevel(station);
          const on = selected?.id === ident;
          const canUp = canSetHideoutLevel(
            station,
            current + 1,
            levels,
            byId,
          );
          const canDown = current > hideoutDefaultLevel(station);
          return (
            <Tooltip
              key={ident}
              placement="bottom"
              mouseEnterDelay={0.25}
              title={
                <HideoutReqTooltip
                  station={station}
                  current={current}
                  levels={levels}
                  byId={byId}
                />
              }
            >
              <div
                className={`${styles.cell}${on ? ` ${styles.cellOn}` : ""}`}
                role="button"
                tabIndex={0}
                onClick={() => setSelected(station.slug || ident)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelected(station.slug || ident);
                  }
                }}
              >
                <div className={styles.cellTop}>
                  {station.image_link ? (
                    <img
                      className={styles.cellIcon}
                      src={station.image_link}
                      alt=""
                    />
                  ) : null}
                  <span className={styles.cellName}>{station.name}</span>
                </div>
                <div className={styles.cellMeta}>
                  <span className={styles.level}>Lv.{current}</span>
                  <span className={styles.actions}>
                    <Button
                      type="link"
                      size="small"
                      disabled={!canDown || mutation.isPending}
                      onClick={(event) => {
                        event.stopPropagation();
                        changeLevel(station, -1);
                      }}
                    >
                      降
                    </Button>
                    <Button
                      type="link"
                      size="small"
                      disabled={!canUp || mutation.isPending}
                      onClick={(event) => {
                        event.stopPropagation();
                        changeLevel(station, 1);
                      }}
                    >
                      升
                    </Button>
                  </span>
                </div>
              </div>
            </Tooltip>
          );
        })}
      </div>
      {selected ? (
        <StationDetail
          station={selected}
          current={levels[selected.id] ?? hideoutDefaultLevel(selected)}
          levels={levels}
          byId={byId}
        />
      ) : (
        <div className={styles.detailSub}>点击设施查看功能与制作。</div>
      )}
      <div className={trade.meta}>
        {catalogQuery.data?.station_count ?? stations.length} 个模块
        {catalogQuery.data?.synced_at
          ? ` · 同步 ${catalogQuery.data.synced_at}`
          : ""}
      </div>
    </div>
  );
}
