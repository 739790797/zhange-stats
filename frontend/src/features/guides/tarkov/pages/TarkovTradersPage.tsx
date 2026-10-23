import { TarkovTradersHubPanel } from "@/features/guides/tarkov/components/TarkovTradersHubPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";

export default function TarkovTradersPage() {
  return (
    <TarkovItemsPageShell
      title="商人"
      crumbs={[]}
      sectionLabel="商人"
      code="DATABASE_SEC_TRADERS"
      subtitle="头像与英文名。点进各商人查看忠诚等级报价。"
    >
      <TarkovTradersHubPanel />
    </TarkovItemsPageShell>
  );
}
