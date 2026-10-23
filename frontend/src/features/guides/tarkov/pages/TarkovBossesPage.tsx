import { TarkovBossesHubPanel } from "@/features/guides/tarkov/components/TarkovBossesHubPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";

export default function TarkovBossesPage() {
  return (
    <TarkovItemsPageShell
      title="BOSS"
      crumbs={[]}
      sectionLabel="BOSS"
      code="DATABASE_SEC_BOSSES"
    >
      <TarkovBossesHubPanel />
    </TarkovItemsPageShell>
  );
}
