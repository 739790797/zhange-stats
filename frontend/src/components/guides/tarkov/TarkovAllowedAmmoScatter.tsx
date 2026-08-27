import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchTarkovAmmo, type TarkovAmmoItem } from "@/api/guidesApi";
import { ammoDetailHref } from "@/lib/tarkovItemTypes";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TarkovAmmoScatterChart } from "@/components/guides/tarkov/TarkovAmmoScatterChart";
import { TarkovAmmoWikiTable } from "@/components/guides/tarkov/TarkovAmmoWikiTable";
import {
  TarkovItemRefGrid,
  type TarkovGuideItemRef,
} from "@/components/guides/tarkov/TarkovGuideItemCell";
import { ammoScatterAxisMax, filterAmmoByIds } from "@/lib/tarkovAmmoScatter";
import styles from "./TarkovAmmoScatterPanel.module.css";

const EMPTY_ITEMS: TarkovAmmoItem[] = [];
const EMBED_HEIGHT = 400;

type Props = {
  ammoIds: string[];
  defaultAmmoId?: string;
  fallbackItems?: TarkovGuideItemRef[];
  note?: string;
};

export function TarkovAllowedAmmoScatter({
  ammoIds,
  defaultAmmoId,
  fallbackItems,
  note,
}: Props) {
  const gameMode = useTarkovGameMode();
  const navigate = useNavigate();
  const ammoQuery = useQuery({
    queryKey: ["guides-tarkov-ammo", gameMode],
    queryFn: fetchTarkovAmmo,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const idSet = useMemo(
    () => new Set(ammoIds.map((id) => id.trim()).filter(Boolean)),
    [ammoIds],
  );

  const data = useMemo(
    () => filterAmmoByIds(ammoQuery.data?.items ?? EMPTY_ITEMS, idSet),
    [ammoQuery.data?.items, idSet],
  );

  const calibers = useMemo(
    () => Array.from(new Set(data.map((row) => row.caliber))),
    [data],
  );

  const axisMax = useMemo(() => ammoScatterAxisMax(data), [data]);

  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hoverFrom, setHoverFrom] = useState<"table" | "chart" | null>(null);
  const leaveTimer = useRef(0);

  const setHover = useCallback((id: string | null, from: "table" | "chart") => {
    window.clearTimeout(leaveTimer.current);
    if (id) {
      setHoveredId(id);
      setHoverFrom(from);
      return;
    }
    leaveTimer.current = window.setTimeout(() => {
      setHoveredId(null);
      setHoverFrom(null);
    }, 80);
  }, []);

  useEffect(
    () => () => window.clearTimeout(leaveTimer.current),
    [],
  );

  const onAmmoClick = (ammo: TarkovAmmoItem) => {
    const id = (ammo.id || "").trim();
    if (!id) return;
    navigate(ammoDetailHref(id));
  };

  if (!idSet.size) return null;

  if (ammoQuery.isLoading) {
    return (
      <div className={styles.embedStatus}>
        <Spin size="small" />
      </div>
    );
  }

  const fallback = fallbackItems?.length ? (
    <>
      <TarkovItemRefGrid items={fallbackItems} />
      {note ? <span className={styles.embedNote}>{note}</span> : null}
    </>
  ) : null;

  if (ammoQuery.isError || !data.length) {
    return fallback;
  }

  return (
    <div className={styles.embedStack}>
      <TarkovAmmoWikiTable
        data={data}
        defaultAmmoId={defaultAmmoId}
        compact
        highlightedId={hoveredId}
        onHoverId={(id) => setHover(id, "table")}
      />
      {note ? <span className={styles.embedNote}>{note}</span> : null}
      <div className={styles.embed}>
        <span className={styles.hint}>点击色点打开弹药详情</span>
        <div className={styles.chart}>
          <TarkovAmmoScatterChart
            data={data}
            colorField={calibers.length <= 1 ? "name" : "caliber"}
            axisMax={axisMax}
            height={EMBED_HEIGHT}
            onAmmoClick={onAmmoClick}
            highlightedId={hoverFrom === "table" ? hoveredId : null}
            onHoverAmmo={(ammo) => setHover(ammo?.id ?? null, "chart")}
          />
        </div>
      </div>
    </div>
  );
}
