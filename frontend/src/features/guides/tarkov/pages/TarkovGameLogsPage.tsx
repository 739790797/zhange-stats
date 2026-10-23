import { Navigate } from "react-router-dom";
import { tarkovMeHref } from "@/features/guides/tarkov/model/tarkovHomeNav";

export default function TarkovGameLogsPage() {
  return <Navigate to={tarkovMeHref("logs")} replace />;
}
