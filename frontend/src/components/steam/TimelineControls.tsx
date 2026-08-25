import { Button, DatePicker, Radio, Space } from "antd";
import { type Dayjs } from "dayjs";

import type { Granularity } from "@/components/steam/constants";
import { datePickerLocale } from "@/locales/zhCN";
import { parseBeijing } from "@/lib/time";

export function TimelineControls({
  granularity,
  dayStartHour,
  anchor,
  isPendingGranularity,
  onGranularityChange,
  onShift,
  onAnchorChange,
  onDayStartHourReset,
}: {
  granularity: Granularity;
  dayStartHour: 0 | 12;
  anchor: Dayjs;
  isPendingGranularity: boolean;
  onGranularityChange: (value: Granularity) => void;
  onShift: (dir: -1 | 1) => void;
  onAnchorChange: (anchor: Dayjs) => void;
  onDayStartHourReset: () => void;
}) {
  return (
    <Space style={{ marginBottom: 16 }} wrap>
      <Radio.Group
        size="small"
        value={granularity}
        onChange={(e) => onGranularityChange(e.target.value)}
        optionType="button"
        options={[
          { label: "日", value: "day" },
          { label: "周", value: "week" },
          { label: "月", value: "month" },
          { label: "年", value: "year" },
        ]}
      />
      {!isPendingGranularity && (
        <>
          <Button size="small" onClick={() => onShift(-1)}>
            {granularity === "day" ? "向前12小时" : "上一段"}
          </Button>
          {granularity === "week" ? (
            <DatePicker
              picker="week"
              locale={datePickerLocale}
              size="small"
              value={anchor}
              allowClear={false}
              onChange={(d) =>
                d &&
                onAnchorChange(
                  parseBeijing(d.format("YYYY-MM-DD")).startOf("isoWeek"),
                )
              }
              style={{ width: 180 }}
            />
          ) : (
            <DatePicker
              className="day-window-picker"
              locale={datePickerLocale}
              size="small"
              value={anchor}
              allowClear={false}
              format={(value) => {
                const start = value.startOf("day");
                if (dayStartHour === 12) {
                  const a = start.hour(12);
                  const b = start.add(1, "day").hour(12);
                  return `${a.format("YYYY-MM-DD HH:mm")} ~ ${b.format("YYYY-MM-DD HH:mm")}`;
                }
                return `${start.format("YYYY-MM-DD")} 00:00 ~ ${start.format("YYYY-MM-DD")} 24:00`;
              }}
              onChange={(d) => {
                if (!d) return;
                onDayStartHourReset();
                onAnchorChange(
                  parseBeijing(d.format("YYYY-MM-DD")).startOf("day"),
                );
              }}
              style={{ width: 320 }}
            />
          )}
          <Button size="small" onClick={() => onShift(1)}>
            {granularity === "day" ? "向后12小时" : "下一段"}
          </Button>
        </>
      )}
    </Space>
  );
}
