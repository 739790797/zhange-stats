import { Alert, InputNumber, Spin } from "antd";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovCrafts,
  fetchTarkovItemDetail,
  type TarkovItemDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { tarkovHideoutHref } from "@/lib/tarkovHomeNav";
import {
  formatDurationSeconds,
  formatMoney,
} from "@/lib/tarkovItemFormat";
import {
  BITCOIN_ITEM_ID,
  GRAPHIC_CARD_ITEM_ID,
  MAX_GRAPHICS_CARDS,
  MIN_GRAPHICS_CARDS,
  bitcoinMsToProduce,
  bitcoinPerDay,
  DEFAULT_BITCOIN_DURATION_SEC,
} from "@/lib/tarkovBitcoinFarm";
import { TarkovGuideItemCell } from "@/components/guides/tarkov/TarkovGuideItemCell";
import styles from "./TarkovGuideTrade.module.css";

function detailFlea(detail: TarkovItemDetail | undefined): {
  price: number;
  icon: string;
  types: string[];
} {
  const raw = (detail?.item || {}) as Record<string, unknown>;
  const price = Number(raw.lastLowPrice || raw.avg24hPrice || 0);
  return {
    price: Number.isFinite(price) ? price : 0,
    icon: String(raw.iconLink || raw.baseImageLink || ""),
    types: Array.isArray(raw.types) ? raw.types.map(String) : [],
  };
}

export function TarkovBitcoinFarmPanel() {
  const [gpus, setGpus] = useState(10);
  const craftsQuery = useQuery({
    queryKey: ["guides-tarkov-crafts", "bitcoin-farm"],
    queryFn: () =>
      fetchTarkovCrafts({ station: "bitcoin-farm", page: 1, pageSize: 20 }),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const bitcoinQuery = useQuery({
    queryKey: ["guides-tarkov-item", BITCOIN_ITEM_ID],
    queryFn: () => fetchTarkovItemDetail(BITCOIN_ITEM_ID),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const gpuQuery = useQuery({
    queryKey: ["guides-tarkov-item", GRAPHIC_CARD_ITEM_ID],
    queryFn: () => fetchTarkovItemDetail(GRAPHIC_CARD_ITEM_ID),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const craft =
    (craftsQuery.data?.items ?? []).find(
      (row) => row.product_item?.id === BITCOIN_ITEM_ID,
    ) || craftsQuery.data?.items?.[0];
  const durationSec = craft?.duration || DEFAULT_BITCOIN_DURATION_SEC;
  const bitcoin = detailFlea(bitcoinQuery.data);
  const gpu = detailFlea(gpuQuery.data);
  const bitcoinPrice = bitcoin.price;
  const gpuPrice = gpu.price;

  const stats = useMemo(() => {
    const ms = bitcoinMsToProduce(gpus, durationSec);
    const perDay = bitcoinPerDay(gpus, durationSec);
    const revenueDay = perDay * bitcoinPrice;
    return {
      seconds: ms / 1000,
      perDay,
      revenueDay,
    };
  }, [gpus, durationSec, bitcoinPrice]);

  if (craftsQuery.isLoading && bitcoinQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (craftsQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="比特币矿场加载失败"
        description={apiError(craftsQuery.error, "比特币矿场加载失败")}
      />
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.meta}>
        产出间隔按 tarkov.dev 公式随显卡数量缩放。燃料/太阳能未计入。
        {craft?.station_slug ? (
          <>
            {" "}
            <Link to={tarkovHideoutHref(craft.station_slug)}>藏身处模块</Link>
          </>
        ) : null}
      </div>
      <div className={styles.sliderRow}>
        <span className={styles.reqs}>显卡数量</span>
        <InputNumber
          min={MIN_GRAPHICS_CARDS}
          max={MAX_GRAPHICS_CARDS}
          value={gpus}
          onChange={(value) => setGpus(Number(value) || MIN_GRAPHICS_CARDS)}
        />
      </div>
      <div className={styles.statGrid}>
        <div className={styles.stat}>
          <div className={styles.statLabel}>单枚耗时</div>
          <div className={styles.statValue}>
            {formatDurationSeconds(stats.seconds)}
          </div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>每天枚数</div>
          <div className={styles.statValue}>{stats.perDay.toFixed(2)}</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>每天跳蚤收入</div>
          <div className={styles.statValue}>
            {formatMoney(stats.revenueDay)}
          </div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>显卡跳蚤价</div>
          <div className={styles.statValue}>{formatMoney(gpuPrice)}</div>
        </div>
      </div>
      <div className={styles.stationHead}>
        {bitcoinQuery.data ? (
          <TarkovGuideItemCell
            item={{
              id: bitcoinQuery.data.id,
              name: bitcoinQuery.data.name,
              icon_link: bitcoin.icon,
              types: bitcoin.types,
              flea_price: bitcoin.price,
            }}
            showCount={false}
            showPrice
          />
        ) : null}
        {gpuQuery.data ? (
          <TarkovGuideItemCell
            item={{
              id: gpuQuery.data.id,
              name: gpuQuery.data.name,
              icon_link: gpu.icon,
              types: gpu.types,
              flea_price: gpu.price,
            }}
            showCount={false}
            showPrice
          />
        ) : null}
      </div>
    </div>
  );
}
