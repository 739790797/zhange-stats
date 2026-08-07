import { useQuery } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Alert, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState, type Key } from "react";
import {
  fetchMyDailyTasks,
  type UserCheckinTask,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import {
  CHECKIN_PLATFORM_LABELS,
  CHECKIN_PLATFORM_ORDER,
  CheckinTreeNameLabel,
  buildCheckinTaskScheduleColumns,
  communityGameRank,
} from "@/components/checkinTaskDisplay";

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

    const gameChildren: GameGroupRow[] = [...byGame.entries()]
      .sort(
        ([a], [b]) =>
          communityGameRank(a) - communityGameRank(b) || a.localeCompare(b),
      )
      .map(([gameCode, roles]) => ({
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
      }));

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
  const [expandedKeys, setExpandedKeys] = useState<Key[]>([]);

  const tasksQuery = useQuery({
    queryKey: ["my-daily-tasks"],
    queryFn: async () => {
      const pageSize = 100;
      const first = await fetchMyDailyTasks({ page: 1, page_size: pageSize });
      const items = [...(first.items || [])];
      const totalPages = Math.max(1, Math.ceil((first.total || 0) / pageSize));
      for (let p = 2; p <= totalPages; p += 1) {
        const next = await fetchMyDailyTasks({ page: p, page_size: pageSize });
        items.push(...(next.items || []));
      }
      return { ...first, items, page: 1, page_size: items.length };
    },
    refetchInterval: 30_000,
  });

  const treeData = useMemo(() => {
    // 只读展示已加入本站的角色（角色管理在个人中心）
    const included = (tasksQuery.data?.items || []).filter(
      (t) => t.included !== false,
    );
    return buildDailyTree(included);
  }, [tasksQuery.data?.items]);

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

  const taskColumns: ColumnsType<DailyRow> = [
    {
      title: "平台 / 游戏 / 角色",
      key: "name",
      width: 280,
      render: (_, row) => {
        if (row.rowType === "platform") {
          return (
            <CheckinTreeNameLabel
              kind="platform"
              platform={row.platform}
              label={
                CHECKIN_PLATFORM_LABELS[row.platform] || row.platform_name
              }
              strong
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
    ...buildCheckinTaskScheduleColumns<DailyRow>({
      isLeaf: (row) => row.rowType === "role",
      getTask: (row) => row as RoleLeaf,
    }),
  ];

  return (
    <div>
      <PageHeader title="我的日常" />

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
        locale={{ emptyText: "暂无已加入本站的角色" }}
        pagination={false}
        size="middle"
        scroll={{ x: 1000 }}
      />
    </div>
  );
}
