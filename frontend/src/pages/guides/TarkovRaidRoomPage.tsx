import { TarkovRaidRoomPanel } from "@/components/guides/tarkov/TarkovRaidRoomPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { useParams } from "react-router-dom";

export default function TarkovRaidRoomPage() {
  const publicId = (useParams().publicId || "").trim();
  return (
    <TarkovItemsPageShell title="联机大厅" crumbs={[]} hideHead fill>
      {publicId ? (
        <TarkovRaidRoomPanel publicId={publicId} />
      ) : (
        <p>房间不存在。</p>
      )}
    </TarkovItemsPageShell>
  );
}
