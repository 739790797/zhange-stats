import {
  fetchTaygedoStatus,
  triggerTaygedoCheckin,
  updateTaygedoRolePref,
} from "@/api/client";
import { CheckinPageTemplate } from "@/components/CheckinPageTemplate";
import {
  hasTaygedoAttendanceCalendar,
  TaygedoAttendanceCalendarButton,
} from "@/components/TaygedoAttendanceCalendar";
import { TaygedoBindPanel } from "@/components/TaygedoBindPanel";

export default function TaygedoPage() {
  return (
    <CheckinPageTemplate
      title="塔吉多"
      bindName="塔吉多"
      bindPanel={<TaygedoBindPanel title="绑定塔吉多账号" />}
      statusQueryKey={["taygedo-status"]}
      fetchStatus={fetchTaygedoStatus}
      triggerCheckin={triggerTaygedoCheckin}
      updateRolePref={updateTaygedoRolePref}
      platformIcon="taygedo"
      renderResultExtra={(row) => {
        if (!hasTaygedoAttendanceCalendar(row.game_code)) return null;
        if (!row.role_uid) return null;
        return (
          <TaygedoAttendanceCalendarButton
            gameCode={row.game_code}
            roleUid={row.role_uid}
            roleName={row.role_name}
            gameName={row.game_name}
          />
        );
      }}
    />
  );
}
