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
import { useState } from "react";
import {
  fetchJobCheckinLogs,
  fetchJobFilterMembers,
  fetchUserCheckinTasks,
  triggerScheduledJob,
  type CheckinLogItem,
  type UserCheckinTask,
} from "@/api/client";

const PLATFORM_OPTIONS = [
  { value: "", label: "全部平台" },
  { value: "skland", label: "森空岛" },
  { value: "taygedo", label: "塔吉多" },
  { value: "exilium", label: "追放" },
  { value: "kujiequ", label: "库街区" },
];

const PLATFORM_LABELS: Record<string, string> = {
  skland: "森空岛",
  taygedo: "塔吉多",
  exilium: "追放",
  kujiequ: "库街区",
};


function runStatusTag(status?: string | null) {
  if (!status) return <Typography.Text type="secondary">-</Typography.Text>;
  if (status === "ok" || status === "success") {
    return <Tag color="success">成功</Tag>;
  }
  if (status === "running") return <Tag color="processing">运行中</Tag>;
  if (status === "error" || status === "fail" || status === "failed") {
    return <Tag color="error">失败</Tag>;
  }
  return <Tag>{status}</Tag>;
}

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

export default function ScheduledJobsPage() {
  const queryClient = useQueryClient();
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

  const tasksQuery = useQuery({
    queryKey: [
      "user-checkin-tasks",
      platform || "",
      memberId ?? null,
      page,
      pageSize,
    ],
    queryFn: () =>
      fetchUserCheckinTasks({
        platform: platform || null,
        member_id: memberId ?? null,
        page,
        page_size: pageSize,
      }),
    refetchInterval: 30_000,
  });

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

  const taskColumns: ColumnsType<UserCheckinTask> = [
    {
      title: "用户",
      dataIndex: "user_label",
      width: 160,
      render: (v: string) => <Typography.Text strong>{v}</Typography.Text>,
    },
    {
      title: "平台",
      dataIndex: "platform",
      width: 140,
      render: (v: string, row) =>
        PLATFORM_LABELS[v] || row.platform_name || v,
    },
    {
      title: "签到时间",
      key: "schedule",
      width: 110,
      render: (_, row) => (
        <Typography.Text>
          {formatCheckinTime(row.checkin_hour, row.checkin_minute)}
        </Typography.Text>
      ),
    },
    {
      title: "自动签到",
      dataIndex: "auto_checkin",
      width: 100,
      align: "center",
      render: (v: boolean) =>
        v ? <Tag color="success">开启</Tag> : <Tag>关闭</Tag>,
    },
    {
      title: "上次签到",
      key: "last",
      width: 200,
      render: (_, row) => (
        <div style={{ lineHeight: 1.45 }}>
          {lastCheckinTag(row)}
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12, display: "block" }}
          >
            {row.last_checkin_at || row.last_checkin_date || "-"}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      fixed: "right",
      render: (_, row) => (
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
      render: (v: string) => runStatusTag(v),
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
            系统级开关与轮询间隔请到「任务配置」
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

      <Table
        rowKey="task_key"
        loading={tasksQuery.isLoading}
        columns={taskColumns}
        dataSource={tasksQuery.data?.items || []}
        pagination={{
          current: page,
          pageSize,
          total: tasksQuery.data?.total || 0,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条任务`,
          onChange: (nextPage, nextSize) => {
            setPage(nextPage);
            setPageSize(nextSize);
          },
        }}
        size="middle"
        scroll={{ x: 1100 }}
      />

      <Modal
        title={
          runsTask
            ? `执行记录 · ${runsTask.platform_name} · ${runsTask.user_label}`
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
