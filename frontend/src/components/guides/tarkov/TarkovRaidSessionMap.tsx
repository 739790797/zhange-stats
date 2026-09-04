import { Alert, Spin } from "antd";
import { Suspense, lazy } from "react";
import type { TarkovMapDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { tarkovMapViewerLayerProps } from "@/lib/tarkovMapViewerDetail";
import type { TarkovRaidRoomLiveMapProps } from "@/components/guides/tarkov/TarkovRaidRoomLiveMap";
import { PanelFallback } from "@/components/RouteFallback";
import catalogCss from "./TarkovItemCatalogPanel.module.css";

const TarkovRaidRoomLiveMap = lazy(() =>
  import("@/components/guides/tarkov/TarkovRaidRoomLiveMap").then((m) => ({
    default: m.TarkovRaidRoomLiveMap,
  })),
);

type Props = Omit<
  TarkovRaidRoomLiveMapProps,
  | "parentSlug"
  | "extracts"
  | "bosses"
  | "spawns"
  | "locks"
  | "hazards"
  | "switches"
  | "stationaryWeapons"
  | "btrStops"
  | "lootContainers"
  | "lootLoose"
  | "places"
> & {
  detail?: TarkovMapDetail | null;
  loading?: boolean;
  error?: unknown;
};

export function TarkovRaidSessionMap({
  detail,
  loading,
  error,
  ...live
}: Props) {
  if (loading) {
    return (
      <div className={catalogCss.status}>
        <Spin tip="加载地图…" />
      </div>
    );
  }
  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        message="地图加载失败"
        description={apiError(error, "地图加载失败")}
      />
    );
  }
  return (
    <Suspense fallback={<PanelFallback tip="加载地图…" />}>
      <TarkovRaidRoomLiveMap
        {...live}
        {...tarkovMapViewerLayerProps(detail)}
      />
    </Suspense>
  );
}
