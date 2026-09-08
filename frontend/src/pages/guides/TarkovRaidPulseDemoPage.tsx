import { Alert } from "antd";
import { useMemo } from "react";
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMapDetail } from "@/api/guidesApi";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TarkovRaidMemberStrip } from "@/components/guides/tarkov/TarkovRaidMemberStrip";
import { TarkovRaidSessionMap } from "@/components/guides/tarkov/TarkovRaidSessionMap";
import { TarkovRaidWorkspace } from "@/components/guides/tarkov/TarkovRaidWorkspace";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import { isAdminUser } from "@/lib/isAdminUser";
import {
  PULSE_DEMO_MAP_ID,
  PULSE_DEMO_ROOM_PUBLIC_ID,
  PULSE_DEMO_TICK_MAX_MS,
  PULSE_DEMO_TICK_MIN_MS,
  PLAYER_FIX_PULSE_MS,
  pulseDemoMembers,
  pulseDemoQuestPreview,
  pulseDemoSelfUserId,
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
  const questPreview = useMemo(
    () =>
      pulseDemoQuestPreview({
        userId: me?.id,
        name: selfName,
      }),
    [me?.id, selfName],
  );

  if (!isAdminUser(me) && !import.meta.env.DEV) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <TarkovItemsPageShell title="找人线演示" crumbs={[]} hideHead fill>
      <TarkovRaidWorkspace
        dockOpen={false}
        showDock={false}
        title="找人线演示"
        meta={
          <>
            海关 · 四个假人 · 约 {PLAYER_FIX_PULSE_MS / 1000} 秒淡出 ·{" "}
            {PULSE_DEMO_TICK_MIN_MS / 1000}–{PULSE_DEMO_TICK_MAX_MS / 1000}{" "}
            秒随机换点
          </>
        }
        members={<TarkovRaidMemberStrip members={members} />}
        belowBar={
          <Alert
            type="info"
            showIcon
            message="测试房间：不写库、不进大厅、不连房间 WebSocket"
            description="彩色标点是你还要做的任务；灰色虚线带「帮」是你已完成、留给假人甲的。四个假人会错开换定位。左侧请保持「任务」勾上。仅管理员可从顶栏进入。"
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
            questOverlays={questPreview.overlays}
            questObjectiveDones={questPreview.objectiveDones}
            questSkippedByTask={questPreview.skippedByTask}
            questParticipantsByTask={questPreview.participantsByTask}
            questPeopleStartOn="all"
            focusRequest={null}
            highlightTaskId=""
            suppressLocalFix={false}
            authorUserId={pulseDemoSelfUserId(me?.id)}
            authorDisplayName={selfName}
            members={members}
            canEdit={false}
            onQuestLabelClick={() => {}}
          />
        }
      />
    </TarkovItemsPageShell>
  );
}
