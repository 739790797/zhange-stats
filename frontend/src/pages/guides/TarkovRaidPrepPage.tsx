import { TarkovRaidPrepPanel } from "@/components/guides/tarkov/TarkovRaidPrepPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovRaidPrepPage() {
  return (
    <TarkovItemsPageShell title="联机大厅" crumbs={[]} hideHead fill>
      <TarkovRaidPrepPanel />
    </TarkovItemsPageShell>
  );
}
