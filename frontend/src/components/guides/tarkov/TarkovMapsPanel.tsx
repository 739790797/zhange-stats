import { useState } from "react";
import { Alert, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMaps } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_MAPS,
  tarkovMapHref,
  tarkovMapSlug,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import styles from "./TarkovMapsPanel.module.css";

function MapThumb({
  slug,
  apiThumb,
  icon,
}: {
  slug: string;
  apiThumb?: string;
  icon?: string;
}) {
  const [broken, setBroken] = useState(false);
  const src = tarkovMapThumbUrl(slug, apiThumb);
  if (!src || broken) {
    return icon ? (
      <svg
        className={styles.thumbFallback}
        viewBox="0 0 24 24"
        aria-hidden
      >
        <path fill="currentColor" d={icon} />
      </svg>
    ) : null;
  }
  return (
    <img
      className={styles.thumb}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
    />
  );
}

export function TarkovMapsPanel() {
  const gameMode = useTarkovGameMode();
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-maps", gameMode],
    queryFn: fetchTarkovMaps,
    staleTime: 5 * 60_000,
    retry: 1,
  });

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
        message="地图列表加载失败"
        description={apiError(catalogQuery.error, "地图列表加载失败")}
      />
    );
  }

  const apiItems = catalogQuery.data?.items ?? [];
  const cards = TARKOV_MAPS.map((home) => {
    const slug = tarkovMapSlug(home.id);
    const api = apiItems.find(
      (row) => row.slug === slug || row.slug === home.id,
    );
    return { home, api, slug };
  });
  const extras = apiItems.filter(
    (row) =>
      !TARKOV_MAPS.some(
        (home) =>
          home.id === row.slug || tarkovMapSlug(home.id) === row.slug,
      ),
  );

  return (
    <div className={styles.grid}>
      {cards.map(({ home, api, slug }) => {
        const soon = home.status === "soon" || Boolean(home.comingSoon);
        const body = (
          <>
            <div className={styles.thumbWrap}>
              {soon ? null : (
                <MapThumb
                  slug={slug}
                  apiThumb={api?.thumb_link}
                  icon={home.icon}
                />
              )}
            </div>
            <div className={styles.body}>
              <span className={styles.name}>{api?.name || home.label}</span>
              <span className={styles.english}>{home.english}</span>
              <span className={styles.meta}>
                {soon
                  ? "即将推出"
                  : [
                      api?.raid_duration
                        ? `${api.raid_duration} 分钟`
                        : null,
                      api?.players ? `${api.players} 人` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "突袭地图"}
              </span>
            </div>
          </>
        );
        if (soon) {
          return (
            <span key={home.id} className={`${styles.card} ${styles.soon}`}>
              {body}
            </span>
          );
        }
        return (
          <Link key={home.id} to={tarkovMapHref(home.id)} className={styles.card}>
            {body}
          </Link>
        );
      })}
      {extras.map((row) => (
        <Link
          key={row.slug}
          to={tarkovMapHref(row.slug)}
          className={styles.card}
        >
          <div className={styles.thumbWrap}>
            <MapThumb slug={row.slug} apiThumb={row.thumb_link} />
          </div>
          <div className={styles.body}>
            <span className={styles.name}>{row.name}</span>
            <span className={styles.english}>{row.english}</span>
            <span className={styles.meta}>
              {[
                row.raid_duration ? `${row.raid_duration} 分钟` : null,
                row.players ? `${row.players} 人` : null,
              ]
                .filter(Boolean)
                .join(" · ") || "突袭地图"}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
