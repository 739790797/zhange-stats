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
import { useEffect, useMemo, useState } from "react";
import type { Key } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import { CheckinAwardsLine } from "@/components/CheckinAwardsLine";
import {
  CHECKIN_PLATFORM_LABELS,
  buildCheckinTaskScheduleColumns,
  platformRank,
} from "@/components/checkinTaskDisplay";
import {
  fetchJobCheckinLogs,
  fetchJobFilterMembers,
  fetchUserCheckinTasks,
  triggerScheduledJob,
  type CheckinLogItem,
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
      .sort(([a], [b]) => a.localeCompare(b))
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

export default function ScheduledJobsPage() {
  const queryClient = useQueryClient();
  const authUser = useAuthStore((s) => s.user);
  const [platform, setPlatform] = useState<string | undefined>();
  const [memberId, setMemberId] = useState<number | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [triggeringKey, setTriggeringKey] = useState<string | null>(null);
  const [runsTask, setRunsTask] = useState<UserCheckinTask | null>(null);
  const [runsPage, setRunsPage] = useState(1);
  const [runsPageSize, setRunsPageSize] = useState(20);

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
      const items = [...first.items];
      const totalPages = Math.max(1, Math.ceil(first.total / pageSize));
      for (let p = 2; p <= totalPages; p += 1) {
        const next = await fetchUserCheckinTasks({
          platform: platform || null,
          member_id: memberId ?? null,
          page: p,
          page_size: pageSize,
        });
        items.push(...next.items);
      }
      return { ...first, items, page: 1, page_size: items.length };
    },
    refetchInterval: 30_000,
  });

  const userGroups = useMemo(
    () => buildUserGroups(tasksQuery.data?.items || [], selfMemberId),
    [tasksQuery.data?.items, selfMemberId],
  );

  const pagedGroups = useMemo(() => {
    const start = (page - 1) * pageSize;
    return userGroups.slice(start, start + pageSize);
  }, [userGroups, page, pageSize]);

  const [expandedKeys, setExpandedKeys] = useState<Key[]>([]);
  useEffect(() => {
    setExpandedKeys(collectExpandKeys(pagedGroups));
  }, [pagedGroups]);

  const checkinLogsQuery = useQuery({
    queryKey: [
      "job-checkin-logs",
      runsTask?.platform || "",
      runsTask?.member_id ?? null,
      runsPage,
      runsPageSize,
    ],
    queryFn: () =>
      fetchJobCheckinLogs({
        platform: runsTask!.platform,
        member_id: runsTask!.member_id,
        page: runsPage,
        page_size: runsPageSize,
      }),
    enabled: Boolean(runsTask),
  });

  const trigger = useMutation({
    mutationFn: ({
      jobId,
      member_id,
    }: {
      jobId: string;
      member_id?: number | null;
      taskKey?: string;
    }) => triggerScheduledJob(jobId, { member_id }),
    onMutate: ({ taskKey }) => {
      if (taskKey) setTriggeringKey(taskKey);
    },
    onSuccess: (data) => {
      message.success(data.message || "已提交执行");
      void queryClient.invalidateQueries({ queryKey: ["user-checkin-tasks"] });
      if (runsTask) {
        void queryClient.invalidateQueries({ queryKey: ["job-checkin-logs"] });
      }
    },
    onError: (e: unknown) => message.error(apiError(e, "执行失败")),
    onSettled: () => setTriggeringKey(null),
  });

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
            <Typography.Text>
              {CHECKIN_PLATFORM_LABELS[row.platform] || row.platform_name}
            </Typography.Text>
          );
        }
        if (row.rowType === "game") {
          return (
            <Typography.Text style={{ paddingLeft: 4 }}>
              {row.game_name}
            </Typography.Text>
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
    ...buildCheckinTaskScheduleColumns<ScheduleRow>({
      isLeaf: (row) => row.rowType === "role",
      getTask: (row) => row as RoleLeaf,
    }),
    {
      title: "操作",
      key: "actions",
      width: 180,
      fixed: "right",
      render: (_, row) => {
        if (row.rowType === "role") {
          return (
            <Space size={4} wrap>
              <Button
                type="link"
                size="small"
                loading={triggeringKey === row.task_key}
                onClick={() =>
                  trigger.mutate({
                    jobId: row.job_id,
                    member_id: row.member_id,
                    taskKey: row.task_key,
                  })
                }
              >
                执行一次
              </Button>
              <Button
                type="link"
                size="small"
                onClick={() => {
                  setRunsPage(1);
                  setRunsTask(row);
                }}
              >
                执行记录
              </Button>
            </Space>
          );
        }
        if (row.rowType === "platform") {
          const firstRole = row.children
            .flatMap((c) => (c.rowType === "game" ? c.children : [c]))
            .find((r) => r.rowType === "role") as RoleLeaf | undefined;
          if (!firstRole) return null;
          return (
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
            </Button>
          );
        }
        return null;
      },
    },
  ];

  const checkinColumns: ColumnsType<CheckinLogItem> = [
    {
      title: "时间",
      dataIndex: "checked_at",
      width: 170,
      render: (v?: string | null) => v || "-",
    },
    {
      title: "角色",
      key: "role",
      width: 200,
      render: (_, row) =>
        `${row.role_name || row.role_uid}（${row.game_name || row.game_code}）`,
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (v: string, row) => (
        <CheckinStatusTag status={v} statusLabel={row.status_label} />
      ),
    },
    {
      title: "摘要",
      key: "summary",
      ellipsis: true,
      render: (_, row) => (
        <CheckinAwardsLine
          awards={row.awards}
          awardsText={row.awards_text || null}
          fallback="-"
        />
      ),
    },
  ];

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
        scroll={{ x: 1280 }}
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
        title={
          runsTask
            ? `执行记录 · ${CHECKIN_PLATFORM_LABELS[runsTask.platform] || runsTask.platform_name} · ${runsTask.user_label}${
                runsTask.role_name || runsTask.role_uid
                  ? ` · ${runsTask.role_name || runsTask.role_uid}`
                  : ""
              }`
            : "执行记录"
        }
        open={Boolean(runsTask)}
        onCancel={() => setRunsTask(null)}
        footer={null}
        width={960}
        destroyOnClose
      >
        <Table
          rowKey={(row) => `${row.platform}-${row.id}`}
          loading={checkinLogsQuery.isLoading || checkinLogsQuery.isFetching}
          columns={checkinColumns}
          dataSource={checkinLogsQuery.data?.items || []}
          size="small"
          pagination={{
            current: runsPage,
            pageSize: runsPageSize,
            total: checkinLogsQuery.data?.total || 0,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (nextPage, nextSize) => {
              setRunsPage(nextPage);
              setRunsPageSize(nextSize);
            },
          }}
        />
      </Modal>
    </div>
  );
}
