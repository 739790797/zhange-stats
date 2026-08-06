import { ReloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  Modal,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";
import {
  fetchMyDailyTaskLogs,
  fetchMyDailyTasks,
  type CheckinLogItem,
  type UserCheckinTask,
} from "@/api/client";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";

const PLATFORM_LABELS: Record<string, string> = {
  skland: "森空岛",
  taygedo: "塔吉多",
  exilium: "追放",
  kujiequ: "库街区",
};

function formatCheckinTime(hour: number, minute: number) {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function lastCheckinTag(task: UserCheckinTask) {
  if (task.last_checkin_ok === true) {
    return <Tag color="success">成功</Tag>;
  }
  if (task.last_checkin_ok === false) {
    return <Tag color="error">失败</Tag>;
  }
  return <Tag>未执行</Tag>;
}

export default function MyDailyPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [runsTask, setRunsTask] = useState<UserCheckinTask | null>(null);
  const [runsPage, setRunsPage] = useState(1);
  const [runsPageSize, setRunsPageSize] = useState(20);

  const tasksQuery = useQuery({
    queryKey: ["my-daily-tasks", page, pageSize],
    queryFn: () =>
      fetchMyDailyTasks({
        page,
        page_size: pageSize,
      }),
    refetchInterval: 30_000,
  });

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

  const taskColumns: ColumnsType<UserCheckinTask> = [
    {
      title: "平台",
      dataIndex: "platform",
      width: 140,
      render: (v: string, row) =>
        PLATFORM_LABELS[v] || row.platform_name || v,
    },
    {
      title: "日常时间",
      key: "schedule",
      width: 110,
      render: (_, row) => (
        <Typography.Text>
          {formatCheckinTime(row.checkin_hour, row.checkin_minute)}
        </Typography.Text>
      ),
    },
    {
      title: "自动执行",
      dataIndex: "auto_checkin",
      width: 100,
      align: "center",
      render: (v: boolean) =>
        v ? <Tag color="success">开启</Tag> : <Tag>关闭</Tag>,
    },
    {
      title: "上次结果",
      key: "last",
      width: 220,
      render: (_, row) => (
        <div style={{ lineHeight: 1.45 }}>
          {lastCheckinTag(row)}
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12, display: "block" }}
          >
            {row.last_checkin_at || row.last_checkin_date || "-"}
          </Typography.Text>
          {row.last_checkin_summary ? (
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: "block" }}
              ellipsis
            >
              {row.last_checkin_summary}
            </Typography.Text>
          ) : null}
        </div>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 110,
      fixed: "right",
      render: (_, row) => (
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
      ),
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
        查看已绑定平台的日常任务时间、自动开关与最近执行结果。修改时间请到各平台页。
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
        rowKey="task_key"
        loading={tasksQuery.isLoading}
        columns={taskColumns}
        dataSource={tasksQuery.data?.items || []}
        locale={{ emptyText: "暂无已绑定的日常任务平台" }}
        pagination={{
          current: page,
          pageSize,
          total: tasksQuery.data?.total || 0,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (nextPage, nextSize) => {
            setPage(nextPage);
            setPageSize(nextSize);
          },
        }}
        size="middle"
        scroll={{ x: 780 }}
      />

      <Modal
        title={
          runsTask
            ? `执行记录 · ${PLATFORM_LABELS[runsTask.platform] || runsTask.platform_name}`
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
