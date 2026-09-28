import { useMemo, useState } from "react";
import { sameGoonMap } from "@/lib/tarkovGoonTracker";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { colorForUserId, type RaidPrepMapOption } from "@/lib/tarkovRaidPrep";
import {
  groupRaidRoomMapPresence,
  type RaidRoomPresenceMember,
  type RaidRoomPresencePhase,
} from "@/lib/tarkovRaidRooms";
import { TarkovGoonSightingHint } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import { useTarkovGoonTracker } from "@/lib/useTarkovGoonTracker";
import styles from "./TarkovRaidRoomOverlapBoard.module.css";

type PhaseLike = {
  kind?: string | null;
  mapId?: string | null;
};

type Props = {
  members: readonly RaidRoomPresenceMember[];
  phaseByUser?: ReadonlyMap<number, PhaseLike>;
  mapOptions: readonly RaidPrepMapOption[];
  picking?: boolean;
  currentMapSlug?: string;
  onPickMap?: (mapSlug: string) => void;
};

function MapThumb({ slug, icon }: { slug: string; icon?: string }) {
  const [broken, setBroken] = useState(false);
  const src = tarkovMapThumbUrl(slug);
  if (!src || broken) {
    if (!icon) return null;
    return (
      <svg className={styles.thumbFallback} viewBox="0 0 24 24" aria-hidden>
        <path fill="currentColor" d={icon} />
      </svg>
    );
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

function personName(row: { display_name: string }): string {
  return (row.display_name || "").trim() || "成员";
}

function PersonChip({
  person,
  matching = false,
}: {
  person: RaidRoomPresenceMember;
  matching?: boolean;
}) {
  const name = personName(person);
  return (
    <span className={styles.chip} title={matching ? `${name} 匹配中` : name}>
      <span
        className={styles.dot}
        style={{ background: colorForUserId(person.user_id) }}
        aria-hidden
      />
      {person.is_host ? <span aria-hidden>⭐</span> : null}
      <span className={styles.chipName}>{name}</span>
      {matching ? <span className={styles.chipTag}>匹配中</span> : null}
    </span>
  );
}

export function TarkovRaidRoomOverlapBoard({
  members,
  phaseByUser,
  mapOptions,
  picking = false,
  currentMapSlug = "",
  onPickMap,
}: Props) {
  const labelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.label);
    return map;
  }, [mapOptions]);
  const iconById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.icon);
    return map;
  }, [mapOptions]);
  const grouped = useMemo(() => {
    const phases: RaidRoomPresencePhase[] = [];
    phaseByUser?.forEach((phase, userId) => {
      phases.push({
        userId,
        kind: phase?.kind,
        mapId: phase?.mapId,
      });
    });
    return groupRaidRoomMapPresence({
      members,
      phases,
      mapIds: mapOptions.map((item) => item.id),
    });
  }, [mapOptions, members, phaseByUser]);
  const { status: goonStatus } = useTarkovGoonTracker();
  const goonMapSlug = goonStatus?.map_slug || "";

  return (
    <div className={styles.board}>
      {grouped.lobby.length ? (
        <div className={styles.band}>
          <span className={styles.bandLabel}>大厅中：</span>
          <div className={styles.chips}>
            {grouped.lobby.map((person) => (
              <PersonChip key={person.user_id} person={person} />
            ))}
          </div>
        </div>
      ) : null}
      {grouped.matching.length ? (
        <div className={styles.band}>
          <span className={styles.bandLabel}>匹配中：</span>
          <div className={styles.chips}>
            {grouped.matching.map((person) => (
              <PersonChip key={person.user_id} person={person} />
            ))}
          </div>
        </div>
      ) : null}
      <p className={styles.sectionLabel}>战局中：</p>
      <div className={styles.grid}>
        {grouped.maps.map((row) => {
          const label = labelById.get(row.mapId) || row.mapId;
          const current = Boolean(
            currentMapSlug && row.mapId === currentMapSlug,
          );
          const goon = sameGoonMap(row.mapId, goonMapSlug);
          return (
            <div key={row.mapId} className={styles.cell}>
              <button
                type="button"
                className={`${styles.card}${current ? ` ${styles.cardCurrent}` : ""}${
                  goon ? ` ${styles.cardGoon}` : ""
                }`}
                disabled={!onPickMap || picking}
                aria-pressed={current}
                aria-label={current ? `继续看${label}` : `切换到${label}`}
                onClick={() => onPickMap?.(row.mapId)}
              >
                <MapThumb slug={row.mapId} icon={iconById.get(row.mapId)} />
                <span className={styles.cardBody}>
                  <span className={styles.mapName}>{label}</span>
                  <TarkovGoonSightingHint mapId={row.mapId} variant="tile" />
                </span>
              </button>
              {row.people.length ? (
                <div className={styles.chips}>
                  {row.people.map((person) => (
                    <PersonChip
                      key={person.user_id}
                      person={person}
                      matching={person.seat === "matching"}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
