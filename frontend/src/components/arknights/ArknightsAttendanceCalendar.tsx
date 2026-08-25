import { fetchArknightsAttendanceCalendar } from "@/api/client";
import { AttendanceCalendarButton } from "@/components/AttendanceCalendarButton";
import { isBilibiliArknightsChannel } from "@/lib/arknightsChannel";

/** 行内「签到日历」按钮；点击弹窗展示。B 服可看奖励表，进度可能不可信。 */
export function ArknightsAttendanceCalendarButton({
  uid,
  roleName,
  channelName,
}: {
  uid: string;
  roleName?: string | null;
  channelName?: string | null;
}) {
  const bili = isBilibiliArknightsChannel(channelName);
  const titleName = roleName || uid;
  const titleChannel = channelName ? `（${channelName}）` : "";

  return (
    <AttendanceCalendarButton
      queryKey={["arknights-attendance-calendar", uid]}
      enabled={Boolean(uid)}
      fetchCalendar={(force) => fetchArknightsAttendanceCalendar(uid, force)}
      modalTitle={`签到日历 · ${titleName}${titleChannel}`}
      dayOrdinalHint="第 N 天 = 本周期第 N 次签到，不是公历日期。"
      claimMarksWhenUnreliable={false}
      unreliableHint={
        bili
          ? "B 服可展示本周期奖励一览；森空岛未返回签到进度，格子不点亮「已签」。"
          : "该渠道未返回可信签到进度，仅展示奖励一览。"
      }
    />
  );
}
