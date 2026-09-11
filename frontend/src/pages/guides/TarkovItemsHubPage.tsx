import { Navigate, useSearchParams } from "react-router-dom";
import {
  ITEMS_DEFAULT_PATH,
  itemListingHref,
  itemPageBySlug,
  itemTypeHref,
  resolveItemTypeKey,
} from "@/lib/tarkovItemTypes";

/** 旧总览 / ?tab= 深链转到手册一级；叶子 tab 并进对应子类；默认进装备。 */
export default function TarkovItemsHubPage() {
  const [params] = useSearchParams();
  const tab = params.get("tab");
  const typeKey = resolveItemTypeKey(tab);
  const leaf = typeKey ? undefined : itemPageBySlug(tab);
  const next = new URLSearchParams(params);
  next.delete("tab");
  const qs = next.toString();
  const target = typeKey
    ? itemTypeHref(typeKey)
    : leaf
      ? itemListingHref(leaf.slug)
      : ITEMS_DEFAULT_PATH;
  return <Navigate to={`${target}${qs ? `?${qs}` : ""}`} replace />;
}
