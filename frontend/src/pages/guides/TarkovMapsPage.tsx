import { TarkovMapsPanel } from "@/components/guides/tarkov/TarkovMapsPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovMapsPage() {
  return (
    <TarkovItemsPageShell
      title="地图"
      crumbs={[]}
      sectionLabel="地图"
      subtitle="突袭时长 / 人数 / 缩略图。互动图层在详情页链到 tarkov.dev。"
    >
      <TarkovMapsPanel />
    </TarkovItemsPageShell>
  );
}
