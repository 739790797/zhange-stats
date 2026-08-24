import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Card,
  Empty,
  Modal,
  Space,
  Switch,
  Tag,
  TimePicker,
  Typography,
  message,
} from "antd";
import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import dayjs, { type Dayjs } from "dayjs";
import type { components } from "@/api/generated/schema";
import {
  checkinDialogTitle,
  classifyCheckinDialog,
  isCheckinSuccess,
  type CheckinDialogKind,
} from "@/lib/checkinStatus";
import { CheckinAwardsLine } from "@/components/CheckinAwardsLine";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import { PageHeader } from "@/components/PageHeader";
import { PlatformIcon } from "@/components/PlatformIcon";
import { isBilibiliArknightsChannel } from "@/lib/arknightsChannel";
import {
  communityGameRank,
  displayCheckinChannelName,
} from "@/lib/checkinDisplay";
import {
  checkinGameIcon,
  type PlatformIconName,
} from "@/lib/platformIcons";

/** 四平台 RoleOut 字段一致，用森空岛 schema 代表 */
export type CheckinPageRole = components["schemas"]["SklandRoleOut"];
export type CheckinPageResultItem = components["schemas"]["CheckinResultItem"];
export type CheckinPageResponse = components["schemas"]["CheckinResponse"];
export type CheckinRolePrefPayload = components["schemas"]["CheckinRolePrefUpdate"];
export type CheckinNowPayload = components["schemas"]["CheckinNowBody"];

/** 模板共用状态面（各平台 *StatusOut 超集的结构子集） */
export interface CheckinPageStatus {
  bound: boolean;
  auto_checkin?: boolean | null;
  checkin_hour?: number | null;
  checkin_minute?: number | null;
  phone_mask?: string | null;
  token_ok?: boolean | null;
  token_error?: string | null;
  roles?: CheckinPageRole[];
  today_results?: CheckinPageResultItem[];
}

export interface CheckinPageTemplateProps {
  title: string;
  subtitle?: string;
  /** 绑定源名称，如「森空岛」「塔吉多」 */
  bindName: string;
  /** 未绑定 / 凭证失效时展示的页内绑定区（替代跳转个人中心） */
  bindPanel?: ReactNode;
  statusQueryKey: string[];
  /** 打开页应 force=true；模板内固定 fetchStatus(true, true)。*Api 须显式传 force，见 frontend-conventions。 */
  fetchStatus: (
    includeRoles?: boolean,
    force?: boolean,
  ) => Promise<CheckinPageStatus>;
  triggerCheckin: (payload: CheckinNowPayload) => Promise<CheckinPageResponse>;
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

/** 仅已签展示签到奖励；B 服优先展示签到 POST 落库的 awards，无则提示不可查询 */
function TodayAwardsBlock({ row }: { row: CheckinPageResultItem }) {
  if (!isCheckinSuccess(row.status)) return null;
  const hasAwards =
    Boolean(row.awards?.length) || Boolean((row.awards_text || "").trim());
  const biliAk =
    row.game_code === "arknights" &&
    isBilibiliArknightsChannel(row.channel_name);
  if (biliAk && !hasAwards) {
    return (
      <>
        <Typography.Text type="secondary">签到奖励：</Typography.Text>
        <Typography.Text type="secondary">B服不支持查询</Typography.Text>
      </>
    );
  }
  if (!hasAwards) return null;
  return (
    <>
      <Typography.Text type="secondary">签到奖励：</Typography.Text>
      <CheckinAwardsLine
        awards={row.awards}
        awardsText={row.awards_text}
        fallback="-"
      />
    </>
  );
}

/** 「标签：内容」拆成两列，与签到奖励对齐 */
function ExtraTextRows({ text }: { text: string }) {
  const lines = text
    .split(/\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  return (
    <>
      {lines.map((line) => {
        const idx = line.indexOf("：");
        const label = idx > 0 ? line.slice(0, idx + 1) : "";
        const value = idx > 0 ? line.slice(idx + 1).trim() : line;
        return (
          <Fragment key={line}>
            <Typography.Text type="secondary">{label || null}</Typography.Text>
            <Typography.Text type="secondary">{value}</Typography.Text>
          </Fragment>
        );
      })}
    </>
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
  return order
    .map((c) => map.get(c)!)
    .sort(
      (a, b) =>
        communityGameRank(a.game_code) - communityGameRank(b.game_code),
    );
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
    <Space wrap size={8} style={{ marginTop: 0 }}>
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
            setEditing(true);
          }
        }}
      />
      {enabled ? (
        <>
          <TimePicker
            size="small"
            format="HH:mm"
            allowClear={false}
            showNow={false}
            needConfirm={false}
            minuteStep={5}
            value={scheduleValue}
            disabled={timeLocked || saving}
            style={{ width: 104 }}
            onChange={(v) => {
              if (!v) return;
              setHour(v.hour());
              setMinute(snapMinute(v.minute()));
            }}
          />
          {timeLocked ? (
            <Button size="small" type="link" onClick={() => setEditing(true)}>
              修改
            </Button>
          ) : null}
          {editing ? (
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
        </>
      ) : null}
    </Space>
  );
}

type CheckinDialogState = {
  kind: CheckinDialogKind;
  message: string;
  awards?: CheckinPageResultItem["awards"];
  awardsText?: string | null;
};

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
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [checkingKey, setCheckingKey] = useState<string | null>(null);
  const [dialog, setDialog] = useState<CheckinDialogState | null>(null);

  // 展示路径始终回源官方；staleTime 避免平台 Tabs 切换时反复 force 打上游
  const statusQuery = useQuery({
    queryKey: statusQueryKey,
    queryFn: () => fetchStatus(true, true),
    retry: false,
    staleTime: 30_000,
  });

  const refreshAfterCheckin = () => {
    void queryClient.invalidateQueries({ queryKey: statusQueryKey });
    void queryClient.invalidateQueries({ queryKey: ["profile-me"] });
    if (statusQueryKey[0] === "exilium-status") {
      void queryClient.invalidateQueries({ queryKey: ["exilium-exchange"] });
    }
    if (statusQueryKey[0] === "skland-status") {
      void queryClient.invalidateQueries({
        queryKey: ["arknights-attendance-calendar"],
      });
    }
    if (statusQueryKey[0] === "kujiequ-status") {
      void queryClient.invalidateQueries({
        queryKey: ["kujiequ-attendance-calendar"],
      });
      void queryClient.invalidateQueries({ queryKey: ["kujiequ-exchange"] });
    }
  };

  const checkin = useMutation({
    mutationFn: async (payload: CheckinNowPayload) => {
      setCheckingKey(`${payload.game_code}::${payload.role_uid}`);
      return triggerCheckin(payload);
    },
    onSuccess: (data) => {
      const results = data.results ?? [];
      const primary = results[0];
      const kind = classifyCheckinDialog({
        skipped: data.skipped,
        ok: data.ok,
        summary: data.summary,
        status: primary?.status,
        message: primary?.message || data.summary,
      });
      const body =
        (primary?.message || "").trim() ||
        (data.summary || "").trim() ||
        checkinDialogTitle(kind);
      setDialog({
        kind,
        message:
          kind === "credential"
            ? `${body}\n请重新绑定${bindName}后再试。`
            : body,
        awards: primary?.awards,
        awardsText: primary?.awards_text,
      });
      refreshAfterCheckin();
    },
    onError: (e: unknown) => {
      const msg = apiError(e, "签到失败");
      const kind = classifyCheckinDialog({
        ok: false,
        status: "error",
        message: msg,
      });
      setDialog({
        kind,
        message:
          kind === "credential"
            ? `${msg}\n请重新绑定${bindName}后再试。`
            : msg,
      });
    },
    onSettled: () => setCheckingKey(null),
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
    >
      {statusQuery.isError ? (
        <Alert
          type={statusQuery.data ? "warning" : "error"}
          showIcon
          message={apiError(statusQuery.error, "加载签到状态失败")}
          description={
            statusQuery.data
              ? "下方为最近一次成功结果；可稍后切换回本页重试刷新。"
              : undefined
          }
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
                        /* 角色 | 区服 | 状态 | 附加(日历等，吸剩余宽) | 自动签到 | 签到 */
                        gridTemplateColumns:
                          "14rem max-content max-content minmax(0, 1fr) max-content max-content",
                        columnGap: 12,
                        rowGap: 10,
                        alignItems: "center",
                        justifyItems: "start",
                        paddingLeft: 30,
                      }}
                    >
                      {group.items.map((row, index) => {
                        const autoOn = Boolean(row.auto_checkin);
                        const signed = isCheckinSuccess(row.status);
                        const canCheckin =
                          Boolean(row.game_code && row.role_uid) && !signed;
                        const channelLabel = displayCheckinChannelName(
                          row.channel_name,
                        );
                        return (
                          <div
                            key={rowKey(row)}
                            style={{ display: "contents" }}
                          >
                            <span
                              style={{
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                maxWidth: "100%",
                              }}
                            >
                              {row.role_name || row.role_uid}
                            </span>
                            {channelLabel ? (
                              <Tag>{channelLabel}</Tag>
                            ) : (
                              <span />
                            )}
                            {autoOn ? (
                              <CheckinStatusTag
                                status={row.status}
                                statusLabel={row.status_label}
                              />
                            ) : (
                              <Tag>关闭</Tag>
                            )}
                            <span style={{ minWidth: 0 }}>
                              {autoOn
                                ? (renderResultExtra?.(row) ?? null)
                                : null}
                            </span>
                            <RoleAutoCheckinControls
                              row={row}
                              saving={savingKey === rowKey(row)}
                              onSave={async (payload) => {
                                await saveRolePref.mutateAsync(payload);
                              }}
                            />
                            <div style={{ justifySelf: "start" }}>
                              {canCheckin ? (
                                <Button
                                  type="primary"
                                  size="small"
                                  loading={checkingKey === rowKey(row)}
                                  disabled={
                                    Boolean(checkingKey) &&
                                    checkingKey !== rowKey(row)
                                  }
                                  onClick={() =>
                                    checkin.mutate({
                                      game_code: row.game_code!,
                                      role_uid: row.role_uid!,
                                    })
                                  }
                                >
                                  签到
                                </Button>
                              ) : null}
                            </div>
                            <div
                              style={{
                                gridColumn: "1 / -1",
                                paddingBottom: 4,
                                display: "grid",
                                gridTemplateColumns: "max-content 1fr",
                                columnGap: 8,
                                rowGap: 2,
                                alignItems: "baseline",
                                borderBottom:
                                  index < group.items.length - 1
                                    ? "1px solid rgba(0,0,0,0.06)"
                                    : undefined,
                              }}
                            >
                              {autoOn ? <TodayAwardsBlock row={row} /> : null}
                              {autoOn && row.extra_text ? (
                                <ExtraTextRows text={row.extra_text} />
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </Space>
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                tokenBroken ? (
                  "无法查询今日状态"
                ) : (
                  <span>
                    暂无已加入本站的角色。请到{" "}
                    <Link to="/daily">我的日常</Link>{" "}
                    同步并勾选要加入的角色。
                  </span>
                )
              }
            />
          )}
        </div>
      ) : (
        <Empty description="绑定后可在此查看签到状态" />
      )}
    </Card>
  );

  const resultModal = (
    <Modal
      open={Boolean(dialog)}
      title={dialog ? checkinDialogTitle(dialog.kind) : undefined}
      onCancel={() => setDialog(null)}
      onOk={() => setDialog(null)}
      cancelButtonProps={{ style: { display: "none" } }}
      okText="知道了"
      destroyOnClose
    >
      {dialog ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
            {dialog.message}
          </Typography.Paragraph>
          {dialog.kind === "success" || dialog.kind === "already" ? (
            (dialog.awards?.length || (dialog.awardsText || "").trim()) ? (
              <CheckinAwardsLine
                awards={dialog.awards}
                awardsText={dialog.awardsText}
                fallback=""
              />
            ) : null
          ) : null}
          {dialog.kind === "credential" ? (
            <Alert
              type="warning"
              showIcon
              message={`请重新绑定${bindName}`}
            />
          ) : null}
        </Space>
      ) : null}
    </Modal>
  );

  if (contentOnly) {
    return (
      <>
        {statusCard}
        {resultModal}
      </>
    );
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
      <PageHeader title={title} subtitle={subtitle} />
      {needsBind ? bindBlock : statusCard}
      {resultModal}
    </div>
  );
}
