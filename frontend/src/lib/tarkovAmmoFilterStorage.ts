const STORAGE_KEY = "zhange.guides.tarkov.ammoFilters.v2";

export type TarkovAmmoFilterState = {
  /** 勾选的口径；`null` = 从未保存（默认全选） */
  selectedCalibers: string[] | null;
};

export function loadTarkovAmmoFilters(): TarkovAmmoFilterState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { selectedCalibers: null };
    const parsed = JSON.parse(raw) as Partial<TarkovAmmoFilterState>;
    if (!Array.isArray(parsed.selectedCalibers)) {
      return { selectedCalibers: null };
    }
    return {
      selectedCalibers: parsed.selectedCalibers.filter(
        (v): v is string => typeof v === "string" && v.trim().length > 0,
      ),
    };
  } catch {
    return { selectedCalibers: null };
  }
}

export function saveTarkovAmmoFilters(state: TarkovAmmoFilterState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota / private mode */
  }
}

/** 用当前可选口径校正历史勾选；`null` 默认全选；允许空数组（用户清空） */
export function resolveCaliberSelection(
  available: string[],
  saved: string[] | null,
): string[] {
  if (saved === null) return [...available];
  const availableSet = new Set(available);
  return saved.filter((c) => availableSet.has(c));
}
