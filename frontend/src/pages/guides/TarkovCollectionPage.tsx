import { Navigate } from "react-router-dom";
import { tarkovMeHref } from "@/lib/tarkovHomeNav";

export default function TarkovCollectionPage() {
  return <Navigate to={tarkovMeHref("collection")} replace />;
}
