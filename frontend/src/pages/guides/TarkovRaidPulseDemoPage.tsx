import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMapDetail } from "@/api/guidesApi";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TarkovRaidRoomChannelRoster } from "@/components/guides/tarkov/TarkovRaidRoomChannelRoster";
import { TarkovRaidSessionMap } from "@/components/guides/tarkov/TarkovRaidSessionMap";
import { TarkovRaidWorkspace } from "@/components/guides/tarkov/TarkovRaidWorkspace";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import { isAdminUser } from "@/lib/isAdminUser";
import {
  PULSE_DEMO_MAP_ID,
  PULSE_DEMO_MAP_SWITCH_MS,
  PULSE_DEMO_ROOM_PUBLIC_ID,
  pulseDemoChannel,
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
  const self = useMemo(
    () =>
      me?.id
        ? { user_id: me.id, display_name: selfName || `用户${me.id}` }
        : null,
    [me?.id, selfName],
  );
  const [mapHop, setMapHop] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => {
      setMapHop((hop) => hop + 1);
    }, PULSE_DEMO_MAP_SWITCH_MS);
    return () => window.clearInterval(timer);
  }, []);
  const members = useMemo(() => pulseDemoMembers(self), [self]);
  const channel = useMemo(() => pulseDemoChannel(self, mapHop), [mapHop, self]);
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
    <TarkovItemsPageShell title="找人线演示" crumbs={[]} hideHead fill fillBleed>
      <TarkovRaidWorkspace
        dockOpen={false}
        showDock={false}
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
            memberPhases={channel.phases}
            pulseDemoHop={mapHop}
            topLeft={
              <TarkovRaidRoomChannelRoster
                members={members}
                viewMaps={channel.viewMaps}
                phaseByUser={channel.phases}
              />
            }
            canEdit={false}
            onQuestLabelClick={() => {}}
          />
        }
      />
    </TarkovItemsPageShell>
  );
}
