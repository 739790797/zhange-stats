import { Navigate } from "react-router-dom";
import { TAVERN_PATH } from "@/lib/tavernNav";

/** 站点首页落到战鸽酒馆（未登录也可读）。 */
export function HomeRedirect() {
  return <Navigate to={TAVERN_PATH} replace />;
}
