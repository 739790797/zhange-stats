import { TarkovBossesHubPanel } from "@/components/guides/tarkov/TarkovBossesHubPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovBossesPage() {
  return (
    <TarkovItemsPageShell
      title="BOSS"
      crumbs={[]}
      sectionLabel="BOSS"
      code="DATABASE_SEC_BOSSES"
      subtitle="按 Boss / Elite / Soldier 分组"
    >
      <TarkovBossesHubPanel />
    </TarkovItemsPageShell>
  );
}
