import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Modal, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { fetchJobRuns, type JobRun } from "@/features/admin/api/jobsApi";
import { apiError } from "@/shared/api/apiError";
import { formatJobRunClock, jobRunStatusLabel } from "@/features/admin/model/jobRunResult";

function statusColor(status: string): string {
  if (status === "ok") return "success";
  if (status === "warning") return "warning";
  if (status === "error") return "error";
  if (status === "running") return "processing";
  return "default";
}

export function JobRunHistoryModal({
  job,
  onClose,
  onSelect,
}: {
  job: { id: string; name: string } | null;
  onClose: () => void;
  onSelect: (run: JobRun) => void;
}) {
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["job-run-history", job?.id, page],
    queryFn: () => fetchJobRuns(job!.id, { page, page_size: 10 }),
    enabled: Boolean(job),
    refetchOnWindowFocus: false,
  });

  useEffect(() => setPage(1), [job?.id]);

  const columns: ColumnsType<JobRun> = [
    {
      title: "开始时间",
      dataIndex: "started_at",
      width: 168,
      render: (value: string | null) => formatJobRunClock(value) || "—",
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 94,
      render: (status: string) => (
        <Tag color={statusColor(status)} style={{ margin: 0 }}>
          {jobRunStatusLabel(status)}
        </Tag>
      ),
    },
    {
      title: "摘要",
      dataIndex: "message",
      ellipsis: true,
      render: (value: string | null) => value || "—",
    },
    {
      title: "操作",
      key: "action",
      width: 82,
      render: (_value, row) => (
        <Button size="small" type="link" onClick={() => onSelect(row)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <Modal
      open={Boolean(job)}
      title={job ? `${job.name} · 执行记录` : "执行记录"}
      onCancel={onClose}
      footer={null}
      width={760}
      destroyOnClose
    >
      {query.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message="无法读取执行记录"
          description={apiError(query.error, "请稍后重试")}
        />
      ) : null}
      {!query.isLoading && !query.data?.items?.length && !query.isError ? (
        <Typography.Text type="secondary">暂无执行记录</Typography.Text>
      ) : null}
      <Table<JobRun>
        rowKey="id"
        size="small"
        loading={query.isLoading || query.isFetching}
        columns={columns}
        dataSource={query.data?.items || []}
        pagination={{
          current: page,
          pageSize: 10,
          total: query.data?.total || 0,
          showSizeChanger: false,
          onChange: setPage,
        }}
      />
    </Modal>
  );
}
