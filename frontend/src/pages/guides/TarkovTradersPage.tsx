import { TarkovTradersHubPanel } from "@/components/guides/tarkov/TarkovTradersHubPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovTradersPage() {
  return (
    <TarkovItemsPageShell
      title="商人"
      crumbs={[]}
      sectionLabel="商人"
      code="DATABASE_SEC_TRADERS"
      subtitle="头像 / 英文名 / 中文简称。点进各商人查看忠诚等级报价。"
    >
      <TarkovTradersHubPanel />
    </TarkovItemsPageShell>
  );
}
