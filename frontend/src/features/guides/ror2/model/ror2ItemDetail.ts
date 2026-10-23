import type { Ror2Item } from "@/features/guides/ror2/api/ror2Api";
import { ROR2_ITEMS_PATH, ror2ItemRarityIsActive } from "./ror2Home";

export type Ror2ItemDetailKind = "item" | "equipment";

type Ror2ItemRouteIdentity = Pick<Ror2Item, "name" | "internal_name" | "code" | "rarity">;

export function ror2ItemDetailKind(item: Pick<Ror2ItemRouteIdentity, "rarity">): Ror2ItemDetailKind {
  return ror2ItemRarityIsActive(item.rarity) ? "equipment" : "item";
}

export function ror2ItemRouteId(item: Pick<Ror2ItemRouteIdentity, "name" | "internal_name" | "code">): string {
  return item.internal_name?.trim() || item.code?.trim() || item.name.trim();
}

export function ror2ItemDetailHref(item: Ror2ItemRouteIdentity, search = ""): string {
  const suffix = search ? (search.startsWith("?") ? search : `?${search}`) : "";
  return `${ROR2_ITEMS_PATH}/${ror2ItemDetailKind(item)}/${encodeURIComponent(ror2ItemRouteId(item))}${suffix}`;
}
