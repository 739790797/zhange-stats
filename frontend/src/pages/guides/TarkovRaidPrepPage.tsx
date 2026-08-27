import { TarkovRaidPrepPanel } from "@/components/guides/tarkov/TarkovRaidPrepPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovRaidPrepPage() {
  return (
    <TarkovItemsPageShell
      title="战局准备"
      crumbs={[]}
      sectionLabel="进度"
      sectionHref="/guides/tarkov/tasks"
      subtitle="先选地图，再勾任务。目标区域、刷新点和区域名会叠到图上；Wiki 图文走法仍是补充。"
    >
      <TarkovRaidPrepPanel />
    </TarkovItemsPageShell>
  );
}
