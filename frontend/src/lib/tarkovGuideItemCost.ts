export type TarkovGuideItemRef = {
  id: string;
  name?: string;
  short_name?: string;
  icon_link?: string;
  types?: string[] | null;
  count?: number;
  found_in_raid?: boolean;
  flea_price?: number | null;
  badge?: string;
};

export function guideItemFleaCost(
  items: TarkovGuideItemRef[] | undefined,
): number | null {
  if (!items?.length) return 0;
  let sum = 0;
  for (const item of items) {
    const price = item.flea_price;
    if (price == null || !Number.isFinite(price) || price <= 0) return null;
    sum += price * Number(item.count || 1);
  }
  return sum;
}
