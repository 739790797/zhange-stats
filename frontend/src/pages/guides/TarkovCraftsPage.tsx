import { TarkovCraftsPanel } from "@/components/guides/tarkov/TarkovCraftsPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovCraftsPage() {
  return (
    <TarkovItemsPageShell
      title="藏身处制作利润"
      crumbs={[]}
      sectionLabel="工具"
      subtitle="制作时长与跳蚤利润。点模块筛选。"
    >
      <TarkovCraftsPanel />
    </TarkovItemsPageShell>
  );
}
