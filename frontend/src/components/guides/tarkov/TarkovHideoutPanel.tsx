import { Alert, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovHideout,
  type TarkovHideoutLevel,
  type TarkovHideoutStation,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_HIDEOUT_PATH,
  tarkovHideoutHref,
  tarkovTraderHref,
} from "@/lib/tarkovHomeNav";
import { formatDurationSeconds, formatMoney } from "@/lib/tarkovItemFormat";
import { guideItemFleaCost } from "@/lib/tarkovGuideItemCost";
import { TarkovGuideItemStack } from "@/components/guides/tarkov/TarkovGuideItemCell";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovGuideTrade.module.css";

type Props = {
  stationSlug?: string;
};

const EMPTY_STATIONS: TarkovHideoutStation[] = [];

function levelCost(level: TarkovHideoutLevel): number | null {
  return guideItemFleaCost(level.item_requirements);
}

export function TarkovHideoutPanel({ stationSlug }: Props) {
  const gameMode = useTarkovGameMode();
  const [searchParams, setSearchParams] = useSearchParams();
  const selected =
    stationSlug || (searchParams.get("station") || "").trim() || "all";

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-hideout", gameMode],
    queryFn: fetchTarkovHideout,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const stations = catalogQuery.data?.items ?? EMPTY_STATIONS;
  const visible = useMemo(() => {
    if (selected === "all") return stations;
    return stations.filter(
      (row) => row.slug === selected || row.id === selected,
    );
  }, [stations, selected]);

  const setStation = (slug: string) => {
    if (stationSlug) return;
    const next = new URLSearchParams(searchParams);
    if (!slug || slug === "all") next.delete("station");
    else next.set("station", slug);
    setSearchParams(next, { replace: true });
  };

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
        message="藏身处加载失败"
        description={apiError(catalogQuery.error, "藏身处加载失败")}
      />
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.chipBar}>
        {stationSlug ? (
          <Link
            to={TARKOV_HIDEOUT_PATH}
            className={`${styles.chipBtn} ${styles.chipAll}`}
          >
            全部
          </Link>
        ) : (
          <button
            type="button"
            className={`${styles.chipBtn} ${styles.chipAll} ${
              selected === "all" ? styles.chipOn : ""
            }`}
            onClick={() => setStation("all")}
          >
            全部
          </button>
        )}
        {stations.map((station) => {
          const on = station.slug === selected;
          const inner = station.image_link ? (
            <img src={station.image_link} alt="" title={station.name} />
          ) : (
            station.name.slice(0, 2)
          );
          if (stationSlug) {
            return (
              <Link
                key={station.slug}
                to={tarkovHideoutHref(station.slug)}
                className={`${styles.chipBtn} ${on ? styles.chipOn : ""}`}
                title={station.name}
              >
                {inner}
              </Link>
            );
          }
          return (
            <button
              key={station.slug}
              type="button"
              className={`${styles.chipBtn} ${on ? styles.chipOn : ""}`}
              title={station.name}
              onClick={() => setStation(station.slug)}
            >
              {inner}
            </button>
          );
        })}
      </div>

      {visible.map((station) => (
        <StationBlock key={station.id} station={station} />
      ))}
    </div>
  );
}

function StationBlock({ station }: { station: TarkovHideoutStation }) {
  return (
    <div className={styles.stack}>
      {(station.levels || []).map((level) => {
        if (!level.item_requirements?.length) return null;
        const columns: ColumnsType<(typeof level.item_requirements)[number]> = [
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
            width: 140,
            align: "right",
            render: (_: unknown, row) => formatMoney(row.flea_price),
          },
        ];
        const cost = levelCost(level);
        return (
          <div key={level.id || `${station.slug}-${level.level}`}>
            <div className={styles.stationHead}>
              {station.image_link ? (
                <img
                  className={styles.stationIcon}
                  src={station.image_link}
                  alt=""
                />
              ) : null}
              <Link
                className={styles.stationName}
                to={tarkovHideoutHref(station.slug)}
              >
                {station.name}
              </Link>
              <span className={styles.levelLabel}>Lv.{level.level}</span>
              <span className={styles.reqs}>
                {formatDurationSeconds(level.construction_time)}
                {cost != null ? ` · ${formatMoney(cost)}` : ""}
              </span>
            </div>
            {level.description ? (
              <div className={styles.reqs}>{level.description}</div>
            ) : null}
            {level.station_requirements?.length ||
            level.trader_requirements?.length ||
            level.skill_requirements?.length ? (
              <div className={styles.reqs}>
                {[
                  ...(level.station_requirements || []).map(
                    (req) => `${req.station_name} Lv.${req.level}`,
                  ),
                  ...(level.skill_requirements || []).map(
                    (req) => `${req.skill} ${req.level}`,
                  ),
                ]
                  .filter(Boolean)
                  .join(" · ")}
                {level.trader_requirements?.map((req) => (
                  <span key={`${req.id}-${req.level}`}>
                    {" · "}
                    <Link to={tarkovTraderHref(req.slug || req.id)}>
                      {req.name} LL{req.level}
                    </Link>
                  </span>
                ))}
              </div>
            ) : null}
            <div className={tableStyles.table}>
              <Table
                rowKey={(row) => row.id}
                columns={columns}
                dataSource={level.item_requirements}
                pagination={false}
                size="small"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
