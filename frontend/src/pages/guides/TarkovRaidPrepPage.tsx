import { TarkovRaidPrepPanel } from "@/components/guides/tarkov/TarkovRaidPrepPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovRaidPrepPage() {
  return (
    <TarkovItemsPageShell title="战局准备" crumbs={[]} hideHead fill>
      <TarkovRaidPrepPanel />
    </TarkovItemsPageShell>
  );
}
