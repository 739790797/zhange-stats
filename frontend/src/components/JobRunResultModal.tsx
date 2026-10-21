import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Descriptions,
  Modal,
  Progress,
  Space,
  Spin,
  Steps,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchJobRunEvents, fetchJobRuns, type JobRunLog } from "@/api/client";
import { apiError } from "@/lib/apiError";
import {
  JOB_RUN_WATCH_TIMEOUT_MS,
  isJobRunFinished,
  jobRunAlertType,
  jobRunCategory,
  jobRunDomainLabel,
  jobRunDomainModeLabel,
  jobRunDomainProgressText,
  jobRunDurationText,
  jobRunSyncedText,
  jobRunDomainStatusColor,
  jobRunDomainStatusLabel,
  jobRunDownloadProgress,
  jobRunFreshnessSummary,
  jobRunPhaseLabel,
  jobRunProgressPercent,
  jobRunProgressRows,
  jobRunResult,
  jobRunResultCounts,
  jobRunSteps,
  jobRunStatusLabel,
  jobRunSummaryText,
  jobRunWatchPollMs,
  parseJobRunMessage,
  pickWatchedJobRun,
  type JobRunDomainRow,
  type JobRunWatch,
} from "@/lib/jobRunResult";

const domainColumns: ColumnsType<JobRunDomainRow> = [
  {
    title: "数据域",
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
    title: "进度 / 上游时间",
    key: "progress",
    ellipsis: true,
    render: (_value, row) => jobRunDomainProgressText(row) || "—",
  },
  {
    title: "结果",
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

const CATEGORY_TITLES: Record<string, string> = {
  repository: "仓库同步结果",
  data_pipeline: "数据采集与入库结果",
  batch_sync: "批量同步结果",
  asset_sync: "模型与译文结果",
};

const COUNT_LABELS: Record<string, string> = {
  ok: "成功",
  failed: "失败",
  skipped: "跳过",
  total: "合计",
  operators: "干员数",
  updated: "已更新",
  unchanged: "未变化",
};

function resultText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

function statusForStep(status: string): "wait" | "process" | "finish" | "error" {
  if (status === "running") return "process";
  if (status === "success" || status === "warning" || status === "skipped") return "finish";
  if (status === "error") return "error";
  return "wait";
}

function stepStatusLabel(status: string): string {
  if (status === "running") return "进行中";
  if (status === "success") return "成功";
  if (status === "warning") return "部分成功";
  if (status === "error") return "失败";
  if (status === "skipped") return "跳过";
  return "等待";
}

export function JobRunResultModal({
  watch,
  onClose,
}: {
  watch: JobRunWatch | null;
  onClose: () => void;
}) {
  const open = Boolean(watch);
  const startedAtRef = useRef(Date.now());
  const cursorRef = useRef({ key: "", afterId: 0 });
  const seenLogIdsRef = useRef(new Set<number>());
  const logKeyRef = useRef("");
  const logContainerRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<JobRunLog[]>([]);
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!watch) {
      setTimedOut(false);
      return;
    }
    startedAtRef.current = Date.now();
    setTimedOut(false);
    const timer = window.setTimeout(() => setTimedOut(true), JOB_RUN_WATCH_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [watch]);

  const discoveryQuery = useQuery({
    queryKey: ["job-run-watch-discovery", watch?.jobId, watch?.sinceRunId],
    queryFn: () =>
      fetchJobRuns(watch!.jobId, {
        page: 1,
        page_size: 10,
      }),
    enabled: open && Boolean(watch?.jobId) && watch?.runId == null,
    refetchOnWindowFocus: false,
    refetchInterval: (q) => {
      const run = pickWatchedJobRun(
        q.state.data?.items,
        watch?.sinceRunId ?? 0,
        watch?.acceptedAt,
      );
      return jobRunWatchPollMs({ run });
    },
  });

  const discoveredRun = pickWatchedJobRun(
    discoveryQuery.data?.items,
    watch?.sinceRunId ?? 0,
    watch?.acceptedAt,
  );
  const activeRunId = watch?.runId ?? discoveredRun?.id;
  const activeRunKey = `${watch?.jobId || ""}:${activeRunId ?? ""}`;
  const eventsQuery = useQuery({
    queryKey: ["job-run-events", watch?.jobId, activeRunId],
    queryFn: async () => {
      const key = `${watch!.jobId}:${activeRunId}`;
      if (cursorRef.current.key !== key) {
        cursorRef.current = { key, afterId: 0 };
      }
      return fetchJobRunEvents(
        watch!.jobId,
        activeRunId!,
        cursorRef.current.afterId,
      );
    },
    enabled: open && Boolean(watch?.jobId) && activeRunId != null,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    refetchInterval: (q) => {
      const data = q.state.data;
      if (data && isJobRunFinished(data.run.status) && !data.has_more) {
        return false;
      }
      return 1000;
    },
  });

  useEffect(() => {
    cursorRef.current = { key: activeRunKey, afterId: 0 };
    logKeyRef.current = activeRunKey;
    seenLogIdsRef.current = new Set();
    setLogs([]);
  }, [activeRunKey]);

  useEffect(() => {
    const data = eventsQuery.data;
    if (!data || data.run.id !== activeRunId) return;
    if (logKeyRef.current !== activeRunKey) return;
    const fresh = (data.logs || []).filter((log) => {
      if (seenLogIdsRef.current.has(log.id)) return false;
      seenLogIdsRef.current.add(log.id);
      return true;
    });
    if (fresh.length) {
      setLogs((current) => [...current, ...fresh].slice(-10_000));
    }
    if (data.next_after_id > cursorRef.current.afterId) {
      cursorRef.current.afterId = data.next_after_id;
    }
  }, [activeRunId, activeRunKey, eventsQuery.data]);

  useEffect(() => {
    if (!logs.length || !logContainerRef.current) return;
    logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
  }, [logs.length]);

  const run = eventsQuery.data?.run ?? discoveredRun ?? null;
  const finished = isJobRunFinished(run?.status);
  const parsed = parseJobRunMessage(run?.message);
  const domainRows = jobRunProgressRows(run);
  const category = jobRunCategory(run?.stats, watch?.category);
  const steps = jobRunSteps(run?.stats);
  const result = jobRunResult(run?.stats);
  const resultCounts = jobRunResultCounts(run?.stats);
  const download = jobRunDownloadProgress(run?.stats);
  const percent = jobRunProgressPercent(run?.stats);
  const running = run?.status === "running";
  const waiting = open && !finished && !running;
  const stalled = timedOut && !finished;
  const phaseLabel = jobRunPhaseLabel(
    run?.stats?.phase == null ? "" : String(run.stats.phase),
  );
  const progressStatus = useMemo(() => {
    if (run?.status === "error") return "exception" as const;
    if (finished && run?.status !== "warning") return "success" as const;
    if (running || waiting) return "active" as const;
    return "normal" as const;
  }, [finished, run?.status, running, waiting]);

  const displayedSteps = useMemo(() => {
    if (steps.length) return steps;
    if (!run) return [];
    const status =
      run.status === "ok"
        ? "success"
        : run.status === "warning"
          ? "warning"
          : run.status === "error"
            ? "error"
            : run.status === "running"
              ? "running"
              : "waiting";
    return [
      {
        id: String(run.stats?.phase || "execute"),
        label: phaseLabel || "执行任务",
        status,
      },
    ];
  }, [phaseLabel, run, steps]);

  const detailTitle = category ? CATEGORY_TITLES[category] : "执行信息";
  const summary = jobRunSummaryText(run, watch?.acceptedMessage);
  const freshness =
    domainRows.length > 0
      ? jobRunFreshnessSummary(domainRows)
      : parsed?.kind === "domains"
        ? jobRunFreshnessSummary(parsed.domains)
        : null;

  return (
    <Modal
      open={open}
      title={watch ? `${watch.jobName} · 执行进度` : "执行进度"}
      onCancel={onClose}
      onOk={onClose}
      cancelButtonProps={{ style: { display: "none" } }}
      okText="关闭"
      width={880}
      destroyOnClose
    >
      {watch ? (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {discoveryQuery.isError || eventsQuery.isError ? (
            <Alert
              type="error"
              showIcon
              message="无法读取执行记录"
              description={apiError(eventsQuery.error || discoveryQuery.error, "请稍后重试")}
            />
          ) : null}
          <Alert
            type={stalled ? "warning" : jobRunAlertType(run?.status || "running")}
            showIcon
            message={stalled ? "暂未拿到结束记录" : summary}
            description={
              stalled
                ? "本次任务仍可能在后台运行；关闭弹窗不会中止任务。"
                : [
                    jobRunStatusLabel(run?.status || "queued"),
                    category ? CATEGORY_TITLES[category] || category : null,
                    freshness,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "已接收执行，正在等待任务开始…"
            }
          />

          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="状态">
              <Tag color={jobRunAlertType(run?.status || "queued")} style={{ margin: 0 }}>
                {jobRunStatusLabel(run?.status || "queued")}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="耗时">
              {jobRunDurationText(run)}
            </Descriptions.Item>
            <Descriptions.Item label="当前阶段" span={2}>
              {displayedSteps.find((step) => step.status === "running")?.label ||
                phaseLabel ||
                (run?.status === "queued" ? "等待任务启动" : "—")}
            </Descriptions.Item>
          </Descriptions>

          {displayedSteps.length ? (
            <div>
              <Typography.Text strong style={{ display: "block", marginBottom: 10 }}>
                执行步骤
              </Typography.Text>
              <Steps
                responsive
                size="small"
                current={Math.max(0, displayedSteps.findIndex((step) => step.status === "running"))}
                items={displayedSteps.map((step) => ({
                  title: step.label,
                  status: statusForStep(step.status),
                  description: stepStatusLabel(step.status),
                }))}
              />
            </div>
          ) : null}

          {percent != null ? (
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                总体进度{phaseLabel ? ` · ${phaseLabel}` : ""}
              </Typography.Text>
              <Progress
                percent={percent}
                status={progressStatus}
                style={{ display: "block", marginTop: 4 }}
              />
            </div>
          ) : waiting && !displayedSteps.length ? (
            <div style={{ textAlign: "center", padding: "8px 0" }}>
              <Spin />
            </div>
          ) : null}

          {category === "repository" ? (
            <Descriptions title={detailTitle} column={2} size="small">
              <Descriptions.Item label="仓库">
                {resultText(result.repository || run?.stats?.repo_id) || "—"}
              </Descriptions.Item>
              <Descriptions.Item label="提交版本">
                {resultText(result.commit || run?.stats?.commit) || "—"}
              </Descriptions.Item>
              <Descriptions.Item label="同步结果" span={2}>
                {resultText(result.summary) || summary}
              </Descriptions.Item>
            </Descriptions>
          ) : null}

          {category === "data_pipeline" ? (
            <div>
              <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                {detailTitle}
              </Typography.Text>
              {domainRows.length ? (
                <Table<JobRunDomainRow>
                  size="small"
                  pagination={false}
                  rowKey={(row, index) => `${row.mode || ""}:${row.id}:${index}`}
                  columns={domainColumns}
                  dataSource={domainRows}
                />
              ) : (
                <Typography.Text type="secondary">
                  {resultText(result.summary) || "当前任务尚未提供数据域明细"}
                </Typography.Text>
              )}
            </div>
          ) : null}

          {category === "batch_sync" ? (
            <div>
              <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                {detailTitle}
              </Typography.Text>
              <Descriptions column={3} size="small">
                {Object.entries(resultCounts).map(([key, value]) => (
                  <Descriptions.Item key={key} label={COUNT_LABELS[key] || key}>
                    {resultText(value) || "—"}
                  </Descriptions.Item>
                ))}
                {!Object.keys(resultCounts).length ? (
                  <Descriptions.Item label="同步结果" span={3}>
                    {resultText(result.summary) || summary}
                  </Descriptions.Item>
                ) : null}
              </Descriptions>
            </div>
          ) : null}

          {category === "asset_sync" ? (
            <div>
              <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
                {detailTitle}
              </Typography.Text>
              <Descriptions column={2} size="small">
                <Descriptions.Item label="版本">
                  {resultText(result.revision || run?.stats?.revision) || "—"}
                </Descriptions.Item>
                <Descriptions.Item label="是否更新">
                  {typeof run?.stats?.updated === "boolean"
                    ? run.stats.updated
                      ? "已更新"
                      : "无需更新"
                    : "—"}
                </Descriptions.Item>
                <Descriptions.Item label="结果" span={2}>
                  {resultText(result.summary) || summary}
                </Descriptions.Item>
              </Descriptions>
              {download ? (
                <div style={{ marginTop: 12 }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    文件下载{download.file ? ` · ${download.file}` : ""}
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
                    <Spin size="small" />
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}

          {!category && domainRows.length ? (
            <Table<JobRunDomainRow>
              size="small"
              pagination={false}
              rowKey={(row, index) => `${row.mode || ""}:${row.id}:${index}`}
              columns={domainColumns}
              dataSource={domainRows}
            />
          ) : null}

          {!category ? (
            <Descriptions title={detailTitle} column={2} size="small">
              {Object.entries(run?.stats || {})
                .filter(([key, value]) =>
                  !["schema_version", "category", "steps", "progress", "result", "domains"].includes(key) &&
                  value != null && typeof value !== "object",
                )
                .map(([key, value]) => (
                  <Descriptions.Item key={key} label={key}>
                    {String(value)}
                  </Descriptions.Item>
                ))}
            </Descriptions>
          ) : null}

          <div>
            <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
              实时日志{logs.length ? ` · ${logs.length} 条` : ""}
            </Typography.Text>
            <div
              ref={logContainerRef}
              role="log"
              aria-live="polite"
              style={{
                maxHeight: 280,
                overflow: "auto",
                border: "1px solid #e8e8e8",
                borderRadius: 6,
                background: "#fafafa",
                padding: 10,
              }}
            >
              {logs.length ? (
                logs.map((log) => (
                  <div
                    key={log.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "150px 72px minmax(0, 1fr)",
                      gap: 8,
                      alignItems: "start",
                      padding: "2px 0",
                    }}
                  >
                    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                      {log.created_at}
                    </Typography.Text>
                    <Tag
                      color={
                        log.level === "ERROR" || log.level === "CRITICAL"
                          ? "error"
                          : log.level === "WARNING"
                            ? "warning"
                            : "default"
                      }
                      style={{ margin: 0, width: "fit-content" }}
                    >
                      {log.level}
                    </Tag>
                    <Typography.Text
                      style={{
                        fontSize: 12,
                        fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace",
                        whiteSpace: "pre-wrap",
                        overflowWrap: "anywhere",
                      }}
                    >
                      {log.message}
                    </Typography.Text>
                  </div>
                ))
              ) : eventsQuery.isFetching || !finished ? (
                <Space size={8}>
                  <Spin size="small" />
                  <Typography.Text type="secondary">等待任务输出日志…</Typography.Text>
                </Space>
              ) : (
                <Typography.Text type="secondary">该执行记录没有可展示的日志</Typography.Text>
              )}
            </div>
          </div>
        </Space>
      ) : null}
    </Modal>
  );
}
