import { PlayCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import {
  Alert,
  Button,
  InputNumber,
  Space,
  Spin,
  Switch,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  fetchPlatformFeaturesAdmin,
  triggerScheduledJob,
  updatePlatformFeatures,
  type PlatformFeatureNode,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { PlatformIcon } from "@/components/PlatformIcon";
import { featureIconName } from "@/lib/platformIcons";

type DraftFlags = Record<string, boolean>;
type DraftJobs = Record<
  string,
  { interval_minutes?: number; hour?: number; minute?: number }
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

function collectJobs(nodes: PlatformFeatureNode[], out: DraftJobs = {}) {
  for (const node of nodes) {
    if (node.job_id && node.schedule) {
      out[node.job_id] = {
        interval_minutes: node.interval_minutes ?? undefined,
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
  triggeringJobId,
  onToggle,
  onJobPatch,
  onManualRun,
}: {
  node: PlatformFeatureNode;
  depth: number;
  flags: DraftFlags;
  jobs: DraftJobs;
  triggeringJobId: string | null;
  onToggle: (id: string, enabled: boolean) => void;
  onJobPatch: (jobId: string, patch: DraftJobs[string]) => void;
  onManualRun: (jobId: string) => void;
}) {
  const enabled = flags[node.id] === true;
  const parentOk = node.parent_effective;
  const reserved = Boolean(node.reserved);
  const canEdit = parentOk && !reserved;
  const jobDraft = node.job_id ? jobs[node.job_id] : undefined;
  const iconName =
    node.kind === "platform" || node.kind === "game"
      ? featureIconName(node.id)
      : null;
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
            {iconName ? <PlatformIcon name={iconName} size={18} /> : null}
            <Typography.Text strong={depth === 0}>{node.name}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {node.kind === "platform"
                ? "平台"
                : node.kind === "game"
                  ? "游戏"
                  : node.kind === "job"
                    ? "任务"
                    : "功能"}
            </Typography.Text>
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
              icon={<PlayCircleOutlined />}
              loading={triggeringJobId === node.job_id}
              onClick={() => onManualRun(node.job_id!)}
            >
              手动同步
            </Button>
          ) : null}
          <Switch
            checked={reserved ? parentOk : enabled}
            disabled={!canEdit}
            onChange={(checked) => onToggle(node.id, checked)}
          />
        </Space>
      </div>
      {(node.children || []).map((child) => (
        <FeatureRow
          key={child.id}
          node={{
            ...child,
            parent_effective: parentOk && (reserved || enabled),
          }}
          depth={depth + 1}
          flags={flags}
          jobs={jobs}
          triggeringJobId={triggeringJobId}
          onToggle={onToggle}
          onJobPatch={onJobPatch}
          onManualRun={onManualRun}
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

  const query = useQuery({
    queryKey: ["platform-features-admin"],
    queryFn: fetchPlatformFeaturesAdmin,
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

  const save = useMutation({
    mutationFn: updatePlatformFeatures,
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
    mutationFn: (jobId: string) => triggerScheduledJob(jobId, {}),
    onMutate: (jobId) => {
      setTriggeringJobId(jobId);
    },
    onSuccess: (data) => {
      message.success(data.message || "已提交同步");
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-ammo"] });
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-guns"] });
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-bosses"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "同步失败")),
    onSettled: () => setTriggeringJobId(null),
  });

  return (
    <div>
      <PageHeader
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
                save.mutate({ features, jobs });
              }}
              style={{ background: "#1a2332", borderColor: "#1a2332" }}
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
              triggeringJobId={triggeringJobId}
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
              onManualRun={(jobId) => manualRun.mutate(jobId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
