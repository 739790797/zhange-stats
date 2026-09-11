import { Navigate, useParams } from "react-router-dom";
import { tarkovHideoutHref } from "@/lib/tarkovHomeNav";

export default function TarkovHideoutDetailPage() {
  const { stationSlug = "" } = useParams<{ stationSlug: string }>();
  return <Navigate to={tarkovHideoutHref(stationSlug)} replace />;
}
