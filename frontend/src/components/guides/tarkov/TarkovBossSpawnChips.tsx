import { Link } from "react-router-dom";
import {
  tarkovBossHref,
  tarkovMapHref,
  tarkovMapMarkByName,
} from "@/lib/tarkovHomeNav";
import {
  escortChipLabel,
  isSameMobCountVariants,
  locationChipLabel,
  type BossSpawnGroup,
  type BossSpawnMapChip,
} from "@/lib/tarkovBossSpawnGroups";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import styles from "./TarkovBossPanel.module.css";

function formatChance(chance: number | undefined): string {
  if (chance == null || !Number.isFinite(chance)) return "—";
  return `${Math.round(chance * 100)}%`;
}

export function TarkovBossMapChip({
  row,
  chance,
}: {
  row: BossSpawnMapChip;
  chance?: string;
}) {
  const mark =
    tarkovMapMarkByName(row.name) ||
    (row.slug ? tarkovMapMarkByName(row.slug) : null);
  const label = mark?.label || row.name || row.slug;
  const href = row.slug
    ? tarkovMapHref(row.slug)
    : mark?.id
      ? tarkovMapHref(mark.id)
      : "";
  const inner = (
    <span className={styles.mapChip}>
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
      <span>{label}</span>
      {chance ? (
        <span className={styles.mapChance}>（{chance}）</span>
      ) : null}
    </span>
  );
  if (!href) return inner;
  return (
    <Link to={href} className={styles.mapChipLink}>
      {inner}
    </Link>
  );
}

export function TarkovBossMapChips({ group }: { group: BossSpawnGroup }) {
  if (!group.maps.length) return <span>—</span>;
  return (
    <span className={styles.spawnMaps}>
      {group.maps.map((row) => (
        <TarkovBossMapChip
          key={row.slug || row.name}
          row={row}
          chance={row.spawnChance || group.sharedSpawnChance || undefined}
        />
      ))}
    </span>
  );
}

export function TarkovBossLocationChips({ group }: { group: BossSpawnGroup }) {
  if (!group.locations.length) return <span>—</span>;
  return (
    <span className={styles.spawnRowBody}>
      {group.locations.map((row, index) => (
        <span
          key={`${row.mapSlug}-${row.name}-${index}`}
          className={styles.locChip}
        >
          {locationChipLabel(row, group, tarkovMapLabel)}
          {group.showLocationChance ? ` ${formatChance(row.chance)}` : ""}
        </span>
      ))}
    </span>
  );
}

export function TarkovBossEscortChips({ group }: { group: BossSpawnGroup }) {
  if (!group.escorts.length) return <span>—</span>;
  if (isSameMobCountVariants(group.escorts)) {
    return (
      <span className={styles.schemeList}>
        {group.escorts.map((row, index) => (
          <span key={`${row.slug}-${row.count}-${index}`} className={styles.schemeLine}>
            组合{index + 1}：{escortChipLabel(row)}
          </span>
        ))}
      </span>
    );
  }
  return (
    <span className={styles.spawnRowBody}>
      {group.escorts.map((row, index) => {
        const label = escortChipLabel(row);
        const href = row.slug ? tarkovBossHref(row.slug) : "";
        const chip = <span className={styles.escortChip}>{label}</span>;
        return href ? (
          <Link
            key={`${row.slug}-${row.count}-${index}`}
            to={href}
            className={styles.mapChipLink}
          >
            {chip}
          </Link>
        ) : (
          <span key={`${row.name}-${row.count}-${index}`}>{chip}</span>
        );
      })}
    </span>
  );
}
