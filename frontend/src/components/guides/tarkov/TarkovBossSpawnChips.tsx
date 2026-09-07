import { Link } from "react-router-dom";
import {
  tarkovBossHref,
  tarkovMapHref,
  tarkovMapMarkByName,
} from "@/lib/tarkovHomeNav";
import { lookupEscortPortrait } from "@/lib/tarkovBossHeatmap";
import {
  escortQtyLabel,
  isSameMobCountVariants,
  locationChipLabel,
  type BossSpawnEscortChip,
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
  if (!group.maps.length) return <span className={styles.spawnEmpty}>—</span>;
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
  if (!group.locations.length) return <span className={styles.spawnEmpty}>—</span>;
  return (
    <span className={styles.locList}>
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

function escortHref(slug: string | undefined): string {
  const key = (slug || "").trim();
  return key ? tarkovBossHref(key) : "";
}

function EscortPerson({
  row,
  portraits,
  combo,
}: {
  row: BossSpawnEscortChip;
  portraits?: ReadonlyMap<string, string>;
  combo?: number;
}) {
  const href = escortHref(row.slug);
  const portrait = portraits ? lookupEscortPortrait(row, portraits) : "";
  const name = (row.name || row.slug || "随从").trim() || "随从";
  const qty = escortQtyLabel(row);
  const title = `查看 ${name}`;
  const body = (
    <>
      {portrait ? (
        <img
          className={styles.escortAvatar}
          src={portrait}
          alt=""
          width={32}
          height={32}
        />
      ) : (
        <span className={styles.escortAvatar} />
      )}
      <span className={styles.escortName}>
        {combo ? <span className={styles.escortCombo}>组合{combo} </span> : null}
        {name}
      </span>
      {qty ? <span className={styles.escortQty}>{qty}</span> : null}
    </>
  );
  if (!href) {
    return <span className={styles.escortPerson}>{body}</span>;
  }
  return (
    <Link to={href} className={styles.escortPerson} title={title}>
      {body}
    </Link>
  );
}

export function TarkovBossEscortChips({
  group,
  portraits,
}: {
  group: BossSpawnGroup;
  portraits?: ReadonlyMap<string, string>;
}) {
  if (!group.escorts.length) return <span className={styles.spawnEmpty}>—</span>;
  const variants = isSameMobCountVariants(group.escorts);
  return (
    <div className={styles.escortList}>
      {group.escorts.map((row, index) => (
        <EscortPerson
          key={`${row.slug}-${row.count}-${index}`}
          row={row}
          portraits={portraits}
          combo={variants ? index + 1 : undefined}
        />
      ))}
    </div>
  );
}
