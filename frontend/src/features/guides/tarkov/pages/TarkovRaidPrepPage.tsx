import { TarkovRaidPrepPanel } from "@/features/guides/tarkov/components/TarkovRaidPrepPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";

export default function TarkovRaidPrepPage() {
  return (
    <TarkovItemsPageShell title="联机大厅" crumbs={[]} hideHead fill>
      <TarkovRaidPrepPanel />
    </TarkovItemsPageShell>
  );
}
