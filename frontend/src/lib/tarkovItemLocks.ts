import type { TarkovItemDetail, TarkovMapLock } from "@/api/guidesApi";
import { lockTypeLabel } from "@/lib/tarkovKeyPacks";

export type TarkovItemKeyLockMap = NonNullable<TarkovItemDetail["locks"]>[number];
export type TarkovItemKeyLock = NonNullable<TarkovItemKeyLockMap["locks"]>[number];

export function itemKeyLockMaps(
  detail: TarkovItemDetail | null | undefined,
): TarkovItemKeyLockMap[] {
  return (detail?.locks || []).filter(
    (row) => row.slug && (row.locks || []).some((lock) => lock.x != null && lock.z != null),
  );
}

export function lockTypeSummary(locks: readonly TarkovItemKeyLock[]): string {
  const counts = new Map<string, number>();
  for (const lock of locks) {
    const label = lockTypeLabel(lock.lock_type) || "锁";
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => `${count} 处${label}`)
    .join(" · ");
}

export function lockPointLabel(
  lock: TarkovItemKeyLock,
  index: number,
  locks: readonly TarkovItemKeyLock[],
): string {
  const type = lockTypeLabel(lock.lock_type) || "锁";
  const same = locks.filter((row) => (row.lock_type || "") === (lock.lock_type || ""));
  const ordinal = same.findIndex((row) => row === lock);
  const name = same.length > 1 ? `${type} ${ordinal >= 0 ? ordinal + 1 : index + 1}` : type;
  return lock.needs_power ? `${name} · 需供电` : name;
}

export function itemKeyLocksAsMapLocks(
  map: TarkovItemKeyLockMap,
  keyId: string,
  keyName = "",
): TarkovMapLock[] {
  return (map.locks || []).flatMap((lock, index) => {
    if (lock.x == null || lock.z == null) return [];
    return [
      {
        id: lock.id || `lock:${map.slug}:${index}`,
        lock_type: lock.lock_type || "",
        needs_power: Boolean(lock.needs_power),
        key_id: keyId,
        key_name: keyName,
        key_short_name: "",
        key_icon: "",
        x: lock.x,
        y: lock.y ?? undefined,
        z: lock.z,
        top: lock.top ?? undefined,
        bottom: lock.bottom ?? undefined,
      },
    ];
  });
}
