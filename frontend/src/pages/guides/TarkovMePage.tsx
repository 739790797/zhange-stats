import { Navigate, useLocation } from "react-router-dom";
import { useSearchParams } from "react-router-dom";
import { TarkovMePanel } from "@/components/guides/tarkov/TarkovMePanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { resolveTarkovMeTab } from "@/lib/tarkovHomeNav";
import { useAuthStore } from "@/stores/authStore";

export default function TarkovMePage() {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const fill = resolveTarkovMeTab(searchParams.get("tab")) === "collection";
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return (
    <TarkovItemsPageShell
      crumbs={[]}
      sectionLabel="个人中心"
      fill={fill}
      fillPagePad={fill}
    >
      <TarkovMePanel />
    </TarkovItemsPageShell>
  );
}
