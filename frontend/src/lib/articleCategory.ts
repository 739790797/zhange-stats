export const DEFAULT_ARTICLE_CATEGORY_CHIP = "processing";

export function articleCategoryChipHex(
  cat: { chip_color?: string | null } | null | undefined,
): string | undefined {
  const raw = cat?.chip_color?.trim();
  return raw || undefined;
}

export function articleCategoryChipColor(
  cat: { chip_color?: string | null } | null | undefined,
): string {
  return articleCategoryChipHex(cat) || DEFAULT_ARTICLE_CATEGORY_CHIP;
}

export function selectableArticleCategories<
  T extends { admin_only?: boolean },
>(cats: T[], canAdmin: boolean): T[] {
  if (canAdmin) return cats;
  return cats.filter((cat) => !cat.admin_only);
}

export function articleCategoryOptionLabel(cat: {
  name: string;
  admin_only?: boolean;
}): string {
  return cat.admin_only ? `${cat.name}（仅管理员）` : cat.name;
}
