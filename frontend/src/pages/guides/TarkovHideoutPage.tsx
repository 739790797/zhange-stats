import { TarkovHideoutPanel } from "@/components/guides/tarkov/TarkovHideoutPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovHideoutPage() {
  return (
    <TarkovItemsPageShell
      title="藏身处"
      crumbs={[]}
      sectionLabel="进度"
      sectionHref="/guides/tarkov/tasks"
      subtitle="模块升级材料、前置站点与商人等级。点图标筛选。"
    >
      <TarkovHideoutPanel />
    </TarkovItemsPageShell>
  );
}
