import { fetchKujiequAttendanceCalendar } from "@/api/client";
import { AttendanceCalendarButton } from "@/components/AttendanceCalendarButton";

export function KujiequAttendanceCalendarButton({
  gameCode,
  roleUid,
  roleName,
  gameName,
}: {
  gameCode: string;
  roleUid: string;
  roleName?: string | null;
  gameName?: string | null;
}) {
  const titleName = roleName || roleUid;
  const titleGame = gameName ? ` · ${gameName}` : "";

  return (
    <AttendanceCalendarButton
      queryKey={["kujiequ-attendance-calendar", gameCode, roleUid]}
      enabled={Boolean(gameCode) && Boolean(roleUid)}
      fetchCalendar={(force) =>
        fetchKujiequAttendanceCalendar(gameCode, roleUid, force)
      }
      modalTitle={`签到日历${titleGame} · ${titleName}`}
      dayOrdinalHint="第 N 天 = 本月第 N 次签到，不是公历日期。"
    />
  );
}
