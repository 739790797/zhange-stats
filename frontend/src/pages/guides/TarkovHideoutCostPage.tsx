import { TarkovHideoutCostPanel } from "@/components/guides/tarkov/TarkovHideoutCostPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovHideoutCostPage() {
  return (
    <TarkovItemsPageShell
      title="藏身处建造成本"
      crumbs={[]}
      sectionLabel="工具"
      subtitle="把各模块全部等级的升级材料按跳蚤低价加总。"
    >
      <TarkovHideoutCostPanel />
    </TarkovItemsPageShell>
  );
}
