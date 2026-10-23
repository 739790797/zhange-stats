import { TarkovKeyPacksPanel } from "@/features/guides/tarkov/components/TarkovKeyPacksPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";

export default function TarkovKeyPacksPage() {
  return (
    <TarkovItemsPageShell crumbs={[]} sectionLabel="钥匙分类" title="钥匙分类">
      <TarkovKeyPacksPanel wiki />
    </TarkovItemsPageShell>
  );
}
