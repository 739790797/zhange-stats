import { useQuery } from "@tanstack/react-query";
import { Alert, Descriptions, Modal, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { fetchJobRuns } from "@/api/client";
import { apiError } from "@/lib/apiError";
import {
  JOB_RUN_WATCH_TIMEOUT_MS,
  isJobRunFinished,
  jobRunAlertType,
  jobRunFreshnessSummary,
  jobRunFreshnessText,
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
  const stats = jobRunStatEntries(run?.stats);
  const waiting = open && !finished && !timedOut;

  return (
    <Modal
      open={open}
      title={watch ? `${watch.jobName} · 执行结果` : "执行结果"}
      onCancel={onClose}
      onOk={onClose}
      cancelButtonProps={{ style: { display: "none" } }}
      okText="关闭"
      width={720}
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
              timedOut && !finished
                ? "warning"
                : jobRunAlertType(run?.status || "running")
            }
            showIcon
            message={
              timedOut && !finished
                ? "仍未拿到结束记录"
                : jobRunSummaryText(run, watch.acceptedMessage)
            }
            description={
              timedOut && !finished
                ? "任务可能还在跑，或这次没有写入执行记录。可稍后刷新任务配置再看。"
                : run
                  ? [
                      jobRunStatusLabel(run.status),
                      parsed?.kind === "domains"
                        ? jobRunFreshnessSummary(parsed.domains)
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")
                  : "已接收执行，正在等待任务开始…"
            }
          />
          {waiting ? (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <Spin />
            </div>
          ) : null}
          {parsed?.kind === "domains" && parsed.domains.length ? (
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              {parsed.domains.map((row, index) => (
                <DomainFreshnessRow
                  key={`${row.id}-${index}`}
                  row={row}
                />
              ))}
            </Space>
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

function DomainFreshnessRow({ row }: { row: JobRunDomainRow }) {
  const freshness = jobRunFreshnessText(row);
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        alignItems: "flex-start",
      }}
    >
      <Tag color={row.ok ? "success" : "error"} style={{ marginInlineEnd: 0 }}>
        {row.ok ? "成功" : "失败"}
      </Tag>
      <div style={{ minWidth: 0 }}>
        <Typography.Text>{row.label}</Typography.Text>
        {freshness ? (
          <Typography.Text
            type="secondary"
            style={{ display: "block", fontSize: 12 }}
          >
            {freshness}
          </Typography.Text>
        ) : null}
        {row.error ? (
          <Typography.Text
            type="danger"
            style={{ display: "block", fontSize: 12 }}
          >
            {row.error}
          </Typography.Text>
        ) : null}
      </div>
    </div>
  );
}
