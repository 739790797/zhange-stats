import { useSearchParams } from "react-router-dom";
import { TarkovMapsPanel } from "@/components/guides/tarkov/TarkovMapsPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { parseTarkovMaintainMode } from "@/lib/tarkovHomeNav";

export default function TarkovMapsPage() {
  const [searchParams] = useSearchParams();
  const maintain = parseTarkovMaintainMode(searchParams.get("maintain"));
  return (
    <TarkovItemsPageShell
      title={maintain ? "地图信息" : "地图"}
      crumbs={[]}
      sectionLabel="地图"
      subtitle={
        maintain
          ? "选一张图，改地名。"
          : "点进地图看图上的撤离点和 BOSS。"
      }
    >
      <TarkovMapsPanel />
    </TarkovItemsPageShell>
  );
}
