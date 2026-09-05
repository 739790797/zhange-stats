import { useSearchParams } from "react-router-dom";
import { TarkovMePanel } from "@/components/guides/tarkov/TarkovMePanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { resolveTarkovMeTab } from "@/lib/tarkovHomeNav";

export default function TarkovMePage() {
  const [searchParams] = useSearchParams();
  const fill = resolveTarkovMeTab(searchParams.get("tab")) === "collection";
  return (
    <TarkovItemsPageShell crumbs={[]} sectionLabel="个人中心" fill={fill}>
      <TarkovMePanel />
    </TarkovItemsPageShell>
  );
}
