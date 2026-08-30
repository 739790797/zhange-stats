import { Navigate, useSearchParams } from "react-router-dom";
import { TARKOV_ME_PATH } from "@/lib/tarkovHomeNav";

export default function TarkovKeyPacksPage() {
  const [params] = useSearchParams();
  const next = new URLSearchParams(params);
  next.set("tab", "keys");
  return <Navigate to={`${TARKOV_ME_PATH}?${next.toString()}`} replace />;
}
