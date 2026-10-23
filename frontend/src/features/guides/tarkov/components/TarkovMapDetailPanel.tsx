import { Alert, Spin, message } from "antd";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMapDetail, type TarkovMapDetail } from "@/features/guides/tarkov/api/guidesApi";
import { useTarkovMapPlaceEditor } from "@/features/guides/tarkov/components/TarkovMapPlaceEditor";
import { apiError } from "@/shared/api/apiError";
import { useTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import { useTarkovDocumentTitle } from "@/features/guides/tarkov/model/tarkovDocumentTitle";
import {
  parseTarkovMaintainMode,
  tarkovMapHref,
  tarkovMapMaintainHref,
} from "@/features/guides/tarkov/model/tarkovHomeNav";
import { logMapLabel } from "@/features/guides/tarkov/model/tarkovGameLogs";
import { tarkovMapPageFollowHref } from "@/features/guides/tarkov/model/tarkovRaidPrep";
import {
  useTarkovLastLogMapId,
  useTarkovLastLogPhase,
} from "@/features/guides/tarkov/hooks/useTarkovLiveWatch";
import { tarkovMapViewerLayerProps } from "@/features/guides/tarkov/model/tarkovMapViewerDetail";
import { isAdminUser } from "@/features/auth/model/isAdminUser";
import { useAuthStore } from "@/features/auth/model/authStore";
import { PanelFallback } from "@/shared/ui/PanelFallback";
import { TarkovDataFreshness } from "@/features/guides/tarkov/components/TarkovDataFreshness";
import styles from "./TarkovMapsPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/features/guides/tarkov/components/TarkovMapViewer").then((m) => ({
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
  const isAdmin = isAdminUser(useAuthStore((s) => s.user));
  const [floor, setFloor] = useState("");
  const editor = useTarkovMapPlaceEditor({
    slug,
    parentSlug: detail.parent_slug || undefined,
    places: detail.places || [],
    floor,
  });
  const variantHref = (id: string) =>
    maintain ? tarkovMapMaintainHref(id, maintain) : tarkovMapHref(id);
  const showPlaceEditor = Boolean(maintain) && isAdmin;

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

      <TarkovDataFreshness
        source={detail.source}
        syncedAt={detail.synced_at}
        note={detail.note}
      />
    </div>
  );
}
