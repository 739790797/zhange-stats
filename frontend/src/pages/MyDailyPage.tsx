import { ReloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Modal,
  Table,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState, type Key } from "react";
import { Link } from "react-router-dom";
import {
  fetchMyDailyTaskLogs,
  fetchMyDailyTasks,
  type CheckinLogItem,
  type UserCheckinTask,
} from "@/api/client";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import {
  CHECKIN_PLATFORM_LABELS,
  CHECKIN_PLATFORM_ORDER,
  buildCheckinTaskScheduleColumns,
} from "@/components/checkinTaskDisplay";
import { isAdminUser } from "@/lib/isAdminUser";
import { useAuthStore } from "@/stores/authStore";

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
  children: Array<GameGroupRow | RoleLeaf>;
};

type DailyRow = PlatformGroupRow | GameGroupRow | RoleLeaf;

function buildDailyTree(tasks: UserCheckinTask[]): PlatformGroupRow[] {
  const byPlatform = new Map<string, UserCheckinTask[]>();
  for (const task of tasks) {
    const list = byPlatform.get(task.platform) || [];
    list.push(task);
    byPlatform.set(task.platform, list);
  }

  const platforms = [
    ...CHECKIN_PLATFORM_ORDER.filter((p) => byPlatform.has(p)),
    ...[...byPlatform.keys()].filter(
      (p) => !CHECKIN_PLATFORM_ORDER.includes(p),
    ),
  ];

  return platforms.map((platform) => {
    const list = byPlatform.get(platform) || [];
    const platformName =
      CHECKIN_PLATFORM_LABELS[platform] || list[0]?.platform_name || platform;

    const withGame = list.filter((t) => t.game_code);
    const legacy = list.filter((t) => !t.game_code);

    const byGame = new Map<string, UserCheckinTask[]>();
    for (const task of withGame) {
      const gc = String(task.game_code);
      const gList = byGame.get(gc) || [];
      gList.push(task);
      byGame.set(gc, gList);
    }

    const gameChildren: GameGroupRow[] = [...byGame.entries()].map(
      ([gameCode, roles]) => ({
        rowKey: `game:${platform}:${gameCode}`,
        rowType: "game" as const,
        platform,
        game_code: gameCode,
        game_name: roles[0]?.game_name || gameCode,
        children: roles.map((t) => ({
          ...t,
          rowKey: t.task_key,
          rowType: "role" as const,
        })),
      }),
    );

    const legacyLeaves: RoleLeaf[] = legacy.map((t) => ({
      ...t,
      rowKey: t.task_key,
      rowType: "role" as const,
    }));

    return {
      rowKey: `platform:${platform}`,
      rowType: "platform" as const,
      platform,
      platform_name: platformName,
      children: [...gameChildren, ...legacyLeaves],
    };
  });
}

export default function MyDailyPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(user);
  const [runsTask, setRunsTask] = useState<UserCheckinTask | null>(null);
  const [runsPage, setRunsPage] = useState(1);
  const [runsPageSize, setRunsPageSize] = useState(20);
  const [expandedKeys, setExpandedKeys] = useState<Key[]>([]);

  const tasksQuery = useQuery({
    queryKey: ["my-daily-tasks"],
    queryFn: async () => {
      const pageSize = 100;
      const first = await fetchMyDailyTasks({ page: 1, page_size: pageSize });
      const items = [...first.items];
      const totalPages = Math.max(1, Math.ceil(first.total / pageSize));
      for (let p = 2; p <= totalPages; p += 1) {
        const next = await fetchMyDailyTasks({ page: p, page_size: pageSize });
        items.push(...next.items);
      }
      return { ...first, items, page: 1, page_size: items.length };
    },
    refetchInterval: 30_000,
  });

  const treeData = useMemo(
    () => buildDailyTree(tasksQuery.data?.items || []),
    [tasksQuery.data?.items],
  );

  useEffect(() => {
    const keys: Key[] = [];
    for (const plat of treeData) {
      keys.push(plat.rowKey);
      for (const child of plat.children) {
        if (child.rowType === "game") keys.push(child.rowKey);
      }
    }
    setExpandedKeys(keys);
  }, [treeData]);

  const checkinLogsQuery = useQuery({
    queryKey: [
      "my-daily-task-logs",
      runsTask?.platform || "",
      runsPage,
      runsPageSize,
    ],
    queryFn: () =>
      fetchMyDailyTaskLogs({
        platform: runsTask!.platform,
        page: runsPage,
        page_size: runsPageSize,
      }),
    enabled: Boolean(runsTask),
  });

  const taskColumns: ColumnsType<DailyRow> = [
    {
      title: "平台 / 游戏 / 角色",
      key: "name",
      width: 280,
      render: (_, row) => {
        if (row.rowType === "platform") {
          return (
            <Typography.Text strong>
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
    ...buildCheckinTaskScheduleColumns<DailyRow>({
      isLeaf: (row) => row.rowType === "role",
      getTask: (row) => row as RoleLeaf,
    }),
    {
      title: "操作",
      key: "actions",
      width: 110,
      fixed: "right",
      render: (_, row) => {
        if (row.rowType === "game") return null;
        const task: UserCheckinTask =
          row.rowType === "platform"
            ? {
                task_key: row.rowKey,
                job_id: "",
                platform: row.platform,
                platform_name: row.platform_name,
                member_id: 0,
                user_label: "",
                auto_checkin: false,
                checkin_hour: 0,
                checkin_minute: 0,
              }
            : row;
        return (
          <Button
            type="link"
            size="small"
            onClick={() => {
              setRunsPage(1);
              setRunsTask(task);
            }}
          >
            执行记录
          </Button>
        );
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
      render: (_, row) => row.awards_text || row.message || "-",
    },
  ];

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>
        我的日常
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        按平台 → 游戏 → 角色查看是否启用与计划时间。修改请到各平台签到页。
        {isAdmin ? (
          <>
            {" "}
            管理端可在{" "}
            <Link to="/settings/jobs">任务调度</Link>{" "}
            查看全部用户（同一套角色任务数据）。
          </>
        ) : null}
      </Typography.Paragraph>

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
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
          message="加载日常任务失败"
          description={apiError(tasksQuery.error, "请稍后重试")}
        />
      ) : null}

      <Table
        rowKey="rowKey"
        loading={tasksQuery.isLoading}
        columns={taskColumns}
        dataSource={treeData}
        expandable={{
          expandedRowKeys: expandedKeys,
          onExpandedRowsChange: (keys) => setExpandedKeys([...keys]),
        }}
        locale={{ emptyText: "暂无已绑定的日常任务平台" }}
        pagination={false}
        size="middle"
        scroll={{ x: 1100 }}
      />

      <Modal
        title={
          runsTask
            ? `执行记录 · ${CHECKIN_PLATFORM_LABELS[runsTask.platform] || runsTask.platform_name}${
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
          dataSource={
            runsTask?.role_uid
              ? (checkinLogsQuery.data?.items || []).filter(
                  (row) =>
                    row.role_uid === runsTask.role_uid &&
                    (!runsTask.game_code ||
                      row.game_code === runsTask.game_code),
                )
              : checkinLogsQuery.data?.items || []
          }
          size="small"
          pagination={{
            current: runsPage,
            pageSize: runsPageSize,
            total: runsTask?.role_uid
              ? undefined
              : checkinLogsQuery.data?.total || 0,
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
