import {
  CopyOutlined,
  GithubOutlined,
  HistoryOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/shared/api/apiError";
import {
  Alert,
  Button,
  InputNumber,
  Space,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { fetchJobRuns, fetchScheduledJobs, triggerScheduledJob, type JobRun } from "@/features/admin/api/jobsApi";
import { fetchPlatformFeaturesAdmin, updatePlatformFeatures, type PlatformFeatureNode } from "@/features/platforms/shared/api/platformFeaturesApi";
import { JobRunResultModal } from "@/features/admin/components/JobRunResultModal";
import { JobRunHistoryModal } from "@/features/admin/components/JobRunHistoryModal";
import { AdminPageHeader } from "@/features/admin/components/AdminPageHeader";
import {
  EXTERNAL_REPOSITORIES,
  isTaskFeatureVisible,
  taskFeatureDisplayName,
  DEFAULT_REPO_SYNC_TIMEOUT_MINUTES,
  MAX_REPO_SYNC_TIMEOUT_MINUTES,
  REPOSITORY_SYNC_TIMEOUT_JOBS,
} from "@/features/admin/model/taskFeaturePresentation";
import { BrandLogo } from "@/shared/ui/BrandLogo";
import { PlatformIcon } from "@/features/platforms/shared/components/PlatformIcon";
import { featureTreeIcon } from "@/features/platforms/shared/model/platformIcons";
import type { JobRunWatch } from "@/features/admin/model/jobRunResult";
import type { PlatformFeaturesUpdate } from "@/features/platforms/shared/api/platformFeaturesApi";

type DraftFlags = Record<string, boolean>;
type DraftJobs = Record<
  string,
  {
    interval_minutes?: number;
    timeout_minutes?: number;
    hour?: number;
    minute?: number;
  }
>;

function collectFlags(nodes: PlatformFeatureNode[], out: DraftFlags = {}) {
  for (const node of nodes) {
    if (!node.reserved) {
      out[node.id] = Boolean(node.enabled);
    }
    if (node.children?.length) collectFlags(node.children, out);
  }
  return out;
}

function collectReservedIds(
  nodes: PlatformFeatureNode[],
  out: Set<string> = new Set(),
) {
  for (const node of nodes) {
    if (node.reserved) out.add(node.id);
    if (node.children?.length) collectReservedIds(node.children, out);
  }
  return out;
}

function parseJobTime(value: string | null | undefined): number {
  if (!value) return Number.NaN;
  const text = value.includes("T") ? value : value.replace(" ", "T");
  const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text) ? text : `${text}+08:00`;
  return Date.parse(zoned);
}

function collectJobs(nodes: PlatformFeatureNode[], out: DraftJobs = {}) {
  for (const node of nodes) {
    if (node.job_id && node.schedule) {
      out[node.job_id] = {
        interval_minutes: node.interval_minutes ?? undefined,
        timeout_minutes: node.timeout_minutes ?? undefined,
        hour: node.hour ?? undefined,
        minute: node.minute ?? undefined,
      };
    }
    if (node.children?.length) collectJobs(node.children, out);
  }
  return out;
}

function FeatureRow({
  node,
  depth,
  flags,
  jobs,
  syncJobIds,
  triggeringJobId,
  runningJobIds,
  onToggle,
  onJobPatch,
  onManualRun,
  onHistory,
  onCopyCommand,
}: {
  node: PlatformFeatureNode;
  depth: number;
  flags: DraftFlags;
  jobs: DraftJobs;
  syncJobIds: ReadonlySet<string>;
  triggeringJobId: string | null;
  runningJobIds: ReadonlySet<string>;
  onToggle: (id: string, enabled: boolean) => void;
  onJobPatch: (jobId: string, patch: DraftJobs[string]) => void;
  onManualRun: (jobId: string, jobName: string) => void;
  onHistory: (jobId: string, jobName: string) => void;
  onCopyCommand: (jobId: string) => void;
}) {
  const enabled = flags[node.id] === true;
  const parentOk = node.parent_effective;
  const reserved = Boolean(node.reserved);
  const canEdit = parentOk && !reserved;
  const jobDraft = node.job_id ? jobs[node.job_id] : undefined;
  const executing = Boolean(
    node.job_id &&
      (runningJobIds.has(node.job_id) || triggeringJobId === node.job_id),
  );
  const icon = featureTreeIcon(node.id, node.kind);
  const externalRepo = EXTERNAL_REPOSITORIES[node.id];
  const featureName = taskFeatureDisplayName(node.id, node.name);
  const canManualRun =
    Boolean(node.job_id) &&
    (node.schedule === "cron" || node.schedule === "interval") &&
    parentOk &&
    (reserved || enabled);

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          padding: "10px 12px",
          marginLeft: depth * 24,
          borderBottom: "1px solid #f0f0f0",
          background: depth === 0 ? "#fafafa" : undefined,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              minWidth: 0,
            }}
          >
            {icon === "brand" ? (
              <span
                className="anticon"
                role="img"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <BrandLogo size={22} color="#1a2332" title="战鸽数据" />
              </span>
            ) : icon ? (
              <PlatformIcon name={icon} size={18} />
            ) : null}
            <Typography.Text strong={depth === 0}>{featureName}</Typography.Text>
            {externalRepo ? (
              <Button
                type="link"
                size="small"
                icon={<GithubOutlined />}
                href={externalRepo.url}
                target="_blank"
                rel="noreferrer"
                title="在 GitHub 打开对应仓库"
                aria-label={`在 GitHub 打开${externalRepo.name}仓库`}
                style={{ paddingInline: 2, height: 22 }}
              />
            ) : null}
            {reserved ? <Tag style={{ margin: 0 }}>预留</Tag> : null}
          </div>
          {!parentOk ? (
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: "block", marginTop: 2 }}
            >
              上级已关闭，此项暂不可用
            </Typography.Text>
          ) : null}
          {reserved ? (
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: "block", marginTop: 2 }}
            >
              暂无独立门控，跟随上级平台开关
            </Typography.Text>
          ) : null}
        </div>
        <Space wrap size={12}>
          {node.schedule === "interval" && node.job_id ? (
            <>
              <Typography.Text type="secondary">每</Typography.Text>
              <InputNumber
                min={1}
                max={1440}
                style={{ width: 72 }}
                disabled={!canEdit || !enabled}
                value={jobDraft?.interval_minutes ?? 3}
                onChange={(v) =>
                  onJobPatch(node.job_id!, {
                    ...jobDraft,
                    interval_minutes: Number(v) || 1,
                  })
                }
              />
              <Typography.Text type="secondary">分钟</Typography.Text>
            </>
          ) : null}
          {node.schedule === "cron" && node.job_id ? (
            <>
              <Typography.Text type="secondary">每天</Typography.Text>
              <InputNumber
                min={0}
                max={23}
                style={{ width: 64 }}
                disabled={!canEdit || !enabled}
                value={jobDraft?.hour ?? 0}
                onChange={(v) =>
                  onJobPatch(node.job_id!, {
                    ...jobDraft,
                    hour: Number(v) || 0,
                  })
                }
              />
              <Typography.Text type="secondary">:</Typography.Text>
              <InputNumber
                min={0}
                max={59}
                style={{ width: 64 }}
                disabled={!canEdit || !enabled}
                value={jobDraft?.minute ?? 0}
                onChange={(v) =>
                  onJobPatch(node.job_id!, {
                    ...jobDraft,
                    minute: Number(v) || 0,
                  })
                }
              />
            </>
          ) : null}
          {canManualRun && node.job_id ? (
            <Button
              size="small"
              disabled={executing}
              loading={executing}
              icon={executing ? undefined : <PlayCircleOutlined />}
              onClick={() => onManualRun(node.job_id!, featureName)}
            >
              {executing ? "执行中" : "手动同步"}
            </Button>
          ) : null}
          {node.job_id && syncJobIds.has(node.job_id) ? (
            <>
              <Tooltip title="复制跨平台 CLI 命令（在 backend/ 激活虚拟环境后运行）">
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  aria-label={`复制${featureName}命令`}
                  onClick={() => onCopyCommand(node.job_id!)}
                >
                  CLI
                </Button>
              </Tooltip>
              <Button
                size="small"
                icon={<HistoryOutlined />}
                aria-label={`查看${featureName}执行记录`}
                onClick={() => onHistory(node.job_id!, featureName)}
              >
                记录
              </Button>
            </>
          ) : null}
          <Switch
            checked={reserved ? parentOk : enabled}
            disabled={!canEdit}
            onChange={(checked) => onToggle(node.id, checked)}
          />
        </Space>
      </div>
      {(node.children || [])
        .filter((child) => isTaskFeatureVisible(child.id))
        .map((child) => (
          <FeatureRow
            key={child.id}
            node={{
              ...child,
              parent_effective: parentOk && (reserved || enabled),
            }}
            depth={depth + 1}
            flags={flags}
            jobs={jobs}
            syncJobIds={syncJobIds}
            triggeringJobId={triggeringJobId}
            runningJobIds={runningJobIds}
            onToggle={onToggle}
            onJobPatch={onJobPatch}
            onManualRun={onManualRun}
            onHistory={onHistory}
            onCopyCommand={onCopyCommand}
          />
        ))}
    </div>
  );
}

export default function TaskConfigPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<{
    flags: DraftFlags;
    jobs: DraftJobs;
  } | null>(null);
  const [triggeringJobId, setTriggeringJobId] = useState<string | null>(null);
  const [pendingRun, setPendingRun] = useState<{
    jobId: string;
    at: number;
  } | null>(null);
  const [runWatch, setRunWatch] = useState<JobRunWatch | null>(null);
  const [historyJob, setHistoryJob] = useState<{ id: string; name: string } | null>(null);

  const query = useQuery({
    queryKey: ["platform-features-admin"],
    queryFn: fetchPlatformFeaturesAdmin,
  });

  const scheduledJobs = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: fetchScheduledJobs,
    refetchInterval: (q) => {
      const running = (q.state.data?.jobs || []).some(
        (job) => job.last_run?.status === "running" || job.last_run?.status === "queued",
      );
      return running || pendingRun ? 2000 : false;
    },
  });

  const baseline = useMemo(() => {
    if (!query.data?.tree?.length) return null;
    return {
      flags: collectFlags(query.data.tree),
      jobs: collectJobs(query.data.tree),
    };
  }, [query.data]);

  useEffect(() => {
    setDraft(null);
  }, [query.dataUpdatedAt]);

  const flags = draft?.flags ?? baseline?.flags;
  const jobs = draft?.jobs ?? baseline?.jobs;
  const runningJobIds = useMemo(() => {
    const ids = new Set<string>();
    for (const job of scheduledJobs.data?.jobs || []) {
      if (job.last_run?.status === "running" || job.last_run?.status === "queued") ids.add(job.id);
    }
    if (pendingRun) ids.add(pendingRun.jobId);
    return ids;
  }, [pendingRun, scheduledJobs.data]);
  const syncJobIds = useMemo(
    () =>
      new Set(
        (scheduledJobs.data?.jobs || [])
          .filter((job) => Boolean(job.sync_category))
          .map((job) => job.id),
      ),
    [scheduledJobs.data],
  );

  useEffect(() => {
    if (!pendingRun) return;
    const job = scheduledJobs.data?.jobs?.find((item) => item.id === pendingRun.jobId);
    if (job?.last_run?.status === "running" || job?.last_run?.status === "queued") {
      setPendingRun(null);
      return;
    }
    const started = parseJobTime(job?.last_run?.started_at);
    if (Number.isNaN(started) || started < pendingRun.at - 5000) return;
    if (["ok", "warning", "error"].includes(job?.last_run?.status || "")) {
      setPendingRun(null);
    }
  }, [pendingRun, scheduledJobs.data]);

  const save = useMutation({
    mutationFn: (payload: PlatformFeaturesUpdate) =>
      updatePlatformFeatures(payload),
    onSuccess: (data) => {
      message.success("任务配置已保存并应用");
      queryClient.setQueryData(["platform-features-admin"], data);
      queryClient.setQueryData(
        ["platform-features-effective"],
        data.effective,
      );
      setDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["user-checkin-tasks"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const manualRun = useMutation({
    mutationFn: async ({
      jobId,
      jobName,
    }: {
      jobId: string;
      jobName: string;
    }) => {
      let sinceRunId = 0;
      try {
        const page = await fetchJobRuns(jobId, { page: 1, page_size: 1 });
        sinceRunId = page.items?.[0]?.id ?? 0;
      } catch {
        sinceRunId = 0;
      }
      const data = await triggerScheduledJob(jobId, {});
      return { data, jobId, jobName, sinceRunId };
    },
    onMutate: ({ jobId }) => {
      setTriggeringJobId(jobId);
      setPendingRun({ jobId, at: Date.now() });
    },
    onSuccess: ({ data, jobId, jobName, sinceRunId }) => {
      setRunWatch({
        jobId,
        jobName,
        sinceRunId,
        runId: data.run_id,
        category: data.category,
        acceptedAt: Date.now(),
        acceptedMessage: data.message || "已提交执行",
      });
      void queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-ammo"] });
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-guns"] });
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-bosses"] });
    },
    onError: (e: unknown) => {
      setPendingRun(null);
      message.error(apiError(e, "同步失败"));
    },
    onSettled: () => setTriggeringJobId(null),
  });

  const copyCliCommand = async (jobId: string) => {
    const command = scheduledJobs.data?.jobs?.find((job) => job.id === jobId)?.cli_command;
    if (!command) {
      message.error("未找到该任务的 CLI 命令");
      return;
    }
    try {
      await navigator.clipboard.writeText(command);
      message.success("CLI 命令已复制");
    } catch {
      message.error("复制失败，请检查浏览器剪贴板权限");
    }
  };

  const openRunHistory = (jobId: string, jobName: string) => {
    setHistoryJob({ id: jobId, name: jobName });
  };

  const openHistoricalRun = (run: JobRun) => {
    const jobId = historyJob?.id;
    if (!jobId) return;
    setRunWatch({
      jobId,
      jobName: historyJob.name,
      sinceRunId: 0,
      runId: run.id,
      category: typeof run.stats?.category === "string" ? run.stats.category : null,
      acceptedAt: Date.now(),
      acceptedMessage: run.message || "执行记录",
    });
    setHistoryJob(null);
  };

  return (
    <div>
      <AdminPageHeader
        title="任务配置"
        subtitle="控制各平台可用性及其子游戏 / 任务。关闭平台后，侧栏、绑定、接口与调度将一并停用。"
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              loading={query.isFetching}
              onClick={() => void query.refetch()}
            >
              刷新
            </Button>
            <Button
              type="primary"
              loading={save.isPending}
              disabled={!flags || !jobs}
              onClick={() => {
                if (!flags || !jobs || !query.data?.tree) return;
                const reserved = collectReservedIds(query.data.tree);
                const features: DraftFlags = {};
                for (const [id, on] of Object.entries(flags)) {
                  if (!reserved.has(id)) features[id] = on;
                }
                const payload = { features, jobs };
                save.mutate(payload);
              }}
            >
              保存并应用
            </Button>
          </Space>
        }
      />

      {query.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="加载任务配置失败"
          description={apiError(query.error, "请稍后重试")}
        />
      ) : null}

      {query.isLoading || !baseline || !flags || !jobs ? (
        <div style={{ padding: 48, textAlign: "center" }}>
          <Spin />
        </div>
      ) : (
        <>
          <div
            style={{
              border: "1px solid #f0f0f0",
              borderRadius: 8,
              overflow: "hidden",
              background: "#fff",
            }}
          >
            {query.data!.tree.map((node) => (
              <FeatureRow
                key={node.id}
                node={node}
                depth={0}
                flags={flags}
                jobs={jobs}
                syncJobIds={syncJobIds}
                triggeringJobId={triggeringJobId}
                runningJobIds={runningJobIds}
                onToggle={(id, enabled) =>
                  setDraft({
                    flags: { ...flags, [id]: enabled },
                    jobs: { ...jobs },
                  })
                }
                onJobPatch={(jobId, patch) =>
                  setDraft({
                    flags: { ...flags },
                    jobs: {
                      ...jobs,
                      [jobId]: { ...jobs[jobId], ...patch },
                    },
                  })
                }
                onManualRun={(jobId, jobName) =>
                  manualRun.mutate({ jobId, jobName })
                }
                onHistory={openRunHistory}
                onCopyCommand={(jobId) => void copyCliCommand(jobId)}
              />
            ))}
          </div>

          <section
            aria-labelledby="repo-sync-timeout-title"
            style={{
              marginTop: 16,
              border: "1px solid #f0f0f0",
              borderRadius: 8,
              background: "#fff",
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "12px 16px", borderBottom: "1px solid #f0f0f0" }}>
              <Typography.Text id="repo-sync-timeout-title" strong style={{ fontSize: 16 }}>
                Git 仓库同步超时
              </Typography.Text>
              <Typography.Text type="secondary" style={{ display: "block", marginTop: 4 }}>
                默认 {DEFAULT_REPO_SYNC_TIMEOUT_MINUTES} 分钟，可按仓库体量分别调整（1–{MAX_REPO_SYNC_TIMEOUT_MINUTES} 分钟）。超时会终止当前 Git 命令。
              </Typography.Text>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: 12,
                padding: 16,
              }}
            >
              {REPOSITORY_SYNC_TIMEOUT_JOBS.map((repo) => (
                <div
                  key={repo.jobId}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: 12,
                    border: "1px solid #f0f0f0",
                    borderRadius: 6,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <Typography.Text strong>{repo.label}</Typography.Text>
                    <Typography.Text type="secondary" style={{ display: "block", fontSize: 12 }}>
                      {repo.repository}
                    </Typography.Text>
                  </div>
                  <Space size={6} style={{ flexShrink: 0 }}>
                    <InputNumber
                      min={1}
                      max={MAX_REPO_SYNC_TIMEOUT_MINUTES}
                      precision={0}
                      style={{ width: 88 }}
                      aria-label={`${repo.label}同步超时（分钟）`}
                      value={jobs[repo.jobId]?.timeout_minutes ?? DEFAULT_REPO_SYNC_TIMEOUT_MINUTES}
                      onChange={(value) => {
                        const timeout = typeof value === "number" ? Math.trunc(value) : DEFAULT_REPO_SYNC_TIMEOUT_MINUTES;
                        setDraft({
                          flags: { ...flags },
                          jobs: {
                            ...jobs,
                            [repo.jobId]: {
                              ...jobs[repo.jobId],
                              timeout_minutes: timeout,
                            },
                          },
                        });
                      }}
                    />
                    <Typography.Text type="secondary">分钟</Typography.Text>
                  </Space>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <JobRunResultModal watch={runWatch} onClose={() => setRunWatch(null)} />
      <JobRunHistoryModal
        job={historyJob}
        onClose={() => setHistoryJob(null)}
        onSelect={openHistoricalRun}
      />
    </div>
  );
}
