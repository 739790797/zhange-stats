import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Descriptions,
  Modal,
  Progress,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchJobRuns } from "@/api/client";
import { apiError } from "@/lib/apiError";
import {
  JOB_RUN_WATCH_TIMEOUT_MS,
  isJobRunFinished,
  jobRunAlertType,
  jobRunDomainLabel,
  jobRunDomainModeLabel,
  jobRunDomainProgressText,
  jobRunSyncedText,
  jobRunDomainStatusColor,
  jobRunDomainStatusLabel,
  jobRunDownloadProgress,
  jobRunFreshnessSummary,
  jobRunPhaseLabel,
  jobRunProgressPercent,
  jobRunProgressRows,
  jobRunStatEntries,
  jobRunStatusLabel,
  jobRunSummaryText,
  jobRunWatchPollMs,
  parseJobRunMessage,
  pickWatchedJobRun,
  type JobRunDomainRow,
  type JobRunWatch,
} from "@/lib/jobRunResult";

const preStyle = {
  margin: 0,
  padding: 12,
  maxHeight: 240,
  overflow: "auto" as const,
  background: "rgba(0,0,0,0.04)",
  borderRadius: 6,
  fontSize: 12,
  whiteSpace: "pre-wrap" as const,
  wordBreak: "break-all" as const,
};

const domainColumns: ColumnsType<JobRunDomainRow> = [
  {
    title: "栏目",
    dataIndex: "id",
    ellipsis: true,
    render: (_value, row) => jobRunDomainLabel(row.id),
  },
  {
    title: "模式",
    dataIndex: "mode",
    width: 72,
    render: (_value, row) => jobRunDomainModeLabel(row.mode) || "—",
  },
  {
    title: "状态",
    dataIndex: "status",
    width: 88,
    render: (_value, row) => (
      <Tag color={jobRunDomainStatusColor(row.status)} style={{ marginInlineEnd: 0 }}>
        {jobRunDomainStatusLabel(row.status)}
      </Tag>
    ),
  },
  {
    title: "进度",
    key: "progress",
    ellipsis: true,
    render: (_value, row) => jobRunDomainProgressText(row) || "—",
  },
  {
    title: "落库",
    dataIndex: "syncedAt",
    ellipsis: true,
    render: (_value, row) => {
      const synced = jobRunSyncedText(row);
      if (synced) return synced;
      if (row.error) {
        return (
          <Typography.Text type="danger" style={{ fontSize: 12 }}>
            {row.error}
          </Typography.Text>
        );
      }
      return "—";
    },
  },
];

export function JobRunResultModal({
  watch,
  onClose,
}: {
  watch: JobRunWatch | null;
  onClose: () => void;
}) {
  const open = Boolean(watch);
  const startedAtRef = useRef(Date.now());
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!watch) {
      setTimedOut(false);
      return;
    }
    startedAtRef.current = Date.now();
    setTimedOut(false);
    const timer = window.setTimeout(
      () => setTimedOut(true),
      JOB_RUN_WATCH_TIMEOUT_MS,
    );
    return () => window.clearTimeout(timer);
  }, [watch]);

  const query = useQuery({
    queryKey: ["job-run-watch", watch?.jobId, watch?.sinceRunId],
    queryFn: () => fetchJobRuns(watch!.jobId, { page: 1, page_size: 5 }),
    enabled: open && Boolean(watch?.jobId),
    refetchOnWindowFocus: false,
    refetchInterval: (q) => {
      const run = pickWatchedJobRun(
        q.state.data?.items,
        watch?.sinceRunId ?? 0,
        watch?.acceptedAt,
      );
      return jobRunWatchPollMs({ run, startedAt: startedAtRef.current });
    },
  });

  const run = pickWatchedJobRun(
    query.data?.items,
    watch?.sinceRunId ?? 0,
    watch?.acceptedAt,
  );
  const finished = isJobRunFinished(run?.status);
  const parsed = parseJobRunMessage(run?.message);
  const domainRows = jobRunProgressRows(run);
  const download = jobRunDownloadProgress(run?.stats);
  const stats = jobRunStatEntries(run?.stats, { omitDownload: Boolean(download) });
  const percent = jobRunProgressPercent(run?.stats);
  const running = run?.status === "running";
  const stalled = timedOut && !finished && !running;
  const waiting = open && !finished && !stalled;
  const phaseLabel = jobRunPhaseLabel(
    run?.stats?.phase == null ? "" : String(run.stats.phase),
  );
  const progressStatus = useMemo(() => {
    if (run?.status === "error") return "exception" as const;
    if (finished) return "success" as const;
    if (waiting) return "active" as const;
    return "normal" as const;
  }, [finished, run?.status, waiting]);

  return (
    <Modal
      open={open}
      title={watch ? `${watch.jobName} · 执行结果` : "执行结果"}
      onCancel={onClose}
      onOk={onClose}
      cancelButtonProps={{ style: { display: "none" } }}
      okText="关闭"
      width={880}
      destroyOnClose
    >
      {watch ? (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {query.isError ? (
            <Alert
              type="error"
              showIcon
              message="无法读取执行记录"
              description={apiError(query.error, "请稍后重试")}
            />
          ) : null}
          <Alert
            type={
              stalled
                ? "warning"
                : jobRunAlertType(run?.status || "running")
            }
            showIcon
            message={
              stalled
                ? "仍未拿到结束记录"
                : jobRunSummaryText(run, watch.acceptedMessage)
            }
            description={
              stalled
                ? "任务可能还在跑，或这次没有写入执行记录。可稍后刷新任务配置再看。"
                : run
                  ? [
                      jobRunStatusLabel(run.status),
                      phaseLabel,
                      domainRows.length
                        ? jobRunFreshnessSummary(domainRows)
                        : parsed?.kind === "domains"
                          ? jobRunFreshnessSummary(parsed.domains)
                          : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")
                  : "已接收执行，正在等待任务开始…"
            }
          />
          {percent != null ? (
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                更新进度
                {phaseLabel ? ` · ${phaseLabel}` : ""}
              </Typography.Text>
              <Progress
                percent={percent}
                status={progressStatus}
                style={{ display: "block", marginTop: 4 }}
              />
            </div>
          ) : waiting ? (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <Spin />
            </div>
          ) : null}
          {download ? (
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                下载进度
                {download.file ? ` · ${download.file}` : ""}
                {download.filesText ? ` · ${download.filesText}` : ""}
              </Typography.Text>
              {download.filePercent != null ? (
                <Progress
                  percent={download.filePercent}
                  status={running ? "active" : "normal"}
                  format={() => download.bytesText || `${download.filePercent}%`}
                  style={{ display: "block", marginTop: 4 }}
                />
              ) : download.bytesText ? (
                <Typography.Text style={{ display: "block", marginTop: 4 }}>
                  {download.bytesText}
                </Typography.Text>
              ) : running ? (
                <div style={{ marginTop: 8 }}>
                  <Spin size="small" />
                </div>
              ) : null}
            </div>
          ) : null}
          {domainRows.length ? (
            <Table<JobRunDomainRow>
              size="small"
              pagination={false}
              rowKey={(row, index) => `${row.mode || ""}:${row.id}:${index}`}
              columns={domainColumns}
              dataSource={domainRows}
            />
          ) : null}
          {parsed?.kind === "json" ? (
            <pre style={preStyle}>{JSON.stringify(parsed.value, null, 2)}</pre>
          ) : null}
          {stats.length ? (
            <Descriptions column={2} size="small">
              {stats.map((row) => (
                <Descriptions.Item key={row.key} label={row.label}>
                  {row.value}
                </Descriptions.Item>
              ))}
            </Descriptions>
          ) : null}
        </Space>
      ) : null}
    </Modal>
  );
}
