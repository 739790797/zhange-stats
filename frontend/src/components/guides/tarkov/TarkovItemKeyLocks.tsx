import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TarkovItemDetail } from "@/api/guidesApi";
import { tarkovMapHref } from "@/lib/tarkovHomeNav";
import {
  itemKeyLockMaps,
  itemKeyLocksAsMapLocks,
  lockFocusPoint,
  lockOverlayFloor,
  lockPointLabel,
  lockTypeSummary,
  type TarkovItemKeyLock,
} from "@/lib/tarkovItemLocks";
import { findInteractiveMap, floorLabel } from "@/lib/tarkovMapImages";
import { tarkovLockIconUrl, tarkovMarkerHeightSpan } from "@/lib/tarkovMapMarkers";
import { mapLayerFloorBands } from "@/lib/tarkovRaidPrep";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import { PanelFallback } from "@/components/RouteFallback";
import styles from "./TarkovItemKeyLocks.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

type Props = {
  detail: TarkovItemDetail;
};

function lockFloorCaption(
  lock: TarkovItemKeyLock,
  bands: ReturnType<typeof mapLayerFloorBands>,
): string {
  if (!bands.length || !tarkovMarkerHeightSpan(lock)) return "";
  return floorLabel(lockOverlayFloor(lock, bands)) || "地面";
}

export function TarkovItemKeyLocks({ detail }: Props) {
  const maps = useMemo(() => itemKeyLockMaps(detail), [detail]);
  const [slug, setSlug] = useState(maps[0]?.slug || "");
  const [focus, setFocus] = useState<TarkovMapFocusRequest | null>(null);
  const selected = maps.find((row) => row.slug === slug) ?? maps[0];
  const floorBands = useMemo(
    () =>
      mapLayerFloorBands(
        findInteractiveMap(
          selected?.slug || "",
          selected?.parent_slug || undefined,
        ),
      ),
    [selected?.slug, selected?.parent_slug],
  );

  const firstLock = (selected?.locks || []).find(
    (lock) => lock.x != null && lock.z != null,
  );

  useEffect(() => {
    const point = firstLock ? lockFocusPoint(firstLock) : null;
    if (!point) {
      setFocus(null);
      return;
    }
    setFocus((prev) => ({ ...point, seq: (prev?.seq || 0) + 1 }));
  }, [firstLock, selected?.slug]);

  if (!selected) return null;

  const locks = selected.locks || [];
  const summary = lockTypeSummary(locks);
  const viewerLocks = itemKeyLocksAsMapLocks(selected, detail.id, detail.name);

  const focusLock = (lock: TarkovItemKeyLock) => {
    const point = lockFocusPoint(lock);
    if (!point) return;
    setFocus((prev) => ({ ...point, seq: (prev?.seq || 0) + 1 }));
  };

  return (
    <section className={styles.wrap}>
      <div className={styles.head}>
        <h2 className={styles.title}>能开的锁</h2>
        <Link className={styles.mapLink} to={tarkovMapHref(selected.slug)}>
          打开{selected.name}地图
        </Link>
      </div>
      {maps.length > 1 ? (
        <div className={styles.tabs} role="tablist" aria-label="地图">
          {maps.map((row) => {
            const on = row.slug === selected.slug;
            return (
              <button
                key={row.slug}
                type="button"
                role="tab"
                aria-selected={on}
                className={`${styles.tab} ${on ? styles.tabOn : ""}`}
                onClick={() => setSlug(row.slug)}
              >
                {row.name}
                <span className={styles.tabCount}>{(row.locks || []).length}</span>
              </button>
            );
          })}
        </div>
      ) : null}
      <div className={styles.meta}>
        <span>
          {selected.name}
          {summary ? ` · ${summary}` : ""}
        </span>
      </div>
      {locks.length ? (
        <div className={styles.points} role="list">
          {locks.map((lock, index) => {
            const x = lock.x;
            const z = lock.z;
            if (x == null || z == null) return null;
            const on = focus != null && focus.x === x && focus.z === z;
            return (
              <button
                key={lock.id || `${x}-${z}-${index}`}
                type="button"
                className={`${styles.point} ${on ? styles.pointOn : ""}`}
                onClick={() => focusLock(lock)}
              >
                <img
                  className={styles.pointIcon}
                  src={tarkovLockIconUrl()}
                  alt=""
                  width={16}
                  height={16}
                />
                {lockPointLabel(
                  lock,
                  index,
                  locks,
                  lockFloorCaption(lock, floorBands),
                )}
              </button>
            );
          })}
        </div>
      ) : null}
      <div className={styles.map}>
        <Suspense fallback={<PanelFallback tip="加载地图…" />}>
          <TarkovMapViewer
            slug={selected.slug}
            parentSlug={selected.parent_slug || undefined}
            extracts={[]}
            bosses={[]}
            spawns={[]}
            locks={viewerLocks}
            overlayMode="locks"
            layerChrome="floors"
            focusRequest={focus}
            suppressLocalFix
            fill
          />
        </Suspense>
      </div>
    </section>
  );
}
