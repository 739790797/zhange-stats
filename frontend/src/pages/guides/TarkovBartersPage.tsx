import { TarkovBartersPanel } from "@/components/guides/tarkov/TarkovBartersPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovBartersPage() {
  return (
    <TarkovItemsPageShell
      title="商人交易利润"
      crumbs={[]}
      sectionLabel="工具"
      subtitle="以物易物成本按跳蚤低价估算；狗牌等无报价的交易利润显示为 —。"
    >
      <TarkovBartersPanel />
    </TarkovItemsPageShell>
  );
}
