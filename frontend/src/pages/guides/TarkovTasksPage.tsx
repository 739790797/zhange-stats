import { TarkovTasksPanel } from "@/components/guides/tarkov/TarkovTasksPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovTasksPage() {
  return (
    <TarkovItemsPageShell title="任务" crumbs={[]} sectionLabel="任务">
      <TarkovTasksPanel />
    </TarkovItemsPageShell>
  );
}
