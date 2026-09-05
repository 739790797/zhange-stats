import { Alert } from "antd";
import { useMemo } from "react";
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMapDetail } from "@/api/guidesApi";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TarkovRaidMemberStrip } from "@/components/guides/tarkov/TarkovRaidMemberStrip";
import { TarkovRaidSessionMap } from "@/components/guides/tarkov/TarkovRaidSessionMap";
import { TarkovRaidWorkspace } from "@/components/guides/tarkov/TarkovRaidWorkspace";
import { TARKOV_RAID_PREP_PATH } from "@/lib/tarkovHomeNav";
import type { RaidPrepMapParticipant } from "@/lib/tarkovRaidPrep";
import {
  PULSE_DEMO_MAP_ID,
  PULSE_DEMO_ROOM_PUBLIC_ID,
  PULSE_DEMO_TICK_MS,
  PLAYER_FIX_PULSE_MS,
  pulseDemoMembers,
} from "@/lib/tarkovRaidRooms";
import { useAuthStore } from "@/stores/authStore";

export default function TarkovRaidPulseDemoPage() {
  const me = useAuthStore((state) => state.user);
  const mapQuery = useQuery({
    queryKey: ["tarkov", "map", PULSE_DEMO_MAP_ID],
    queryFn: () => fetchTarkovMapDetail(PULSE_DEMO_MAP_ID),
  });
  const selfName = (me?.display_name || me?.username || "").trim();
  const members = useMemo(
    () =>
      pulseDemoMembers(
        me?.id
          ? {
              user_id: me.id,
              display_name: selfName || `用户${me.id}`,
            }
          : null,
      ),
    [me?.id, selfName],
  );

  if (!import.meta.env.DEV) {
    return <Navigate to={TARKOV_RAID_PREP_PATH} replace />;
  }

  return (
    <TarkovItemsPageShell title="找人线演示" crumbs={[]} hideHead fill>
      <TarkovRaidWorkspace
        dockOpen={false}
        showDock={false}
        title="找人线演示"
        meta={
          <>
            海关 · 本地假人 · 约 {PLAYER_FIX_PULSE_MS / 1000} 秒淡出 · 每{" "}
            {PULSE_DEMO_TICK_MS / 1000} 秒换点
          </>
        }
        members={<TarkovRaidMemberStrip members={members} />}
        belowBar={
          <Alert
            type="info"
            showIcon
            message="开发环境演示房：不写库、不进大厅、不连房间 WebSocket"
            description="两个假人轮流广播定位。你自己若也有截图定位，线会连到你。生产构建打不开这个地址。"
          />
        }
        goonMapId={PULSE_DEMO_MAP_ID}
        map={
          <TarkovRaidSessionMap
            publicId={PULSE_DEMO_ROOM_PUBLIC_ID}
            mapId={PULSE_DEMO_MAP_ID}
            detail={mapQuery.data}
            loading={mapQuery.isLoading}
            error={mapQuery.isError ? mapQuery.error : undefined}
            questOverlays={[]}
            focusRequest={null}
            highlightTaskId=""
            suppressLocalFix={false}
            authorUserId={me?.id || 0}
            authorDisplayName={selfName}
            members={members}
            canEdit={false}
            onQuestLabelClick={() => {}}
            questParticipantsByTask={EMPTY_PARTICIPANTS}
          />
        }
      />
    </TarkovItemsPageShell>
  );
}

const EMPTY_PARTICIPANTS = new Map<
  string,
  readonly RaidPrepMapParticipant[]
>();
