import { TarkovKeyPacksPanel } from "@/components/guides/tarkov/TarkovKeyPacksPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovKeyPacksPage() {
  return (
    <TarkovItemsPageShell crumbs={[]} sectionLabel="钥匙分类" title="钥匙分类">
      <TarkovKeyPacksPanel wiki />
    </TarkovItemsPageShell>
  );
}
