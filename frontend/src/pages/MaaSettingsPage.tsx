import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Drawer,
  Image,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Tooltip,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import {
  bindMaaSlot,
  createMaaSlot,
  destroyMaaSlot,
  fetchMaaAdminList,
  fetchMaaSlotAudits,
  fetchMaaSlotLogs,
  startMaaSlot,
  stopMaaSlot,
  triggerMaaReconcile,
  unbindMaaSlot,
  type MaaResourceSummary,
  type MaaSlot,
} from "@/api/maaApi";
import { fetchJobFilterMembers } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { useAuthedImage } from "@/hooks/useAuthedImage";
import { apiError } from "@/lib/apiError";

const STATUS_COLOR: Record<string, string> = {
  provisioning: "processing",
  online: "success",
  offline: "default",
  destroying: "warning",
  destroyed: "default",
  error: "error",
};

const STATUS_LABEL: Record<string, string> = {
  provisioning: "启动中",
  online: "就绪",
  offline: "离线",
  destroying: "销毁中",
  destroyed: "已销毁",
  error: "异常",
};

const ACCENT = "#1677ff";

function formatMem(mbRaw: string | null | undefined): string {
  const n = Number(mbRaw);
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n >= 1024) {
    const gb = n / 1024;
    return `${gb >= 10 ? gb.toFixed(1) : gb.toFixed(2)}GB`;
  }
  return `${Number.isInteger(n) ? String(n) : n.toFixed(1)}MB`;
}

function mbToGbLabel(mbRaw: string | null | undefined): string {
  const n = Number(mbRaw);
  if (!Number.isFinite(n) || n < 0) return "—";
  return `${(n / 1024).toFixed(2)} GB`;
}

function SectionMark({ title }: { title: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 16,
      }}
    >
      <span
        style={{
          width: 3,
          height: 14,
          borderRadius: 1,
          background: ACCENT,
          display: "inline-block",
        }}
      />
      <Typography.Text strong style={{ fontSize: 15 }}>
        {title}
      </Typography.Text>
    </div>
  );
}

function OverviewStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{ textAlign: "center", minWidth: 72 }}>
      <div style={{ color: "rgba(0,0,0,0.45)", fontSize: 13, marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ color: ACCENT, fontSize: 28, fontWeight: 600, lineHeight: 1.1 }}>
        {value}
      </div>
    </div>
  );
}

function HostRing({
  percent,
  title,
  footer,
}: {
  percent: number;
  title: string;
  footer: string;
}) {
  const pct = Math.max(0, Math.min(100, percent));
  return (
    <div style={{ textAlign: "center", width: 168, padding: "0 8px" }}>
      <Progress
        type="circle"
        percent={Number(pct.toFixed(2))}
        size={128}
        strokeColor={ACCENT}
        trailColor="rgba(22,119,255,0.12)"
        strokeWidth={8}
        format={() => (
          <div>
            <div style={{ fontSize: 18, fontWeight: 600, color: "rgba(0,0,0,0.88)" }}>
              {pct.toFixed(2)} %
            </div>
            <div style={{ fontSize: 13, color: "rgba(0,0,0,0.45)", marginTop: 2 }}>
              {title}
            </div>
          </div>
        )}
      />
      <div
        style={{
          marginTop: 10,
          fontSize: 12,
          color: "rgba(0,0,0,0.45)",
          whiteSpace: "nowrap",
        }}
      >
        {footer}
      </div>
    </div>
  );
}

function MaaSummaryBoard({ summary }: { summary?: MaaResourceSummary }) {
  const cpu = Number(summary?.host_cpu_percent);
  const memUsed = Number(summary?.host_memory_used_mb);
  const memTotal = Number(summary?.host_memory_total_mb);
  const cpuCount = Number(summary?.host_cpu_count);
  const memPct =
    Number.isFinite(memUsed) && Number.isFinite(memTotal) && memTotal > 0
      ? (memUsed / memTotal) * 100
      : 0;
  const cpuCoresUsed =
    Number.isFinite(cpu) && Number.isFinite(cpuCount) && cpuCount > 0
      ? (cpu / 100) * cpuCount
      : null;

  const counts = [
    { label: "槽位", value: summary?.active_slots ?? 0 },
    { label: "就绪空闲", value: summary?.unbound_online ?? 0 },
    { label: "在线", value: summary?.online ?? 0 },
    { label: "离线", value: summary?.offline ?? 0 },
    { label: "异常", value: summary?.error ?? 0 },
    { label: "忙碌", value: summary?.busy ?? 0 },
  ];

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 48,
        alignItems: "flex-start",
        marginBottom: 8,
      }}
    >
      <div style={{ flex: "0 0 400px", minWidth: 360, paddingRight: 24 }}>
        <SectionMark title="状态" />
        <div
          style={{
            display: "flex",
            gap: 40,
            flexWrap: "nowrap",
            justifyContent: "flex-start",
            paddingLeft: 8,
          }}
        >
          <HostRing
            percent={Number.isFinite(cpu) ? cpu : 0}
            title="CPU"
            footer={
              cpuCoresUsed != null && Number.isFinite(cpuCount)
                ? `( ${cpuCoresUsed.toFixed(2)} / ${cpuCount} ) 核`
                : "等待 Worker 上报"
            }
          />
          <HostRing
            percent={memPct}
            title="内存"
            footer={`${mbToGbLabel(summary?.host_memory_used_mb ?? null)} / ${mbToGbLabel(summary?.host_memory_total_mb ?? null)}`}
          />
        </div>
      </div>
      <div style={{ flex: "1 1 360px", minWidth: 280 }}>
        <SectionMark title="概览" />
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "20px 36px",
            alignItems: "flex-start",
            justifyContent: "center",
          }}
        >
          {counts.map((c) => (
            <OverviewStat key={c.label} label={c.label} value={c.value} />
          ))}
        </div>
      </div>
    </div>
  );
}

function SlotUsage({
  cpu,
  memMb,
}: {
  cpu?: string | null;
  memMb?: string | null;
}) {
  return (
    <Space direction="vertical" size={0}>
      <Typography.Text>CPU：{cpu || "—"}%</Typography.Text>
      <Typography.Text>内存：{formatMem(memMb)}</Typography.Text>
    </Space>
  );
}

function SlotScreenshot({
  slotId,
  has,
  status,
}: {
  slotId: number;
  has: boolean;
  status?: string;
}) {
  const [tick, setTick] = useState(0);
  const { url, error } = useAuthedImage(
    has ? `/settings/maa/slots/${slotId}/screenshot` : null,
    tick,
  );
  // 供给中定期刷新，便于看到启动画面
  useEffect(() => {
    if (!has || status !== "provisioning") return;
    const t = window.setInterval(() => setTick((v) => v + 1), 8000);
    return () => window.clearInterval(t);
  }, [has, status]);
  if (!has) {
    return (
      <Typography.Text type="secondary">
        {status === "provisioning" ? "启动中…" : "无"}
      </Typography.Text>
    );
  }
  if (error) return <Typography.Text type="danger">加载失败</Typography.Text>;
  if (!url) return <Typography.Text type="secondary">…</Typography.Text>;
  return (
    <Space direction="vertical" size={4}>
      <Image src={url} width={120} style={{ objectFit: "contain" }} />
      <Button size="small" type="link" onClick={() => setTick((t) => t + 1)}>
        刷新
      </Button>
    </Space>
  );
}

export default function MaaSettingsPage() {
  const queryClient = useQueryClient();
  const [includeDestroyed, setIncludeDestroyed] = useState(false);
  const [auditSlotId, setAuditSlotId] = useState<number | null>(null);
  const [logSlotId, setLogSlotId] = useState<number | null>(null);
  const [bindSlot, setBindSlot] = useState<MaaSlot | null>(null);
  const [bindMemberId, setBindMemberId] = useState<number | null>(null);

  const listQuery = useQuery({
    queryKey: ["maa-admin", includeDestroyed],
    queryFn: () => fetchMaaAdminList(includeDestroyed),
    refetchInterval: (q) => {
      const slots = q.state.data?.slots || [];
      const busy = slots.some((s) =>
        ["provisioning", "destroying"].includes(s.status),
      );
      return busy ? 2000 : 5000;
    },
  });

  const membersQuery = useQuery({
    queryKey: ["job-filter-members"],
    queryFn: fetchJobFilterMembers,
    staleTime: 60_000,
  });

  const auditsQuery = useQuery({
    queryKey: ["maa-audits", auditSlotId],
    queryFn: () => fetchMaaSlotAudits(auditSlotId!),
    enabled: auditSlotId != null,
  });

  const logsQuery = useQuery({
    queryKey: ["maa-logs", logSlotId],
    queryFn: () => fetchMaaSlotLogs(logSlotId!),
    enabled: logSlotId != null,
    refetchInterval: logSlotId != null ? 3000 : false,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["maa-admin"] });

  const createMut = useMutation({
    mutationFn: createMaaSlot,
    onSuccess: () => {
      message.success("已创建槽位，正在按步骤启动…");
      invalidate();
    },
    onError: (e) => message.error(apiError(e, "创建失败")),
  });

  const actionMut = useMutation({
    mutationFn: async ({
      id,
      action,
    }: {
      id: number;
      action: "start" | "stop" | "destroy" | "unbind";
    }) => {
      if (action === "start") return startMaaSlot(id);
      if (action === "stop") return stopMaaSlot(id);
      if (action === "destroy") return destroyMaaSlot(id);
      return unbindMaaSlot(id);
    },
    onMutate: async ({ id, action }) => {
      if (action !== "destroy") return;
      await queryClient.cancelQueries({ queryKey: ["maa-admin"] });
      const key = ["maa-admin", includeDestroyed] as const;
      const prev = queryClient.getQueryData<Awaited<ReturnType<typeof fetchMaaAdminList>>>(key);
      if (prev) {
        queryClient.setQueryData(key, {
          ...prev,
          slots: prev.slots.map((s) =>
            s.id === id
              ? { ...s, status: "destroying", desired_action: "destroy" }
              : s,
          ),
        });
      }
      return { prev, key };
    },
    onSuccess: (_data, vars) => {
      message.success(vars.action === "destroy" ? "已提交销毁" : "已提交");
      invalidate();
    },
    onError: (e, _vars, ctx) => {
      if (ctx?.prev && ctx.key) {
        queryClient.setQueryData(ctx.key, ctx.prev);
      }
      message.error(apiError(e, "操作失败"));
    },
  });

  const bindMut = useMutation({
    mutationFn: () => bindMaaSlot(bindSlot!.id, bindMemberId!),
    onSuccess: () => {
      message.success("已绑定");
      setBindSlot(null);
      setBindMemberId(null);
      invalidate();
    },
    onError: (e) => message.error(apiError(e, "绑定失败")),
  });

  const reconcileMut = useMutation({
    mutationFn: triggerMaaReconcile,
    onSuccess: (r) => message.success(r.message),
    onError: (e) => message.error(apiError(e, "对账请求失败")),
  });

  const summary = listQuery.data?.summary;
  const memberOptions = useMemo(
    () =>
      (membersQuery.data || []).map((m) => ({
        value: m.member_id,
        label: m.label,
      })),
    [membersQuery.data],
  );

  return (
    <div>
      <PageHeader
        title="MAA 资源"
        subtitle="单槽参考：内存约 4GB（空闲 Android 约 1.5～3GB，进游戏约 3～6GB）、CPU 约 1～2 核（空闲常 <0.5 核）、磁盘约 10GB+（镜像约 3GB 多槽共享）。单机常驻建议 2～4 槽。"
      />

      <div style={{ marginBottom: 20 }}>
        <MaaSummaryBoard summary={summary} />
      </div>

      <Space wrap style={{ marginBottom: 12 }}>
        <Button
          type="primary"
          loading={createMut.isPending}
          onClick={() => createMut.mutate()}
        >
          新增槽位
        </Button>
        <Button
          loading={reconcileMut.isPending}
          onClick={() => reconcileMut.mutate()}
        >
          触发对账
        </Button>
        <Button
          type={includeDestroyed ? "primary" : "default"}
          onClick={() => setIncludeDestroyed((v) => !v)}
        >
          {includeDestroyed ? "隐藏已销毁" : "显示已销毁"}
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={listQuery.isLoading}
        dataSource={listQuery.data?.slots || []}
        pagination={false}
        columns={[
          { title: "ID", dataIndex: "id", width: 64 },
          {
            title: "状态",
            dataIndex: "status",
            render: (s: string, row: MaaSlot) => (
              <Space direction="vertical" size={0}>
                <Tag color={STATUS_COLOR[s] || "default"}>
                  {STATUS_LABEL[s] || s}
                </Tag>
                {row.desired_action ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    待执行: {row.desired_action}
                  </Typography.Text>
                ) : null}
              </Space>
            ),
          },
          {
            title: "绑定",
            render: (_: unknown, row: MaaSlot) =>
              row.bound_member_id
                ? `${row.bound_member_nickname || "成员"} (#${row.bound_member_id})`
                : "—",
          },
          {
            title: "占用",
            render: (_: unknown, row: MaaSlot) => {
              const running =
                row.status === "online" ||
                row.status === "provisioning" ||
                (row.status === "error" &&
                  !!(row.cpu_percent || row.memory_usage_mb));
              if (!running && !row.cpu_percent && !row.memory_usage_mb) {
                return "—";
              }
              return (
                <SlotUsage cpu={row.cpu_percent} memMb={row.memory_usage_mb} />
              );
            },
          },
          {
            title: "心跳",
            dataIndex: "last_heartbeat_at",
            render: (v: string | null) => v || "—",
          },
          {
            title: "截图",
            render: (_: unknown, row: MaaSlot) => (
              <SlotScreenshot
                slotId={row.id}
                has={row.has_screenshot}
                status={row.status}
              />
            ),
          },
          {
            title: "进度",
            dataIndex: "last_error",
            ellipsis: true,
            width: 220,
            render: (v: string | null, row: MaaSlot) => {
              if (!v) return "—";
              const tone =
                row.status === "error"
                  ? "danger"
                  : row.status === "provisioning"
                    ? "secondary"
                    : undefined;
              return (
                <Tooltip title={v}>
                  <Typography.Text type={tone} ellipsis style={{ maxWidth: 200 }}>
                    {v}
                  </Typography.Text>
                </Tooltip>
              );
            },
          },
          {
            title: "操作",
            width: 280,
            render: (_: unknown, row: MaaSlot) => (
              <Space wrap size="small">
                <Button
                  size="small"
                  disabled={row.status !== "offline" || !!row.desired_action}
                  loading={actionMut.isPending}
                  onClick={() =>
                    actionMut.mutate({ id: row.id, action: "start" })
                  }
                >
                  上线
                </Button>
                <Button
                  size="small"
                  disabled={row.status !== "online" || !!row.desired_action}
                  loading={actionMut.isPending}
                  onClick={() =>
                    actionMut.mutate({ id: row.id, action: "stop" })
                  }
                >
                  下线
                </Button>
                <Button
                  size="small"
                  disabled={
                    row.status === "destroyed" ||
                    row.status === "destroying" ||
                    row.status === "provisioning"
                  }
                  onClick={() => {
                    setBindSlot(row);
                    setBindMemberId(row.bound_member_id ?? null);
                  }}
                >
                  绑定
                </Button>
                <Button
                  size="small"
                  disabled={!row.bound_member_id}
                  onClick={() =>
                    actionMut.mutate({ id: row.id, action: "unbind" })
                  }
                >
                  解绑
                </Button>
                <Button size="small" onClick={() => setLogSlotId(row.id)}>
                  日志
                </Button>
                <Button size="small" onClick={() => setAuditSlotId(row.id)}>
                  审计
                </Button>
                <Popconfirm
                  title="确认移除？将删除容器与游戏数据卷，不可恢复。"
                  disabled={
                    row.status === "online" ||
                    row.status === "destroyed" ||
                    row.status === "destroying"
                  }
                  onConfirm={() =>
                    actionMut.mutate({ id: row.id, action: "destroy" })
                  }
                >
                  <Button
                    size="small"
                    danger
                    disabled={
                      row.status === "online" ||
                      row.status === "destroyed" ||
                      row.status === "destroying"
                    }
                  >
                    移除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={logSlotId != null ? `槽位 #${logSlotId} 运行日志` : "日志"}
        open={logSlotId != null}
        onClose={() => setLogSlotId(null)}
        width={720}
      >
        {logsQuery.data?.last_error ? (
          <Typography.Paragraph type="danger" style={{ marginBottom: 12 }}>
            {logsQuery.data.last_error}
          </Typography.Paragraph>
        ) : null}
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          状态：{logsQuery.data?.status || "—"}（约 3 秒自动刷新）
        </Typography.Paragraph>
        <pre
          style={{
            margin: 0,
            padding: 12,
            background: "#0f172a",
            color: "#e2e8f0",
            borderRadius: 8,
            fontSize: 12,
            lineHeight: 1.45,
            maxHeight: "70vh",
            overflow: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {logsQuery.isLoading
            ? "加载中…"
            : logsQuery.data?.text || "暂无日志"}
        </pre>
      </Drawer>

      <Drawer
        title={auditSlotId != null ? `槽位 #${auditSlotId} 审计` : "审计"}
        open={auditSlotId != null}
        onClose={() => setAuditSlotId(null)}
        width={520}
      >
        <Table
          size="small"
          rowKey="id"
          loading={auditsQuery.isLoading}
          dataSource={auditsQuery.data || []}
          pagination={false}
          columns={[
            { title: "时间", dataIndex: "created_at", width: 180 },
            { title: "动作", dataIndex: "action", width: 100 },
            {
              title: "结果",
              dataIndex: "result",
              width: 80,
              render: (r: string) => (
                <Tag color={r === "success" ? "success" : "error"}>{r}</Tag>
              ),
            },
            { title: "说明", dataIndex: "message", ellipsis: true },
          ]}
        />
      </Drawer>

      <Modal
        title={bindSlot ? `绑定槽位 #${bindSlot.id}` : "绑定"}
        open={bindSlot != null}
        onCancel={() => setBindSlot(null)}
        onOk={() => {
          if (!bindMemberId) {
            message.warning("请选择成员");
            return;
          }
          bindMut.mutate();
        }}
        confirmLoading={bindMut.isPending}
      >
        <Select
          style={{ width: "100%" }}
          showSearch
          optionFilterProp="label"
          placeholder="选择成员"
          options={memberOptions}
          value={bindMemberId}
          onChange={(v) => setBindMemberId(v)}
        />
      </Modal>
    </div>
  );
}
