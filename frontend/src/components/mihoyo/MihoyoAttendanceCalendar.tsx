import { fetchMihoyoAttendanceCalendar } from "@/api/client";
import { AttendanceCalendarButton } from "@/components/AttendanceCalendarButton";

export function MihoyoAttendanceCalendarButton({
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
      queryKey={["mihoyo-attendance-calendar", gameCode, roleUid]}
      enabled={Boolean(gameCode) && Boolean(roleUid)}
      fetchCalendar={(force) =>
        fetchMihoyoAttendanceCalendar(gameCode, roleUid, force)
      }
      modalTitle={`签到日历${titleGame} · ${titleName}`}
      dayOrdinalHint="第 N 天 = 本月第 N 次签到，不是公历日期。"
      unreliableHint="本月有漏签，格子按已签次数顺序标记，可能与官方日历日期不完全对应。"
    />
  );
}
