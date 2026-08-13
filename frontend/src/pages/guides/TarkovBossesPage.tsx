import { TarkovBossesHubPanel } from "@/components/guides/tarkov/TarkovBossesHubPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovBossesPage() {
  return (
    <TarkovItemsPageShell
      title="BOSS"
      crumbs={[]}
      sectionLabel="BOSS"
      code="DATABASE_SEC_BOSSES"
      subtitle="Boss 是《逃离塔科夫》中令人恐惧且致命的敌人，拥有独特的装备和特质"
    >
      <TarkovBossesHubPanel />
    </TarkovItemsPageShell>
  );
}
