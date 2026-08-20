import { TarkovMapsPanel } from "@/components/guides/tarkov/TarkovMapsPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovMapsPage() {
  return (
    <TarkovItemsPageShell
      title="地图"
      crumbs={[]}
      sectionLabel="地图"
      subtitle="突袭时长 / 人数。详情页内嵌可缩放地图（撤离点 / BOSS）。"
    >
      <TarkovMapsPanel />
    </TarkovItemsPageShell>
  );
}
