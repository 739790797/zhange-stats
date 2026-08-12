import {
  AMMO_CATEGORIES,
  DEFAULT_AMMO_CATEGORY,
  type AmmoCategoryId,
} from "@/lib/tarkovAmmoCategories";

const STORAGE_KEY = "zhange.guides.tarkov.ammoFilters.v1";

export type TarkovAmmoFilterState = {
  category: AmmoCategoryId;
  /** 各大类下勾选的口径（原始 caliber 字符串） */
  selectedByCategory: Partial<Record<AmmoCategoryId, string[]>>;
};

const CATEGORY_IDS = new Set<AmmoCategoryId>(
  AMMO_CATEGORIES.map((c) => c.id),
);

function isCategoryId(value: unknown): value is AmmoCategoryId {
  return typeof value === "string" && CATEGORY_IDS.has(value as AmmoCategoryId);
}

export function loadTarkovAmmoFilters(): TarkovAmmoFilterState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { category: DEFAULT_AMMO_CATEGORY, selectedByCategory: {} };
    }
    const parsed = JSON.parse(raw) as Partial<TarkovAmmoFilterState>;
    const category = isCategoryId(parsed.category)
      ? parsed.category
      : DEFAULT_AMMO_CATEGORY;
    const selectedByCategory: Partial<Record<AmmoCategoryId, string[]>> = {};
    const src = parsed.selectedByCategory;
    if (src && typeof src === "object") {
      for (const id of CATEGORY_IDS) {
        const list = src[id];
        if (!Array.isArray(list)) continue;
        selectedByCategory[id] = list.filter(
          (v): v is string => typeof v === "string" && v.trim().length > 0,
        );
      }
    }
    return { category, selectedByCategory };
  } catch {
    return { category: DEFAULT_AMMO_CATEGORY, selectedByCategory: {} };
  }
}

export function saveTarkovAmmoFilters(state: TarkovAmmoFilterState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota / private mode */
  }
}

/** 用当前可选口径校正历史勾选；无历史则默认全选该类 */
export function resolveCategorySelection(
  category: AmmoCategoryId,
  available: string[],
  selectedByCategory: Partial<Record<AmmoCategoryId, string[]>>,
): string[] {
  const availableSet = new Set(available);
  const saved = selectedByCategory[category];
  if (!saved) return [...available];
  return saved.filter((c) => availableSet.has(c));
}
