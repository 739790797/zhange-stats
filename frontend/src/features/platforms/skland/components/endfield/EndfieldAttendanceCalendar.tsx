import { fetchEndfieldAttendanceCalendar } from "@/features/platforms/skland/api/sklandApi";
import { AttendanceCalendarButton } from "@/features/daily/components/AttendanceCalendarButton";

/** 终末地行内「签到日历」按钮；点击弹窗展示周期奖励。 */
export function EndfieldAttendanceCalendarButton({
  uid,
  roleName,
  channelName,
}: {
  uid: string;
  roleName?: string | null;
  channelName?: string | null;
}) {
  const titleName = roleName || uid;
  const titleChannel = channelName ? `（${channelName}）` : "";

  return (
    <AttendanceCalendarButton
      queryKey={["endfield-attendance-calendar", uid]}
      enabled={Boolean(uid)}
      fetchCalendar={(force) => fetchEndfieldAttendanceCalendar(uid, force)}
      modalTitle={`签到日历 · ${titleName}${titleChannel}`}
      dayOrdinalHint="第 N 天 = 本周期第 N 次签到，不是公历日期。"
    />
  );
}
