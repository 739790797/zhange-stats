import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type {
  TarkovBossGearItem,
  TarkovBossGearSlot,
} from "@/api/guidesApi";
import {
  ARMOR_EFFECT_COLORS,
  ARMOR_EFFECT_LABELS,
  armorEffectsForAmmo,
} from "@/lib/tarkovAmmoArmorEffect";
import {
  bossGearAmmoStats,
  bossGearItemLabel,
  groupBossGearSlots,
  splitBossGearContains,
} from "@/lib/tarkovBossEquipment";
import { inventoryThumbUrl } from "@/lib/tarkovItemImages";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import panel from "./TarkovBossPanel.module.css";
import styles from "./TarkovBossEquipment.module.css";

type GearContained = NonNullable<TarkovBossGearItem["contains"]>[number];

function thumbOf(item: { icon_link?: string; item_id: string }): string {
  return inventoryThumbUrl(item.icon_link, item.item_id) || item.icon_link || "";
}

function formatStat(value: number | null): string {
  return value == null ? "—" : String(value);
}

function GearCard({ item }: { item: TarkovBossGearItem }) {
  const text = bossGearItemLabel(item);
  const thumb = thumbOf(item);
  const nested = item.contains || [];
  const stowed = splitBossGearContains(nested);
  const hasStow =
    stowed.magazines.length > 0 ||
    stowed.ammo.length > 0 ||
    stowed.plates.length > 0;
  return (
    <article className={styles.card}>
      <Link
        className={styles.main}
        to={itemHrefFromTypes(item.item_id, item.types)}
        title={text}
      >
        <span className={styles.icon}>
          {thumb ? <img src={thumb} alt="" /> : null}
        </span>
        <span className={styles.name}>{text}</span>
      </Link>
      {hasStow ? (
        <div className={styles.stow}>
          {stowed.magazines.length ? (
            <StowBlock label="弹匣">
              {stowed.magazines.map((child) => (
                <StowItem key={child.item_id} item={child} />
              ))}
            </StowBlock>
          ) : null}
          {stowed.ammo.length ? (
            <StowBlock label="子弹">
              {stowed.ammo.map((child) => (
                <AmmoRow key={child.item_id} item={child} />
              ))}
            </StowBlock>
          ) : null}
          {stowed.plates.length ? (
            <StowBlock label="插板">
              {stowed.plates.map((child) => (
                <StowItem key={child.item_id} item={child} />
              ))}
            </StowBlock>
          ) : null}
          {stowed.other.length ? (
            <div className={styles.otherChips}>
              {stowed.other.map((child) => (
                <StowItem key={child.item_id} item={child} />
              ))}
            </div>
          ) : null}
        </div>
      ) : nested.length ? (
        <div className={styles.contains}>
          {nested.map((child) => (
            <StowItem key={child.item_id} item={child} />
          ))}
        </div>
      ) : null}
    </article>
  );
}

function StowBlock({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.stowBlock}>
      <div className={styles.stowLabel}>{label}</div>
      <div className={styles.stowBody}>{children}</div>
    </div>
  );
}

function StowItem({ item }: { item: GearContained }) {
  const text = bossGearItemLabel(item, true);
  const thumb = thumbOf(item);
  const href = itemHrefFromTypes(item.item_id, item.types);
  const title = bossGearItemLabel(item);
  return (
    <div className={styles.stowItem}>
      <Link className={styles.stowIcon} to={href} title={title}>
        {thumb ? <img src={thumb} alt="" /> : null}
      </Link>
      <Link className={styles.stowName} to={href} title={title}>
        {text}
      </Link>
    </div>
  );
}

function AmmoRow({ item }: { item: GearContained }) {
  const text = bossGearItemLabel(item, true);
  const thumb = thumbOf(item);
  const href = itemHrefFromTypes(item.item_id, item.types);
  const title = bossGearItemLabel(item);
  const stats = bossGearAmmoStats(item);
  const showStats = stats.damage != null || stats.penetration != null;
  const showEffects = stats.penetration != null && stats.armorDamage != null;
  return (
    <div className={styles.ammoRow}>
      <Link className={styles.stowIcon} to={href} title={title}>
        {thumb ? <img src={thumb} alt="" /> : null}
      </Link>
      <Link className={styles.stowName} to={href} title={title}>
        {text}
      </Link>
      <div className={styles.ammoStats}>
        {showStats ? (
          <>
            <span>伤害</span>
            <b>{formatStat(stats.damage)}</b>
            <span>穿透</span>
            <b>{formatStat(stats.penetration)}</b>
          </>
        ) : null}
      </div>
      {showEffects ? (
        <AmmoArmorStrip
          penetration={stats.penetration ?? 0}
          armorDamage={stats.armorDamage ?? 0}
        />
      ) : (
        <span />
      )}
    </div>
  );
}

function AmmoArmorStrip({
  penetration,
  armorDamage,
}: {
  penetration: number;
  armorDamage: number;
}) {
  const effects = armorEffectsForAmmo(penetration, armorDamage);
  return (
    <div className={styles.effects} aria-label="对护甲效果">
      {effects.map((level, index) => {
        const { bg, fg } = ARMOR_EFFECT_COLORS[level];
        return (
          <div
            key={index}
            className={styles.effect}
            style={{ background: bg, color: fg }}
            title={`${index + 1}级 ${ARMOR_EFFECT_LABELS[level]}`}
          >
            <span className={styles.effectClass}>{index + 1}级</span>
            <span className={styles.effectLabel}>
              {ARMOR_EFFECT_LABELS[level]}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function slotGridClass(key: string | undefined): string {
  return key === "gun" || key === "pistol" ? styles.gridArmed : styles.grid;
}

export function TarkovBossEquipment({
  slots,
}: {
  slots: TarkovBossGearSlot[];
}) {
  const groups = groupBossGearSlots(slots);
  if (!groups.length) return null;
  return (
    <section className={panel.section}>
      <div className={panel.lootHead}>
        <span className={panel.diamond} aria-hidden>
          ◆
        </span>
        配装
      </div>
      <div className={styles.groups}>
        {groups.map((group) => (
          <div key={group.id}>
            <h3 className={styles.groupHead}>{group.label}</h3>
            {group.slots.map((slot) => {
              const items = slot.items || [];
              return (
                <div key={slot.key || slot.label} className={styles.slot}>
                  <div className={styles.slotMeta}>
                    <div className={styles.slotLabel}>{slot.label}</div>
                    <span className={styles.slotCount}>{items.length} 件</span>
                  </div>
                  <div className={slotGridClass(slot.key)}>
                    {items.map((item) => (
                      <GearCard key={item.item_id} item={item} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}
