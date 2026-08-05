import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Card,
  Empty,
  List,
  Space,
  Switch,
  Tag,
  TimePicker,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";
import { useState } from "react";
import dayjs, { type Dayjs } from "dayjs";
import { PageHeader } from "@/components/PageHeader";
import {
  checkinStatusLabel,
  checkinStatusTagColor,
  isCheckinSuccess,
} from "@/lib/checkinStatus";

export interface CheckinPageRole {
  game_code: string;
  game_name: string;
  uid: string;
  role_name: string;
  channel_name: string;
}

export interface CheckinPageResultItem {
  game_code?: string;
  game_name?: string;
  role_uid?: string;
  role_name?: string;
  channel_name?: string;
  status: string;
  status_label?: string | null;
  message: string;
  awards_text?: string | null;
  extra_text?: string | null;
}

export interface CheckinPageStatus {
  bound: boolean;
  auto_checkin?: boolean | null;
  checkin_hour?: number | null;
  checkin_minute?: number | null;
  phone_mask?: string | null;
  last_checkin_date?: string | null;
  last_checkin_ok?: boolean | null;
  last_checkin_summary?: string | null;
  token_ok?: boolean | null;
  token_error?: string | null;
  roles?: CheckinPageRole[];
  today_results?: CheckinPageResultItem[];
}

export interface CheckinPageResponse {
  skipped: boolean;
  ok?: boolean | null;
  summary: string;
  results?: CheckinPageResultItem[];
}

export interface CheckinPageTemplateProps {
  title: string;
  subtitle?: string;
  /** 绑定源名称，如「森空岛」「塔吉多」 */
  bindName: string;
  /** 未绑定 / 凭证失效时展示的页内绑定区（替代跳转个人中心） */
  bindPanel?: ReactNode;
  statusQueryKey: string[];
  fetchStatus: (
    includeRoles?: boolean,
    force?: boolean,
  ) => Promise<CheckinPageStatus>;
  triggerCheckin: () => Promise<CheckinPageResponse>;
  updateBind: (payload: {
    auto_checkin?: boolean;
    checkin_hour?: number;
    checkin_minute?: number;
  }) => Promise<{
    auto_checkin?: boolean | null;
    checkin_hour?: number | null;
    checkin_minute?: number | null;
  }>;
  /** 是否展示 phone_mask（塔吉多） */
  showPhoneMask?: boolean;
  /** 嵌入平台页 Tabs 时隐藏外层标题区 */
  contentOnly?: boolean;
}


function StatusTag({
  status,
  statusLabel,
}: {
  status: string;
  statusLabel?: string | null;
}) {
  return (
    <Tag color={checkinStatusTagColor(status)}>
      {checkinStatusLabel(status, statusLabel)}
    </Tag>
  );
}

function awardsText(row: CheckinPageResultItem) {
  if (row.awards_text) return row.awards_text;
  if (row.status === "error") return row.message || "-";
  if (row.message && row.message.includes("获得：")) {
    return row.message.split("获得：").slice(1).join("获得：") || "-";
  }
  // 追放等：message 形如「今日已签到：积分+40」/「签到成功：…」
  if (row.message) {
    for (const sep of ["：", ":"]) {
      const idx = row.message.indexOf(sep);
      if (idx >= 0) {
        const rest = row.message.slice(idx + sep.length).trim();
        if (rest) return rest;
      }
    }
  }
  return "-";
}

export function CheckinPageTemplate({
  title,
  subtitle,
  bindName,
  bindPanel,
  statusQueryKey,
  fetchStatus,
  triggerCheckin,
  updateBind,
  showPhoneMask = false,
  contentOnly = false,
}: CheckinPageTemplateProps) {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const statusQuery = useQuery({
    queryKey: statusQueryKey,
    queryFn: () => fetchStatus(true, false),
    retry: false,
  });

  const onRefreshStatus = async () => {
    setRefreshing(true);
    try {
      const data = await fetchStatus(true, true);
      queryClient.setQueryData(statusQueryKey, data);
      message.success("已从官方同步今日签到状态");
    } catch (e: unknown) {
      message.error(apiError(e, "同步失败"));
    } finally {
      setRefreshing(false);
    }
  };

  const checkin = useMutation({
    mutationFn: triggerCheckin,
    onSuccess: (data) => {
      const results = data.results ?? [];
      const allDone =
        Boolean(results.length) &&
        results.every((r) => isCheckinSuccess(r.status));
      if (
        data.skipped ||
        (allDone && results.every((r) => r.status === "already"))
      ) {
        message.info("今日已签到");
      } else if (data.ok === false) {
        message.warning("签到未全部成功，失败角色可再次尝试");
      } else {
        message.success("签到完成");
      }
      queryClient.invalidateQueries({ queryKey: statusQueryKey });
      queryClient.invalidateQueries({ queryKey: ["profile-me"] });
      if (statusQueryKey[0] === "exilium-status") {
        queryClient.invalidateQueries({ queryKey: ["exilium-exchange"] });
      }
    },
    onError: (e: unknown) => message.error(apiError(e, "签到失败")),
  });

  const toggleAuto = useMutation({
    mutationFn: (enabled: boolean) => updateBind({ auto_checkin: enabled }),
    onSuccess: (data) => {
      message.success(data.auto_checkin ? "已开启每日自动签到" : "已关闭自动签到");
      queryClient.invalidateQueries({ queryKey: statusQueryKey });
      queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "更新失败")),
  });

  const saveSchedule = useMutation({
    mutationFn: (value: Dayjs) =>
      updateBind({
        checkin_hour: value.hour(),
        checkin_minute: value.minute(),
      }),
    onSuccess: () => {
      message.success("签到时间已保存");
      queryClient.invalidateQueries({ queryKey: statusQueryKey });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const scheduleValue = (() => {
    const h = statusQuery.data?.checkin_hour;
    const m = statusQuery.data?.checkin_minute;
    if (h == null || m == null) return dayjs().hour(0).minute(5).second(0);
    return dayjs().hour(h).minute(m).second(0);
  })();

  const bound = Boolean(statusQuery.data?.bound);
  const todayResults = statusQuery.data?.today_results || [];
  const tokenBroken = bound && statusQuery.data?.token_ok === false;
  const needsBind =
    (!bound || tokenBroken) && Boolean(bindPanel) && !statusQuery.isLoading;

  const statusCard = (
    <Card
      title="签到状态"
      loading={statusQuery.isLoading}
      style={{ marginBottom: contentOnly ? 0 : 24 }}
      extra={
        bound && !tokenBroken ? (
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={() => onRefreshStatus()}
          >
            同步官方
          </Button>
        ) : null
      }
    >
      {statusQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message={apiError(statusQuery.error, "加载签到状态失败")}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {bound ? (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 24,
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Space size={12} wrap>
              <Tag color="success">已绑定</Tag>
              {showPhoneMask && statusQuery.data?.phone_mask ? (
                <Typography.Text type="secondary">
                  {statusQuery.data.phone_mask}
                </Typography.Text>
              ) : null}
              {statusQuery.data?.token_ok === true ? (
                <Tag color="processing">凭证有效</Tag>
              ) : statusQuery.data?.token_ok === false ? (
                <Tag color="error">凭证失效</Tag>
              ) : null}
              {statusQuery.data?.last_checkin_date ? (
                <Typography.Text type="secondary">
                  最近签到：{statusQuery.data.last_checkin_date}
                  {statusQuery.data.last_checkin_ok === true
                    ? " · 成功"
                    : statusQuery.data.last_checkin_ok === false
                      ? " · 有失败"
                      : ""}
                </Typography.Text>
              ) : null}
            </Space>
            <Space wrap>
              <Typography.Text>每日自动签到</Typography.Text>
              <Switch
                checked={Boolean(statusQuery.data?.auto_checkin)}
                loading={toggleAuto.isPending}
                onChange={(v) => toggleAuto.mutate(v)}
              />
              <Typography.Text type="secondary">每天</Typography.Text>
              <TimePicker
                format="HH:mm"
                allowClear={false}
                value={scheduleValue}
                disabled={!statusQuery.data?.auto_checkin}
                needConfirm={false}
                onChange={(v) => {
                  if (v) saveSchedule.mutate(v);
                }}
              />
              <Typography.Text type="secondary">（北京时间）</Typography.Text>
            </Space>
          </div>

          <div>
            <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
              今日签到
            </Typography.Text>
            {todayResults.length ? (
              <List
                size="small"
                dataSource={todayResults}
                renderItem={(row) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                      <Space wrap>
                        <Tag>{row.game_name || row.game_code}</Tag>
                        <span>
                          {row.role_name || row.role_uid}
                          {row.channel_name ? (
                            <Typography.Text type="secondary">
                              {" "}
                              · {row.channel_name}
                            </Typography.Text>
                          ) : null}
                        </span>
                        <StatusTag
                          status={row.status}
                          statusLabel={row.status_label}
                        />
                      </Space>
                      <Typography.Text type="secondary">
                        奖励：{awardsText(row)}
                      </Typography.Text>
                      {row.extra_text ? (
                        <Typography.Text type="secondary">
                          {row.extra_text}
                        </Typography.Text>
                      ) : null}
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  tokenBroken
                    ? "无法查询今日状态"
                    : "暂无今日结果，可点击立即签到或同步官方"
                }
              />
            )}
          </div>
        </Space>
      ) : (
        <Empty description="绑定后可在此查看签到记录" />
      )}
    </Card>
  );

  if (contentOnly) {
    return statusCard;
  }

  const bindBlock = needsBind ? (
    <div
      style={{
        maxWidth: 560,
        margin: "0 auto",
        padding: "8px 0 48px",
      }}
    >
      <Alert
        type={tokenBroken ? "warning" : "info"}
        showIcon
        style={{ marginBottom: 16 }}
        message={
          tokenBroken
            ? `${bindName}凭证可能已失效`
            : `尚未绑定${bindName}`
        }
        description={
          tokenBroken
            ? statusQuery.data?.token_error || "请重新绑定后再试。"
            : undefined
        }
      />
      <Card>{bindPanel}</Card>
    </div>
  ) : null;

  return (
    <div>
      <PageHeader
        title={title}
        subtitle={subtitle}
        extra={
          bound && !tokenBroken ? (
            <Button
              type="primary"
              loading={checkin.isPending}
              onClick={() => checkin.mutate()}
            >
              立即签到
            </Button>
          ) : null
        }
      />

      {needsBind ? bindBlock : statusCard}
    </div>
  );
}
