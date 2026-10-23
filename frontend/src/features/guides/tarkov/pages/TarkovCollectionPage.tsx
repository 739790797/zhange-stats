import { Navigate } from "react-router-dom";
import { tarkovMeHref } from "@/features/guides/tarkov/model/tarkovHomeNav";

export default function TarkovCollectionPage() {
  return <Navigate to={tarkovMeHref("collection")} replace />;
}
