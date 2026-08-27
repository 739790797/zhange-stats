import { TarkovRaidRoomPanel } from "@/components/guides/tarkov/TarkovRaidRoomPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TARKOV_RAID_PREP_PATH } from "@/lib/tarkovHomeNav";
import { useParams } from "react-router-dom";

export default function TarkovRaidRoomPage() {
  const publicId = (useParams().publicId || "").trim();
  return (
    <TarkovItemsPageShell
      title="战局准备房间"
      crumbs={[{ label: "战局准备", to: TARKOV_RAID_PREP_PATH }]}
      sectionLabel="进度"
      sectionHref="/guides/tarkov/tasks"
      subtitle="多人勾选任务会并集署名；钉点和直线跟地图缩放走。到期后只读留档。"
    >
      {publicId ? (
        <TarkovRaidRoomPanel publicId={publicId} />
      ) : (
        <p>房间不存在。</p>
      )}
    </TarkovItemsPageShell>
  );
}
