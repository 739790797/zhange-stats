import { TarkovBitcoinFarmPanel } from "@/components/guides/tarkov/TarkovBitcoinFarmPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovBitcoinFarmPage() {
  return (
    <TarkovItemsPageShell
      title="比特币矿场利润"
      crumbs={[]}
      sectionLabel="工具"
      subtitle="按显卡数量估算物理比特币产出与跳蚤收入。"
    >
      <TarkovBitcoinFarmPanel />
    </TarkovItemsPageShell>
  );
}
