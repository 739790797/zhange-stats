import { CalendarOutlined, ReloadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Empty,
  Modal,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { useState } from "react";
import {
  CheckinAwardsLine,
  CHECKIN_CALENDAR_AWARD_ICON_SIZE,
  type CheckinAward,
} from "@/components/CheckinAwardsLine";
import { apiError } from "@/lib/apiError";

export type AttendanceCalendarDay = {
  day: number;
  claimed: boolean;
  awards?: CheckinAward[] | null;
};

export type AttendanceCalendarData = {
  days?: AttendanceCalendarDay[] | null;
  claimed_days: number;
  total_days: number;
  has_today_claim: boolean;
  stale?: boolean;
  progress_reliable?: boolean | null;
};

export type AttendanceCalendarButtonProps = {
  queryKey: unknown[];
  enabled: boolean;
  fetchCalendar: (force: boolean) => Promise<AttendanceCalendarData>;
  modalTitle: string;
  /** 如「第 N 天 = 本周期第 N 次签到，不是公历日期。」 */
  dayOrdinalHint: string;
  /**
   * 进度不可信时是否仍点亮「已签」。默认 true。
   * 方舟 B 服为 false：只展示奖励一览。
   */
  claimMarksWhenUnreliable?: boolean;
  /** progress_reliable === false 时的说明 */
  unreliableHint?: string;
};

/** 行内「签到日历」：小 link + Modal + 刷新 + 奖励格。新平台日历套此组件。 */
export function AttendanceCalendarButton({
  queryKey,
  enabled,
  fetchCalendar,
  modalTitle,
  dayOrdinalHint,
  claimMarksWhenUnreliable = true,
  unreliableHint,
}: AttendanceCalendarButtonProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const query = useQuery({
    queryKey,
    queryFn: () => fetchCalendar(false),
    enabled: open && enabled,
    retry: false,
  });

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchCalendar(true);
      queryClient.setQueryData(queryKey, data);
      message.success("已刷新签到日历");
    } catch (e: unknown) {
      message.error(apiError(e, "刷新签到日历失败"));
    } finally {
      setRefreshing(false);
    }
  };

  const data = query.data;
  const progressReliable = data?.progress_reliable !== false;
  const showClaimMarks = progressReliable || claimMarksWhenUnreliable;

  return (
    <>
      <Button
        type="link"
        size="small"
        icon={<CalendarOutlined />}
        style={{ paddingInline: 4, height: "auto" }}
        onClick={() => setOpen(true)}
      >
        签到日历
      </Button>
      <Modal
        title={modalTitle}
        open={open}
        onCancel={() => setOpen(false)}
        width={840}
        footer={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              loading={refreshing}
              onClick={() => void onRefresh()}
            >
              刷新
            </Button>
            <Button type="primary" onClick={() => setOpen(false)}>
              关闭
            </Button>
          </Space>
        }
        destroyOnClose
      >
        {query.isLoading ? (
          <div style={{ textAlign: "center", padding: 32 }}>
            <Spin />
          </div>
        ) : query.isError ? (
          <Alert
            type="warning"
            showIcon
            message={apiError(query.error, "加载签到日历失败")}
          />
        ) : !data?.days?.length ? (
          <Empty description="暂无签到日历数据" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {data.stale ? (
              <Alert
                type="warning"
                showIcon
                message="官方同步失败，正在显示缓存"
              />
            ) : null}
            {!progressReliable && unreliableHint ? (
              <Alert type="info" showIcon message={unreliableHint} />
            ) : null}
            <Space wrap size={8}>
              {showClaimMarks ? (
                <Tag color="blue">
                  已签 {data.claimed_days}/{data.total_days} 天
                </Tag>
              ) : (
                <Tag color="blue">共 {data.total_days} 天奖励</Tag>
              )}
              {showClaimMarks ? (
                data.has_today_claim ? (
                  <Tag color="success">今日已领</Tag>
                ) : (
                  <Tag>今日未领</Tag>
                )
              ) : null}
            </Space>
            <Typography.Paragraph
              type="secondary"
              style={{ marginBottom: 0, fontSize: 12 }}
            >
              {dayOrdinalHint}
            </Typography.Paragraph>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(132px, 1fr))",
                gap: 10,
                maxHeight: "60vh",
                overflow: "auto",
              }}
            >
              {data.days.map((day) => {
                const showClaimed = showClaimMarks && day.claimed;
                return (
                  <div
                    key={day.day}
                    style={{
                      border:
                        "1px solid var(--ant-color-border-secondary, #f0f0f0)",
                      borderRadius: 8,
                      padding: "10px 12px",
                      background: showClaimed
                        ? "rgba(82, 196, 26, 0.06)"
                        : "transparent",
                      opacity: showClaimMarks ? (showClaimed ? 1 : 0.85) : 1,
                    }}
                  >
                    <Space
                      style={{
                        width: "100%",
                        justifyContent: "space-between",
                      }}
                      size={4}
                    >
                      <Typography.Text strong>第 {day.day} 天</Typography.Text>
                      {showClaimMarks ? (
                        <Tag
                          color={day.claimed ? "success" : "default"}
                          style={{ marginInlineEnd: 0 }}
                        >
                          {day.claimed ? "已签" : "未签"}
                        </Tag>
                      ) : null}
                    </Space>
                    <div style={{ marginTop: 8 }}>
                      <CheckinAwardsLine
                        awards={day.awards}
                        fallback="—"
                        iconSize={CHECKIN_CALENDAR_AWARD_ICON_SIZE}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </Space>
        )}
      </Modal>
    </>
  );
}
