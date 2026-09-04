import { TarkovMePanel } from "@/components/guides/tarkov/TarkovMePanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovMePage() {
  return (
    <TarkovItemsPageShell crumbs={[]} sectionLabel="个人中心">
      <TarkovMePanel />
    </TarkovItemsPageShell>
  );
}
