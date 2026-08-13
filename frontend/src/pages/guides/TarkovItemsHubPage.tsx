import { Navigate, useSearchParams } from "react-router-dom";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import { itemTypeHref, resolveItemTypeKey } from "@/lib/tarkovItemTypes";

/** 分类总览已撤；旧 /items 与 ?tab= 深链转到首页或对应分类。 */
export default function TarkovItemsHubPage() {
  const [params] = useSearchParams();
  const typeKey = resolveItemTypeKey(params.get("tab"));
  if (typeKey) {
    const next = new URLSearchParams(params);
    next.delete("tab");
    const qs = next.toString();
    return (
      <Navigate to={`${itemTypeHref(typeKey)}${qs ? `?${qs}` : ""}`} replace />
    );
  }
  return <Navigate to={TARKOV_HOME_PATH} replace />;
}
