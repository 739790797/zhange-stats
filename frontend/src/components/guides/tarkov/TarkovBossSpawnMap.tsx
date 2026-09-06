import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import type { TarkovBossDetail } from "@/api/guidesApi";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import { PanelFallback } from "@/components/RouteFallback";
import {
  bossSpawnOverlay,
  buildBossSpawnMapViews,
  heatmapMapParentSlug,
  heatmapSpawnLocationOptions,
  type BossSpawnMapView,
} from "@/lib/tarkovBossHeatmap";
import { tarkovMapMarkByName } from "@/lib/tarkovHomeNav";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import styles from "./TarkovBossPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

type Props = {
  detail: TarkovBossDetail;
};

function mapChipLabel(view: BossSpawnMapView): string {
  const mark =
    tarkovMapMarkByName(view.name) ||
    (view.slug ? tarkovMapMarkByName(view.slug) : null);
  return mark?.label || view.name || view.slug;
}

export function TarkovBossSpawnMap({ detail }: Props) {
  const views = useMemo(() => buildBossSpawnMapViews(detail), [detail]);
  const [mapSlug, setMapSlug] = useState("");
  const [focus, setFocus] = useState<TarkovMapFocusRequest | null>(null);
  const active = views.find((row) => row.slug === mapSlug) || views[0];
  const locations = active ? heatmapSpawnLocationOptions(active.points) : [];
  const overlay = useMemo(() => {
    if (!active) return null;
    return bossSpawnOverlay({
      id: detail.id,
      slug: detail.slug,
      name: detail.name,
      chancePct: active.chancePct,
      points: active.points,
    });
  }, [active, detail.id, detail.name, detail.slug]);

  useEffect(() => {
    if (!views.length) return;
    if (!views.some((row) => row.slug === mapSlug)) {
      setMapSlug(views[0].slug);
    }
  }, [views, mapSlug]);

  useEffect(() => {
    if (!active) return;
    const first = heatmapSpawnLocationOptions(active.points)[0];
    setFocus(
      first ? { x: first.x, y: first.y, z: first.z, seq: 1 } : null,
    );
    const timer = window.setTimeout(() => {
      window.dispatchEvent(new Event("resize"));
    }, 40);
    return () => window.clearTimeout(timer);
  }, [active]);

  if (!active || !overlay) return null;

  const activeName = focus
    ? locations.find((row) => row.x === focus.x && row.z === focus.z)?.name
    : locations[0]?.name;

  return (
    <div className={styles.spawnMap}>
      <span className={styles.sectionLabel}>刷点</span>
      {views.length > 1 ? (
        <div className={styles.spawnMapTabs} role="tablist" aria-label="刷点地图">
          {views.map((row) => {
            const mark =
              tarkovMapMarkByName(row.name) ||
              (row.slug ? tarkovMapMarkByName(row.slug) : null);
            const on = row.slug === active.slug;
            return (
              <button
                key={row.slug || row.name}
                type="button"
                role="tab"
                aria-selected={on}
                className={on ? styles.spawnMapTabOn : styles.spawnMapTab}
                onClick={() => setMapSlug(row.slug)}
              >
                {mark?.icon ? (
                  <svg
                    className={styles.mapIcon}
                    viewBox="0 0 24 24"
                    width={16}
                    height={16}
                    aria-hidden
                  >
                    <path d={mark.icon} fill="currentColor" />
                  </svg>
                ) : null}
                <span>{mapChipLabel(row)}</span>
                {row.chance ? (
                  <span className={styles.mapChance}>（{row.chance}）</span>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : (
        <div className={styles.spawnMapSolo}>
          {mapChipLabel(active)}
          {active.chance ? `（${active.chance}）` : ""}
        </div>
      )}
      {locations.length ? (
        <div className={styles.spawnLocs} role="list">
          {locations.map((row) => (
            <button
              key={`${row.name}-${row.x}-${row.z}`}
              type="button"
              className={
                row.name === activeName ? styles.spawnLocOn : styles.spawnLoc
              }
              onClick={() =>
                setFocus((prev) => ({
                  x: row.x,
                  y: row.y,
                  z: row.z,
                  seq: (prev?.seq || 0) + 1,
                }))
              }
            >
              {tarkovMapLabel(row.name, active.slug) || row.name}
            </button>
          ))}
        </div>
      ) : (
        <div className={styles.spawnMapEmpty}>这份数据没有坐标，仍可看底图</div>
      )}
      <div className={styles.spawnMapFrame}>
        <Suspense fallback={<PanelFallback tip="加载地图…" />}>
          <TarkovMapViewer
            key={active.slug}
            slug={active.slug}
            parentSlug={heatmapMapParentSlug(active.slug) || undefined}
            bosses={[overlay]}
            extracts={[]}
            spawns={[]}
            overlayMode="boss-spawns"
            layerChrome="floors"
            focusRequest={focus}
            suppressLocalFix
            fill
          />
        </Suspense>
      </div>
    </div>
  );
}
