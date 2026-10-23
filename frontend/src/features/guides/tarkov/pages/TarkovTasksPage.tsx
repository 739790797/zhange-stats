import { TarkovTasksPanel } from "@/features/guides/tarkov/components/TarkovTasksPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";

export default function TarkovTasksPage() {
  return (
    <TarkovItemsPageShell title="任务" crumbs={[]} sectionLabel="任务">
      <TarkovTasksPanel />
    </TarkovItemsPageShell>
  );
}
