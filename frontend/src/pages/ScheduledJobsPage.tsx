import { ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type Key,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import {
  CHECKIN_PLATFORM_LABELS,
  CheckinTreeNameLabel,
  buildCheckinTaskScheduleColumns,
  communityGameRank,
  platformRank,
} from "@/components/checkinTaskDisplay";
import {
  fetchJobFilterMembers,
  fetchUserCheckinTasks,
  triggerScheduledJob,
  type JobTriggerResult,
  type UserCheckinTask,
} from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

const PLATFORM_OPTIONS = [
  { value: "", label: "全部平台" },
  { value: "skland", label: "森空岛" },
  { value: "taygedo", label: "塔吉多" },
  { value: "exilium", label: "追放" },
  { value: "kujiequ", label: "库街区" },
];

type RoleLeaf = UserCheckinTask & {
  rowKey: string;
  rowType: "role";
};

type GameGroupRow = {
  rowKey: string;
  rowType: "game";
  platform: string;
  game_code: string;
  game_name: string;
  children: RoleLeaf[];
};

type PlatformGroupRow = {
  rowKey: string;
  rowType: "platform";
  platform: string;
  platform_name: string;
  member_id: number;
  children: Array<GameGroupRow | RoleLeaf>;
};

type UserGroupRow = {
  rowKey: string;
  rowType: "user";
  member_id: number;
  user_label: string;
  isSelf: boolean;
  taskCount: number;
  children: PlatformGroupRow[];
};

type ScheduleRow = UserGroupRow | PlatformGroupRow | GameGroupRow | RoleLeaf;

type ExchangeDialog = {
  title: string;
  summary?: string | null;
  ok?: boolean | null;
  exchanges: NonNullable<JobTriggerResult["exchanges"]>;
};

function countLeaves(nodes: Array<GameGroupRow | RoleLeaf>): number {
  let n = 0;
  for (const node of nodes) {
    if (node.rowType === "role") n += 1;
    else n += node.children.length;
  }
  return n;
}

function buildPlatformTree(
  tasks: UserCheckinTask[],
  memberId: number,
): PlatformGroupRow[] {
  const byPlatform = new Map<string, UserCheckinTask[]>();
  for (const task of tasks) {
    const list = byPlatform.get(task.platform) || [];
    list.push(task);
    byPlatform.set(task.platform, list);
  }

  const platforms = [...byPlatform.keys()].sort(
    (a, b) => platformRank(a) - platformRank(b),
  );

  return platforms.map((platform) => {
    const list = byPlatform.get(platform) || [];
    const withGame = list.filter((t) => t.game_code);
    const legacy = list.filter((t) => !t.game_code);

    const byGame = new Map<string, UserCheckinTask[]>();
    for (const task of withGame) {
      const gc = String(task.game_code);
      const gList = byGame.get(gc) || [];
      gList.push(task);
      byGame.set(gc, gList);
    }

    const gameChildren: GameGroupRow[] = [...byGame.entries()]
      .sort(
        ([a], [b]) =>
          communityGameRank(a) - communityGameRank(b) || a.localeCompare(b),
      )
      .map(([gameCode, roles]) => ({
        rowKey: `game:${memberId}:${platform}:${gameCode}`,
        rowType: "game" as const,
        platform,
        game_code: gameCode,
        game_name: roles[0]?.game_name || gameCode,
        children: roles
          .slice()
          .sort((a, b) => (a.role_uid || "").localeCompare(b.role_uid || ""))
          .map((t) => ({
            ...t,
            rowKey: t.task_key,
            rowType: "role" as const,
          })),
      }));

    const legacyLeaves: RoleLeaf[] = legacy.map((t) => ({
      ...t,
      rowKey: t.task_key,
      rowType: "role" as const,
    }));

    return {
      rowKey: `platform:${memberId}:${platform}`,
      rowType: "platform" as const,
      platform,
      platform_name:
        CHECKIN_PLATFORM_LABELS[platform] || list[0]?.platform_name || platform,
      member_id: memberId,
      children: [...gameChildren, ...legacyLeaves],
    };
  });
}

function buildUserGroups(
  tasks: UserCheckinTask[],
  selfMemberId: number | null,
): UserGroupRow[] {
  const byMember = new Map<number, UserCheckinTask[]>();
  for (const task of tasks) {
    const list = byMember.get(task.member_id) || [];
    list.push(task);
    byMember.set(task.member_id, list);
  }

  const groups: UserGroupRow[] = [];
  for (const [memberId, list] of byMember) {
    const children = buildPlatformTree(list, memberId);
    groups.push({
      rowKey: `user:${memberId}`,
      rowType: "user",
      member_id: memberId,
      user_label: list[0]?.user_label || `member#${memberId}`,
      isSelf: selfMemberId != null && memberId === selfMemberId,
      taskCount: countLeaves(children.flatMap((p) => p.children)),
      children,
    });
  }

  groups.sort((a, b) => {
    if (a.isSelf !== b.isSelf) return a.isSelf ? -1 : 1;
    return a.user_label.localeCompare(b.user_label, "zh-CN");
  });
  return groups;
}

function collectExpandKeys(groups: UserGroupRow[]): Key[] {
  const keys: Key[] = [];
  for (const user of groups) {
    keys.push(user.rowKey);
    for (const plat of user.children) {
      keys.push(plat.rowKey);
      for (const child of plat.children) {
        if (child.rowType === "game") keys.push(child.rowKey);
      }
    }
  }
  return keys;
}

const preStyle: CSSProperties = {
  margin: 0,
  padding: 12,
  maxHeight: 320,
  overflow: "auto",
  background: "rgba(0,0,0,0.04)",
  borderRadius: 6,
  fontSize: 12,
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
};

export default function ScheduledJobsPage() {
  const queryClient = useQueryClient();
  const authUser = useAuthStore((s) => s.user);
  const [platform, setPlatform] = useState<string | undefined>();
  const [memberId, setMemberId] = useState<number | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [triggeringKey, setTriggeringKey] = useState<string | null>(null);
  const [exchangeDialog, setExchangeDialog] = useState<ExchangeDialog | null>(
    null,
  );

  const membersQuery = useQuery({
    queryKey: ["job-filter-members"],
    queryFn: fetchJobFilterMembers,
  });

  const selfMemberId = useMemo(() => {
    if (!authUser?.id) return null;
    const hit = (membersQuery.data || []).find((m) => m.user_id === authUser.id);
    return hit?.member_id ?? null;
  }, [authUser?.id, membersQuery.data]);

  const tasksQuery = useQuery({
    queryKey: ["user-checkin-tasks", platform || "", memberId ?? null],
    queryFn: async () => {
      const pageSize = 100;
      const first = await fetchUserCheckinTasks({
        platform: platform || null,
        member_id: memberId ?? null,
        page: 1,
        page_size: pageSize,
      });
      const items = [...(first.items || [])];
      const totalPages = Math.max(1, Math.ceil((first.total || 0) / pageSize));
      for (let p = 2; p <= totalPages; p += 1) {
        const next = await fetchUserCheckinTasks({
          platform: platform || null,
          member_id: memberId ?? null,
          page: p,
          page_size: pageSize,
        });
        items.push(...(next.items || []));
      }
      return { ...first, items, page: 1, page_size: items.length };
    },
    refetchInterval: 30_000,
  });

  const userGroups = useMemo(() => {
    // 任务调度只展示已开启的自动签到任务
    const enabled = (tasksQuery.data?.items || []).filter((t) => t.auto_checkin);
    return buildUserGroups(enabled, selfMemberId);
  }, [tasksQuery.data?.items, selfMemberId]);

  const pagedGroups = useMemo(() => {
    const start = (page - 1) * pageSize;
    return userGroups.slice(start, start + pageSize);
  }, [userGroups, page, pageSize]);

  const [expandedKeys, setExpandedKeys] = useState<Key[]>([]);
  useEffect(() => {
    setExpandedKeys(collectExpandKeys(pagedGroups));
  }, [pagedGroups]);

  const trigger = useMutation({
    mutationFn: ({
      jobId,
      member_id,
      game_code,
      role_uid,
    }: {
      jobId: string;
      member_id?: number | null;
      game_code?: string | null;
      role_uid?: string | null;
      taskKey?: string;
      roleLabel?: string;
    }) =>
      triggerScheduledJob(jobId, {
        member_id: member_id ?? null,
        game_code: game_code || null,
        role_uid: role_uid || null,
      }),
    onMutate: ({ taskKey }) => {
      if (taskKey) setTriggeringKey(taskKey);
    },
    onSuccess: (data, vars) => {
      void queryClient.invalidateQueries({ queryKey: ["user-checkin-tasks"] });
      const isRoleSync = Boolean(vars.game_code && vars.role_uid);
      if (isRoleSync) {
        setExchangeDialog({
          title: vars.roleLabel
            ? `执行原文 · ${vars.roleLabel}`
            : "执行原文",
          summary: data.summary || data.message,
          ok: data.ok,
          exchanges: data.exchanges || [],
        });
        return;
      }
      message.success(data.message || "已提交执行");
    },
    onError: (e: unknown) => message.error(apiError(e, "执行失败")),
    onSettled: () => setTriggeringKey(null),
  });

  const scheduleCols = buildCheckinTaskScheduleColumns<ScheduleRow>({
    isLeaf: (row) => row.rowType === "role",
    getTask: (row) => row as RoleLeaf,
  });
  const awardCol = scheduleCols.find((c) => c.key === "today_summary");
  const beforeAwardCols = scheduleCols.filter((c) => c.key !== "today_summary");

  const actionsCol: ColumnsType<ScheduleRow>[number] = {
    title: "操作",
    key: "actions",
    width: 96,
    render: (_, row) => {
      // 固定宽度，避免 loading 图标把表格撑出横滚
      const btnWrap = (node: ReactNode) => (
        <div style={{ width: 80, whiteSpace: "nowrap" }}>{node}</div>
      );
      if (row.rowType === "role") {
        return btnWrap(
          <Button
            type="link"
            size="small"
            loading={triggeringKey === row.task_key}
            onClick={() =>
              trigger.mutate({
                jobId: row.job_id,
                member_id: row.member_id,
                game_code: row.game_code,
                role_uid: row.role_uid,
                taskKey: row.task_key,
                roleLabel: row.role_name || row.role_uid || undefined,
              })
            }
          >
            执行一次
          </Button>,
        );
      }
      if (row.rowType === "platform") {
        const firstRole = row.children
          .flatMap((c) => (c.rowType === "game" ? c.children : [c]))
          .find((r) => r.rowType === "role") as RoleLeaf | undefined;
        if (!firstRole) return null;
        return btnWrap(
          <Button
            type="link"
            size="small"
            loading={triggeringKey === `plat:${row.rowKey}`}
            onClick={() =>
              trigger.mutate({
                jobId: firstRole.job_id,
                member_id: row.member_id,
                taskKey: `plat:${row.rowKey}`,
              })
            }
          >
            执行一次
          </Button>,
        );
      }
      return null;
    },
  };

  const taskColumns: ColumnsType<ScheduleRow> = [
    {
      title: "用户 / 平台 / 游戏 / 角色",
      key: "name",
      width: 280,
      render: (_, row) => {
        if (row.rowType === "user") {
          return (
            <Space size={6} wrap>
              <Typography.Text strong>{row.user_label}</Typography.Text>
              {row.isSelf ? <Tag color="blue">我</Tag> : null}
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {row.taskCount} 个任务
              </Typography.Text>
            </Space>
          );
        }
        if (row.rowType === "platform") {
          return (
            <CheckinTreeNameLabel
              kind="platform"
              platform={row.platform}
              label={
                CHECKIN_PLATFORM_LABELS[row.platform] || row.platform_name
              }
            />
          );
        }
        if (row.rowType === "game") {
          return (
            <CheckinTreeNameLabel
              kind="game"
              platform={row.platform}
              gameCode={row.game_code}
              label={row.game_name}
              style={{ paddingLeft: 4 }}
            />
          );
        }
        if (row.game_code) {
          return (
            <Typography.Text type="secondary" style={{ paddingLeft: 8 }}>
              {row.role_name || row.role_uid}
            </Typography.Text>
          );
        }
        return (
          <Typography.Text type="secondary">整平台（未配置角色）</Typography.Text>
        );
      },
    },
    ...beforeAwardCols,
    ...(awardCol ? [awardCol] : []),
    actionsCol,
  ];

  const firstExchange = exchangeDialog?.exchanges?.[0];

  return (
    <div>
      <PageHeader
        title="任务调度"
        subtitle={
          <>
            按用户查看角色级签到任务（与「
            <Link to="/daily">我的日常</Link>
            」同一套数据）；当前登录用户排在最前。系统级开关与轮询间隔请到「任务配置」。
          </>
        }
      />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          marginBottom: 16,
        }}
      >
        <Space wrap size={8}>
          <Select
            style={{ width: 180 }}
            placeholder="平台"
            value={platform ?? ""}
            onChange={(value) => {
              setPlatform(value || undefined);
              setPage(1);
            }}
            options={PLATFORM_OPTIONS}
          />
          <Select
            style={{ width: 220 }}
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="全部用户"
            value={memberId}
            onChange={(value: number | null) => {
              setMemberId(value ?? undefined);
              setPage(1);
            }}
            options={(membersQuery.data || []).map((m) => ({
              value: m.member_id,
              label: m.label,
            }))}
            loading={membersQuery.isLoading}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            可按平台 / 用户筛选
          </Typography.Text>
        </Space>
        <Button
          icon={<ReloadOutlined />}
          loading={tasksQuery.isFetching}
          onClick={() => void tasksQuery.refetch()}
        >
          刷新
        </Button>
      </div>

      {tasksQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="加载签到任务失败"
          description={apiError(tasksQuery.error, "请稍后重试")}
        />
      ) : null}

      <Table<ScheduleRow>
        rowKey="rowKey"
        loading={tasksQuery.isLoading}
        columns={taskColumns}
        dataSource={pagedGroups}
        pagination={{
          current: page,
          pageSize,
          total: userGroups.length,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 位用户`,
          onChange: (nextPage, nextSize) => {
            setPage(nextPage);
            setPageSize(nextSize);
          },
        }}
        size="middle"
        expandable={{
          expandedRowKeys: expandedKeys,
          onExpandedRowsChange: (keys) => setExpandedKeys([...keys]),
          childrenColumnName: "children",
          indentSize: 20,
        }}
        rowClassName={(row) =>
          row.rowType === "user" ? "jobs-user-group-row" : ""
        }
      />

      <Modal
        open={Boolean(exchangeDialog)}
        title={exchangeDialog?.title || "执行原文"}
        onCancel={() => setExchangeDialog(null)}
        onOk={() => setExchangeDialog(null)}
        cancelButtonProps={{ style: { display: "none" } }}
        okText="关闭"
        width={720}
        destroyOnClose
      >
        {exchangeDialog ? (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            {exchangeDialog.summary ? (
              <Alert
                type={
                  exchangeDialog.ok === false
                    ? "error"
                    : exchangeDialog.ok
                      ? "success"
                      : "info"
                }
                showIcon
                message={exchangeDialog.summary}
              />
            ) : null}
            {firstExchange ? (
              <>
                <div>
                  <Space
                    style={{
                      width: "100%",
                      justifyContent: "space-between",
                      marginBottom: 8,
                    }}
                  >
                    <Typography.Text strong>请求</Typography.Text>
                    {firstExchange.upstream_request ? (
                      <Typography.Text
                        copyable={{ text: firstExchange.upstream_request }}
                        type="secondary"
                        style={{ fontSize: 12 }}
                      >
                        复制
                      </Typography.Text>
                    ) : null}
                  </Space>
                  <pre style={preStyle}>
                    {firstExchange.upstream_request || "（无请求原文）"}
                  </pre>
                </div>
                <div>
                  <Space
                    style={{
                      width: "100%",
                      justifyContent: "space-between",
                      marginBottom: 8,
                    }}
                  >
                    <Typography.Text strong>响应</Typography.Text>
                    {firstExchange.upstream_response ? (
                      <Typography.Text
                        copyable={{ text: firstExchange.upstream_response }}
                        type="secondary"
                        style={{ fontSize: 12 }}
                      >
                        复制
                      </Typography.Text>
                    ) : null}
                  </Space>
                  <pre style={preStyle}>
                    {firstExchange.upstream_response || "（无响应原文）"}
                  </pre>
                </div>
              </>
            ) : (
              <Alert
                type="warning"
                showIcon
                message="本次未捕获到上游 HTTP 原文"
                description="可能未实际打到上游，或该平台未写入 exchange。"
              />
            )}
          </Space>
        ) : null}
      </Modal>
    </div>
  );
}
