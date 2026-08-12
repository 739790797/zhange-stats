import {
  DEFAULT_GUN_CATEGORY,
  GUN_CATEGORIES,
  type GunCategoryId,
} from "@/lib/tarkovGunCategories";

const STORAGE_KEY = "zhange.guides.tarkov.gunFilters.v1";

export type TarkovGunFilterState = {
  category: GunCategoryId;
  selectedByCategory: Partial<Record<GunCategoryId, string[]>>;
};

const CATEGORY_IDS = new Set<GunCategoryId>(GUN_CATEGORIES.map((c) => c.id));

function isCategoryId(value: unknown): value is GunCategoryId {
  return typeof value === "string" && CATEGORY_IDS.has(value as GunCategoryId);
}

export function loadTarkovGunFilters(): TarkovGunFilterState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { category: DEFAULT_GUN_CATEGORY, selectedByCategory: {} };
    }
    const parsed = JSON.parse(raw) as Partial<TarkovGunFilterState>;
    const category = isCategoryId(parsed.category)
      ? parsed.category
      : DEFAULT_GUN_CATEGORY;
    const selectedByCategory: Partial<Record<GunCategoryId, string[]>> = {};
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
    return { category: DEFAULT_GUN_CATEGORY, selectedByCategory: {} };
  }
}

export function saveTarkovGunFilters(state: TarkovGunFilterState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}

export function resolveGunCategorySelection(
  category: GunCategoryId,
  available: string[],
  selectedByCategory: Partial<Record<GunCategoryId, string[]>>,
): string[] {
  const availableSet = new Set(available);
  const saved = selectedByCategory[category];
  if (!saved) return [...available];
  return saved.filter((c) => availableSet.has(c));
}
