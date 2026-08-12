import { Navigate, useSearchParams } from "react-router-dom";
import { TarkovItemTypeHub } from "@/components/guides/tarkov/TarkovItemTypeHub";
import {
  itemTypeHref,
  resolveItemTypeKey,
} from "@/lib/tarkovItemTypes";

/** 物品分类总览（Figma 战术目录）；兼容旧 ?tab= 深链。 */
export default function TarkovItemsHubPage() {
  const [params] = useSearchParams();
  const tab = params.get("tab");
  const typeKey = resolveItemTypeKey(tab);
  if (typeKey) {
    const next = new URLSearchParams(params);
    next.delete("tab");
    const qs = next.toString();
    return (
      <Navigate
        to={`${itemTypeHref(typeKey)}${qs ? `?${qs}` : ""}`}
        replace
      />
    );
  }

  return <TarkovItemTypeHub />;
}
