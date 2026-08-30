import { TarkovMePanel } from "@/components/guides/tarkov/TarkovMePanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovMePage() {
  return (
    <TarkovItemsPageShell
      title="个人中心"
      crumbs={[]}
      sectionLabel="个人中心"
      subtitle="任务勾选、钥匙和本机日志路径都在这里。"
    >
      <TarkovMePanel />
    </TarkovItemsPageShell>
  );
}
