import { TarkovWipeLengthPanel } from "@/components/guides/tarkov/TarkovWipeLengthPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovWipeLengthPage() {
  return (
    <TarkovItemsPageShell
      title="平均删档周期"
      crumbs={[]}
      sectionLabel="工具"
      subtitle="历史赛季长度，用于估算当前 wipe 进度。"
    >
      <TarkovWipeLengthPanel />
    </TarkovItemsPageShell>
  );
}
