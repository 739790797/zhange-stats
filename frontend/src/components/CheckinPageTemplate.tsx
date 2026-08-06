import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Card,
  Empty,
  Space,
  Switch,
  TimePicker,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import dayjs, { type Dayjs } from "dayjs";
import { isCheckinSuccess } from "@/lib/checkinStatus";
import { CheckinAwardsLine } from "@/components/CheckinAwardsLine";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import { PageHeader } from "@/components/PageHeader";
import {
  PlatformIcon,
  checkinGameIcon,
  type PlatformIconName,
} from "@/components/PlatformIcon";

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
  awards?: Array<{
    name: string;
    count?: number;
    resource_id?: string | null;
    resource_type?: string | null;
    icon_url?: string | null;
  }> | null;
  extra_text?: string | null;
  auto_checkin?: boolean | null;
  checkin_hour?: number | null;
  checkin_minute?: number | null;
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

export interface CheckinRolePrefPayload {
  game_code: string;
  role_uid: string;
  enabled: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
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
  updateRolePref: (payload: CheckinRolePrefPayload) => Promise<CheckinPageStatus>;
  /** 是否展示 phone_mask（塔吉多） */
  showPhoneMask?: boolean;
  /** 嵌入平台页 Tabs 时隐藏外层标题区 */
  contentOnly?: boolean;
  /** 未知 game_code 时的平台/社区图标回退 */
  platformIcon?: PlatformIconName;
  /** 今日签到每一行状态标签后的附加内容（如官服签到日历） */
  renderResultExtra?: (row: CheckinPageResultItem) => ReactNode;
}

function toScheduleValue(hour: number, minute: number): Dayjs {
  return dayjs().hour(hour).minute(minute).second(0).millisecond(0);
}

function snapMinute(minute: number): number {
  return Math.max(0, Math.min(55, minute - (minute % 5)));
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

function AwardsBlock({ row }: { row: CheckinPageResultItem }) {
  const text = awardsText(row);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      <Typography.Text type="secondary">奖励：</Typography.Text>
      <CheckinAwardsLine
        awards={row.awards}
        awardsText={text === "-" ? null : text}
        fallback="-"
      />
    </div>
  );
}

function rowKey(row: CheckinPageResultItem) {
  return `${row.game_code || ""}::${row.role_uid || ""}`;
}

type GameGroup = {
  game_code: string;
  game_name: string;
  items: CheckinPageResultItem[];
};

function groupTodayResults(rows: CheckinPageResultItem[]): GameGroup[] {
  const order: string[] = [];
  const map = new Map<string, GameGroup>();
  for (const row of rows) {
    const code = row.game_code || "_";
    let group = map.get(code);
    if (!group) {
      group = {
        game_code: code,
        game_name: row.game_name || row.game_code || "签到",
        items: [],
      };
      map.set(code, group);
      order.push(code);
    } else if (!group.game_name && row.game_name) {
      group.game_name = row.game_name;
    }
    group.items.push(row);
  }
  return order.map((c) => map.get(c)!);
}

function RoleAutoCheckinControls({
  row,
  saving,
  onSave,
}: {
  row: CheckinPageResultItem;
  saving: boolean;
  onSave: (payload: CheckinRolePrefPayload) => Promise<void>;
}) {
  const gameCode = row.game_code || "";
  const roleUid = row.role_uid || "";
  const [enabled, setEnabled] = useState(Boolean(row.auto_checkin));
  const [hour, setHour] = useState(row.checkin_hour ?? 0);
  const [minute, setMinute] = useState(
    row.checkin_minute != null ? snapMinute(row.checkin_minute) : 5,
  );
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    const h = row.checkin_hour ?? 0;
    const m = row.checkin_minute != null ? snapMinute(row.checkin_minute) : 5;
    setEnabled(Boolean(row.auto_checkin));
    setHour(h);
    setMinute(m);
    setEditing(false);
  }, [row.auto_checkin, row.checkin_hour, row.checkin_minute, row.game_code, row.role_uid]);

  const timeLocked = enabled && !editing;
  const scheduleValue = toScheduleValue(hour, minute);

  if (!gameCode || !roleUid) return null;

  return (
    <Space wrap size={8} style={{ marginTop: 0, justifyContent: "flex-end" }}>
      <Typography.Text type="secondary">自动签到</Typography.Text>
      <Switch
        size="small"
        checked={enabled}
        loading={saving}
        onChange={(v) => {
          setEnabled(v);
          if (!v) {
            setEditing(false);
            void onSave({
              game_code: gameCode,
              role_uid: roleUid,
              enabled: false,
              checkin_hour: hour,
              checkin_minute: minute,
            });
          } else {
            // 开启后进入编辑，时间需点「保存」才落库
            setEditing(true);
          }
        }}
      />
      <TimePicker
        size="small"
        format="HH:mm"
        allowClear={false}
        showNow={false}
        needConfirm={false}
        minuteStep={5}
        value={scheduleValue}
        disabled={!enabled || timeLocked || saving}
        style={{ width: 104 }}
        onChange={(v) => {
          if (!v) return;
          // 仅填入本地时间，不请求保存
          setHour(v.hour());
          setMinute(snapMinute(v.minute()));
        }}
      />
      {enabled && timeLocked ? (
        <Button size="small" type="link" onClick={() => setEditing(true)}>
          修改
        </Button>
      ) : null}
      {enabled && editing ? (
        <Button
          size="small"
          type="primary"
          loading={saving}
          onClick={() => {
            void onSave({
              game_code: gameCode,
              role_uid: roleUid,
              enabled: true,
              checkin_hour: hour,
              checkin_minute: minute,
            })
              .then(() => setEditing(false))
              .catch(() => {
                /* 错误由外层 message 处理 */
              });
          }}
        >
          保存
        </Button>
      ) : null}
    </Space>
  );
}

export function CheckinPageTemplate({
  title,
  subtitle,
  bindName,
  bindPanel,
  statusQueryKey,
  fetchStatus,
  triggerCheckin,
  updateRolePref,
  showPhoneMask: _showPhoneMask = false,
  contentOnly = false,
  platformIcon,
  renderResultExtra,
}: CheckinPageTemplateProps) {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [savingKey, setSavingKey] = useState<string | null>(null);

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
      if (statusQueryKey[0] === "skland-status") {
        queryClient.invalidateQueries({
          queryKey: ["arknights-attendance-calendar"],
        });
      }
    },
    onError: (e: unknown) => message.error(apiError(e, "签到失败")),
  });

  const saveRolePref = useMutation({
    mutationFn: async (payload: CheckinRolePrefPayload) => {
      setSavingKey(`${payload.game_code}::${payload.role_uid}`);
      return updateRolePref(payload);
    },
    onSuccess: (data, payload) => {
      message.success(payload.enabled ? "已保存自动签到设置" : "已关闭该角色自动签到");
      queryClient.setQueryData(statusQueryKey, data);
      queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
    onSettled: () => setSavingKey(null),
  });

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
        <div>
            {todayResults.length ? (
              <Space direction="vertical" size={20} style={{ width: "100%" }}>
                {groupTodayResults(todayResults).map((group) => {
                  const iconName = checkinGameIcon(
                    group.game_code,
                    platformIcon,
                  );
                  return (
                    <div key={group.game_code}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          marginBottom: 8,
                        }}
                      >
                        {iconName ? (
                          <PlatformIcon name={iconName} size={22} />
                        ) : null}
                        <Typography.Text strong>
                          {group.game_name}
                        </Typography.Text>
                      </div>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns:
                            "minmax(8rem, max-content) auto auto minmax(0, 1fr)",
                          columnGap: 10,
                          rowGap: 10,
                          alignItems: "center",
                          paddingLeft: 30,
                        }}
                      >
                        {group.items.map((row, index) => (
                          <div
                            key={rowKey(row)}
                            style={{ display: "contents" }}
                          >
                            <span style={{ whiteSpace: "nowrap" }}>
                              {row.role_name || row.role_uid}
                              {row.channel_name ? (
                                <Typography.Text type="secondary">
                                  {" "}
                                  · {row.channel_name}
                                </Typography.Text>
                              ) : null}
                            </span>
                            <CheckinStatusTag
                              status={row.status}
                              statusLabel={row.status_label}
                            />
                            <span>
                              {renderResultExtra?.(row) ?? null}
                            </span>
                            <div
                              style={{
                                justifySelf: "end",
                                minWidth: 0,
                              }}
                            >
                              <RoleAutoCheckinControls
                                row={row}
                                saving={savingKey === rowKey(row)}
                                onSave={async (payload) => {
                                  await saveRolePref.mutateAsync(payload);
                                }}
                              />
                            </div>
                            <div
                              style={{
                                gridColumn: "1 / -1",
                                paddingBottom: 4,
                                borderBottom:
                                  index < group.items.length - 1
                                    ? "1px solid rgba(0,0,0,0.06)"
                                    : undefined,
                              }}
                            >
                              <AwardsBlock row={row} />
                              {row.extra_text ? (
                                <Typography.Text type="secondary">
                                  {row.extra_text}
                                </Typography.Text>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </Space>
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
