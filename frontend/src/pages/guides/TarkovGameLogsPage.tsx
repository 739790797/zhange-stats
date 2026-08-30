import { Navigate } from "react-router-dom";
import { tarkovMeHref } from "@/lib/tarkovHomeNav";

export default function TarkovGameLogsPage() {
  return <Navigate to={tarkovMeHref("logs")} replace />;
}
