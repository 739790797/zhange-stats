import { TarkovLootTiersPanel } from "@/components/guides/tarkov/TarkovLootTiersPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovLootTiersPage() {
  return (
    <TarkovItemsPageShell
      title="战利品等级"
      crumbs={[]}
      sectionLabel="进度"
      sectionHref="/guides/tarkov/tasks"
      subtitle="按跳蚤市场每格价格把可出售物品分成 S–E。"
    >
      <TarkovLootTiersPanel />
    </TarkovItemsPageShell>
  );
}
