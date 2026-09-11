import { Navigate } from "react-router-dom";
import { tarkovHideoutHref } from "@/lib/tarkovHomeNav";

export default function TarkovHideoutPage() {
  return <Navigate to={tarkovHideoutHref()} replace />;
}
