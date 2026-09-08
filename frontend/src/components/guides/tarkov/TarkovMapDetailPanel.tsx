import { Alert, Spin, message } from "antd";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMapDetail, type TarkovMapDetail } from "@/api/guidesApi";
import { useTarkovMapPlaceEditor } from "@/components/guides/tarkov/TarkovMapPlaceEditor";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import {
  parseTarkovMaintainMode,
  tarkovMapHref,
  tarkovMapMaintainHref,
} from "@/lib/tarkovHomeNav";
import { logMapLabel } from "@/lib/tarkovGameLogs";
import { tarkovMapPageFollowHref } from "@/lib/tarkovRaidPrep";
import {
  useTarkovLastLogMapId,
  useTarkovLastLogPhase,
} from "@/lib/useTarkovLiveWatch";
import { tarkovMapViewerLayerProps } from "@/lib/tarkovMapViewerDetail";
import { PanelFallback } from "@/components/RouteFallback";
import styles from "./TarkovMapsPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

type Props = {
  slug: string;
};

export function TarkovMapDetailPanel({ slug }: Props) {
  const gameMode = useTarkovGameMode();
  const navigate = useNavigate();
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const autoMapSigRef = useRef("");
  const followHref = tarkovMapPageFollowHref({
    currentSlug: slug,
    logMapId: lastLogPhase?.mapId || lastLogMapId,
    phaseKind: lastLogPhase?.kind,
  });
  useEffect(() => {
    if (!followHref) return;
    const sig = `${followHref}:${lastLogPhase?.raidId || ""}:${lastLogPhase?.kind || "idle"}`;
    if (autoMapSigRef.current === sig) return;
    autoMapSigRef.current = sig;
    navigate(followHref);
    message.info(
      `已按游戏日志切换到${logMapLabel(lastLogPhase?.mapId || lastLogMapId)}`,
    );
  }, [
    followHref,
    lastLogMapId,
    lastLogPhase?.kind,
    lastLogPhase?.mapId,
    lastLogPhase?.raidId,
    navigate,
  ]);
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-map", gameMode, slug],
    queryFn: () => fetchTarkovMapDetail(slug),
    staleTime: 5 * 60_000,
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
        message="地图页加载失败"
        description={apiError(detailQuery.error, "地图页加载失败")}
      />
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  return (
    <TarkovMapDetailReady slug={slug} detail={detail} />
  );
}

function TarkovMapDetailReady({
  slug,
  detail,
}: {
  slug: string;
  detail: TarkovMapDetail;
}) {
  const [searchParams] = useSearchParams();
  const maintain = parseTarkovMaintainMode(searchParams.get("maintain"));
  const [floor, setFloor] = useState("");
  const editor = useTarkovMapPlaceEditor({
    slug,
    parentSlug: detail.parent_slug || undefined,
    places: detail.places || [],
    floor,
  });
  const variantHref = (id: string) =>
    maintain ? tarkovMapMaintainHref(id, maintain) : tarkovMapHref(id);
  const showPlaceEditor = Boolean(maintain);

  return (
    <div className={`${styles.stack} ${styles.stackFill}`}>
      {showPlaceEditor && editor.bar ? (
        <div className={styles.editBar}>
          {editor.bar}
        </div>
      ) : null}
      <div className={styles.mapSlot}>
        <Suspense fallback={<PanelFallback tip="加载地图…" />}>
          <TarkovMapViewer
            key={slug}
            slug={slug}
            fill
            {...tarkovMapViewerLayerProps(detail)}
            placeEdit={showPlaceEditor ? editor.placeEdit : undefined}
            onFloorChange={setFloor}
          />
        </Suspense>
      </div>
      {showPlaceEditor ? editor.modal : null}

      {detail.variants?.length ? (
        <div>
          <div className={styles.section}>地图变体</div>
          <div className={styles.variants}>
            <Link
              className={`${styles.variant} ${
                !detail.parent_slug ? styles.variantOn : ""
              }`}
              to={variantHref(detail.parent_slug || detail.slug)}
            >
              常规
            </Link>
            {detail.variants.map((row) => (
              <Link
                key={row.slug}
                className={`${styles.variant} ${
                  row.slug === detail.slug ? styles.variantOn : ""
                }`}
                to={variantHref(row.slug)}
              >
                {row.name || row.slug}
                {row.raid_duration ? ` · ${row.raid_duration} 分` : ""}
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
