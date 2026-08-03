import { ReloadOutlined, ScheduleOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { fetchScheduledJobs, type ScheduledJob } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

function statusTag(job: ScheduledJob) {
  if (job.registered) {
    return <Tag color="success">已注册</Tag>;
  }
  if (job.config_enabled === false) {
    return <Tag>已关闭</Tag>;
  }
  if (job.config_enabled === true) {
    return <Tag color="warning">未启动</Tag>;
  }
  return <Tag>未注册</Tag>;
}

function lastRunTag(status?: string | null) {
  if (!status) return <Typography.Text type="secondary">-</Typography.Text>;
  if (status === "ok") return <Tag color="success">成功</Tag>;
  if (status === "running") return <Tag color="processing">运行中</Tag>;
  if (status === "error") return <Tag color="error">失败</Tag>;
  return <Tag>{status}</Tag>;
}

export default function ScheduledJobsPage() {
  const jobsQuery = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: fetchScheduledJobs,
    refetchInterval: 30_000,
  });

  const columns: ColumnsType<ScheduledJob> = [
    {
      title: "任务",
      dataIndex: "name",
      key: "name",
      render: (_, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{row.name}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {row.id}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: "说明",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "状态",
      key: "status",
      width: 100,
      render: (_, row) => statusTag(row),
    },
    {
      title: "调度",
      key: "schedule",
      width: 200,
      render: (_, row) =>
        row.schedule ? (
          <Space direction="vertical" size={0}>
            <span>{row.schedule}</span>
            {row.trigger_type ? (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {row.trigger_type}
              </Typography.Text>
            ) : null}
          </Space>
        ) : (
          <Typography.Text type="secondary">-</Typography.Text>
        ),
    },
    {
      title: "下次执行",
      dataIndex: "next_run_at",
      key: "next_run_at",
      width: 170,
      render: (v: string | null | undefined) =>
        v || <Typography.Text type="secondary">-</Typography.Text>,
    },
    {
      title: "最近执行",
      key: "last_run",
      width: 220,
      render: (_, row) => {
        const last = row.last_run;
        if (!last) {
          return <Typography.Text type="secondary">暂无记录</Typography.Text>;
        }
        return (
          <Space direction="vertical" size={0}>
            <Space size={6}>
              {lastRunTag(last.status)}
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {last.started_at || "-"}
              </Typography.Text>
            </Space>
            {last.message ? (
              <Typography.Text
                type="secondary"
                ellipsis
                style={{ fontSize: 12, maxWidth: 200 }}
                title={last.message}
              >
                {last.message}
              </Typography.Text>
            ) : null}
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <PageHeader
        title="定时任务"
        subtitle="查看系统当前已注册与配置中的后台定时任务"
        extra={
          <Space>
            <Link to="/settings/users">用户管理</Link>
            <Link to="/settings/email">邮箱设置</Link>
            <Button
              icon={<ReloadOutlined />}
              loading={jobsQuery.isFetching}
              onClick={() => jobsQuery.refetch()}
            >
              刷新
            </Button>
          </Space>
        }
      />

      {jobsQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="加载定时任务失败"
          description={
            (jobsQuery.error as { response?: { data?: { detail?: string } } })
              ?.response?.data?.detail ||
            (jobsQuery.error as Error)?.message ||
            "请稍后重试"
          }
        />
      ) : null}

      <Alert
        type="info"
        showIcon
        icon={<ScheduleOutlined />}
        style={{ marginBottom: 16 }}
        message={
          jobsQuery.data
            ? `调度器${jobsQuery.data.scheduler_running ? "运行中" : "未运行"} · 时区 ${jobsQuery.data.timezone}`
            : "加载中…"
        }
        description="已关闭的任务不会注册到调度器；「未启动」表示配置开启但当前进程未成功注册。"
      />

      <Table
        rowKey="id"
        loading={jobsQuery.isLoading}
        columns={columns}
        dataSource={jobsQuery.data?.jobs || []}
        pagination={false}
        size="middle"
      />
    </div>
  );
}
