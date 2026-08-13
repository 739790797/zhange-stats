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
import { fetchTaygedoAttendanceCalendar } from "@/api/client";
import { CheckinAwardsLine } from "@/components/CheckinAwardsLine";
import { apiError } from "@/lib/apiError";

export function TaygedoAttendanceCalendarButton({
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
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const queryKey = ["taygedo-attendance-calendar", gameCode, roleUid];

  const query = useQuery({
    queryKey,
    queryFn: () => fetchTaygedoAttendanceCalendar(gameCode, roleUid, false),
    enabled: open && Boolean(gameCode) && Boolean(roleUid),
    retry: false,
  });

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchTaygedoAttendanceCalendar(gameCode, roleUid, true);
      queryClient.setQueryData(queryKey, data);
      message.success("已刷新签到日历");
    } catch (e: unknown) {
      message.error(apiError(e, "刷新签到日历失败"));
    } finally {
      setRefreshing(false);
    }
  };

  const titleName = roleName || roleUid;
  const titleGame = gameName ? ` · ${gameName}` : "";

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
        title={`签到日历${titleGame} · ${titleName}`}
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
        ) : !query.data?.days?.length ? (
          <Empty description="暂无签到日历数据" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {query.data.stale ? (
              <Alert
                type="warning"
                showIcon
                message="官方同步失败，正在显示缓存"
              />
            ) : null}
            <Space wrap size={8}>
              <Tag color="blue">
                已签 {query.data.claimed_days}/{query.data.total_days} 天
              </Tag>
              {query.data.has_today_claim ? (
                <Tag color="success">今日已领</Tag>
              ) : (
                <Tag>今日未领</Tag>
              )}
            </Space>
            <Typography.Paragraph
              type="secondary"
              style={{ marginBottom: 0, fontSize: 12 }}
            >
              第 N 天 = 本月第 N 次签到，不是公历日期。
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
              {query.data.days.map((day) => (
                <div
                  key={day.day}
                  style={{
                    border:
                      "1px solid var(--ant-color-border-secondary, #f0f0f0)",
                    borderRadius: 8,
                    padding: "10px 12px",
                    background: day.claimed
                      ? "rgba(82, 196, 26, 0.06)"
                      : "transparent",
                    opacity: day.claimed ? 1 : 0.85,
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
                    <Tag
                      color={day.claimed ? "success" : "default"}
                      style={{ marginInlineEnd: 0 }}
                    >
                      {day.claimed ? "已签" : "未签"}
                    </Tag>
                  </Space>
                  <div style={{ marginTop: 8 }}>
                    <CheckinAwardsLine awards={day.awards} fallback="—" />
                  </div>
                </div>
              ))}
            </div>
          </Space>
        )}
      </Modal>
    </>
  );
}
