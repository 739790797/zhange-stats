import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Drawer,
  Dropdown,
  Image,
  Modal,
  Progress,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  Tooltip,
  theme,
  message,
} from "antd";
import type { MenuProps } from "antd";
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

const STATUS_DOT: Record<string, string> = {
  provisioning: "#1677ff",
  online: "#52c41a",
  offline: "#bfbfbf",
  destroying: "#faad14",
  destroyed: "#d9d9d9",
  error: "#ff4d4f",
};

const STATUS_LABEL: Record<string, string> = {
  provisioning: "启动中",
  online: "就绪",
  offline: "离线",
  destroying: "销毁中",
  destroyed: "已销毁",
  error: "异常",
};

type DetailTab = "overview" | "logs" | "audits" | "screenshot";

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

function StatusCell({ status, desired }: { status: string; desired?: string | null }) {
  return (
    <Space size={6}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: STATUS_DOT[status] || "#bfbfbf",
          display: "inline-block",
          flexShrink: 0,
        }}
      />
      <span>
        <Typography.Text>{STATUS_LABEL[status] || status}</Typography.Text>
        {desired ? (
          <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
            · {desired}
          </Typography.Text>
        ) : null}
      </span>
    </Space>
  );
}

function MiniHostMeter({
  percent,
  label,
  detail,
  color,
}: {
  percent: number;
  label: string;
  detail: string;
  color: string;
}) {
  const pct = Math.max(0, Math.min(100, percent));
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        minWidth: 160,
        padding: "8px 12px",
        border: "1px solid rgba(0,0,0,0.06)",
        borderRadius: 6,
        background: "#fafafa",
      }}
    >
      <Progress
        type="circle"
        percent={Number(pct.toFixed(1))}
        size={44}
        strokeWidth={10}
        strokeColor={color}
        trailColor="rgba(0,0,0,0.06)"
        format={() => (
          <span style={{ fontSize: 11, fontWeight: 600 }}>{pct.toFixed(0)}</span>
        )}
      />
      <div style={{ lineHeight: 1.3 }}>
        <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{detail}</div>
      </div>
    </div>
  );
}

function MaaSummaryBoard({ summary }: { summary?: MaaResourceSummary }) {
  const { token } = theme.useToken();
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
        gap: 12,
        alignItems: "stretch",
        marginBottom: 16,
      }}
    >
      <MiniHostMeter
        percent={Number.isFinite(cpu) ? cpu : 0}
        label="CPU"
        color={token.colorPrimary}
        detail={
          cpuCoresUsed != null && Number.isFinite(cpuCount)
            ? `${cpuCoresUsed.toFixed(2)} / ${cpuCount} 核`
            : "等待上报"
        }
      />
      <MiniHostMeter
        percent={memPct}
        label="内存"
        color={token.colorLink}
        detail={`${mbToGbLabel(summary?.host_memory_used_mb ?? null)} / ${mbToGbLabel(summary?.host_memory_total_mb ?? null)}`}
      />
      {counts.map((c) => (
        <div
          key={c.label}
          style={{
            minWidth: 72,
            padding: "8px 14px",
            border: "1px solid rgba(0,0,0,0.06)",
            borderRadius: 6,
            background: "#fff",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>{c.label}</div>
          <div
            style={{
              fontSize: 20,
              fontWeight: 600,
              color: token.colorPrimary,
              lineHeight: 1.2,
              marginTop: 2,
            }}
          >
            {c.value}
          </div>
        </div>
      ))}
    </div>
  );
}

function SlotScreenshot({
  slotId,
  has,
  status,
  width = 120,
  showRefresh = true,
}: {
  slotId: number;
  has: boolean;
  status?: string;
  width?: number;
  showRefresh?: boolean;
}) {
  const [tick, setTick] = useState(0);
  const { url, error } = useAuthedImage(
    has ? `/settings/maa/slots/${slotId}/screenshot` : null,
    tick,
  );
  useEffect(() => {
    if (!has || status !== "provisioning") return;
    const t = window.setInterval(() => setTick((v) => v + 1), 8000);
    return () => window.clearInterval(t);
  }, [has, status]);
  if (!has) {
    return (
      <Typography.Text type="secondary">
        {status === "provisioning" ? "启动中…" : "无截图"}
      </Typography.Text>
    );
  }
  if (error) return <Typography.Text type="danger">加载失败</Typography.Text>;
  if (!url) return <Typography.Text type="secondary">…</Typography.Text>;
  return (
    <Space direction="vertical" size={4}>
      <Image src={url} width={width} style={{ objectFit: "contain" }} />
      {showRefresh ? (
        <Button size="small" type="link" onClick={() => setTick((t) => t + 1)}>
          刷新
        </Button>
      ) : null}
    </Space>
  );
}

function shortProgress(text: string | null | undefined, max = 36): string {
  if (!text) return "—";
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

export default function MaaSettingsPage() {
  const queryClient = useQueryClient();
  const [includeDestroyed, setIncludeDestroyed] = useState(false);
  const [detailSlotId, setDetailSlotId] = useState<number | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
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

  const detailSlot = useMemo(
    () => (listQuery.data?.slots || []).find((s) => s.id === detailSlotId) ?? null,
    [listQuery.data?.slots, detailSlotId],
  );

  const auditsQuery = useQuery({
    queryKey: ["maa-audits", detailSlotId],
    queryFn: () => fetchMaaSlotAudits(detailSlotId!),
    enabled: detailSlotId != null && detailTab === "audits",
  });

  const logsQuery = useQuery({
    queryKey: ["maa-logs", detailSlotId],
    queryFn: () => fetchMaaSlotLogs(detailSlotId!),
    enabled: detailSlotId != null && detailTab === "logs",
    refetchInterval:
      detailSlotId != null && detailTab === "logs" ? 3000 : false,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["maa-admin"] });

  const openDetail = (slotId: number, tab: DetailTab = "overview") => {
    setDetailSlotId(slotId);
    setDetailTab(tab);
  };

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

  const slotActionItems = (row: MaaSlot): MenuProps["items"] => {
    const busy = !!row.desired_action;
    return [
      {
        key: "start",
        label: "上线",
        disabled: row.status !== "offline" || busy,
        onClick: () => actionMut.mutate({ id: row.id, action: "start" }),
      },
      {
        key: "stop",
        label: "下线",
        disabled: row.status !== "online" || busy,
        onClick: () => actionMut.mutate({ id: row.id, action: "stop" }),
      },
      { type: "divider" },
      {
        key: "bind",
        label: "绑定成员",
        disabled:
          row.status === "destroyed" ||
          row.status === "destroying" ||
          row.status === "provisioning",
        onClick: () => {
          setBindSlot(row);
          setBindMemberId(row.bound_member_id ?? null);
        },
      },
      {
        key: "unbind",
        label: "解绑",
        disabled: !row.bound_member_id,
        onClick: () => actionMut.mutate({ id: row.id, action: "unbind" }),
      },
      { type: "divider" },
      {
        key: "detail",
        label: "详情",
        onClick: () => openDetail(row.id, "overview"),
      },
      {
        key: "logs",
        label: "日志",
        onClick: () => openDetail(row.id, "logs"),
      },
      {
        key: "audits",
        label: "审计",
        onClick: () => openDetail(row.id, "audits"),
      },
      { type: "divider" },
      {
        key: "destroy",
        danger: true,
        label: "移除",
        disabled:
          row.status === "online" ||
          row.status === "destroyed" ||
          row.status === "destroying",
        onClick: () => {
          Modal.confirm({
            title: "确认移除？",
            content: "将删除容器与游戏数据卷，不可恢复。",
            okText: "移除",
            okType: "danger",
            cancelText: "取消",
            onOk: () => actionMut.mutateAsync({ id: row.id, action: "destroy" }),
          });
        },
      },
    ];
  };

  return (
    <div>
      <PageHeader
        title="MAA 资源"
        subtitle="单槽参考：内存约 4GB、CPU 约 1～2 核、磁盘约 10GB+。单机常驻建议 2～4 槽。"
      />

      <MaaSummaryBoard summary={summary} />

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
          marginBottom: 12,
        }}
      >
        <Space wrap>
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
        </Space>
        <Button
          type={includeDestroyed ? "primary" : "default"}
          onClick={() => setIncludeDestroyed((v) => !v)}
        >
          {includeDestroyed ? "隐藏已销毁" : "显示已销毁"}
        </Button>
      </div>

      <Table
        size="middle"
        rowKey="id"
        loading={listQuery.isLoading}
        dataSource={listQuery.data?.slots || []}
        pagination={false}
        scroll={{ x: 900 }}
        columns={[
          { title: "ID", dataIndex: "id", width: 56 },
          {
            title: "状态",
            dataIndex: "status",
            width: 140,
            render: (s: string, row: MaaSlot) => (
              <StatusCell status={s} desired={row.desired_action} />
            ),
          },
          {
            title: "绑定",
            width: 160,
            ellipsis: true,
            render: (_: unknown, row: MaaSlot) =>
              row.bound_member_id
                ? `${row.bound_member_nickname || "成员"} (#${row.bound_member_id})`
                : "—",
          },
          {
            title: "占用",
            width: 120,
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
                <Typography.Text style={{ fontSize: 12 }}>
                  {row.cpu_percent || "—"}% / {formatMem(row.memory_usage_mb)}
                </Typography.Text>
              );
            },
          },
          {
            title: "心跳",
            dataIndex: "last_heartbeat_at",
            width: 168,
            ellipsis: true,
            render: (v: string | null) => (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {v || "—"}
              </Typography.Text>
            ),
          },
          {
            title: "进度",
            dataIndex: "last_error",
            ellipsis: true,
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
                  <Typography.Text
                    type={tone}
                    style={{ fontSize: 12, cursor: "pointer" }}
                    onClick={() => openDetail(row.id, "logs")}
                  >
                    {shortProgress(v)}
                  </Typography.Text>
                </Tooltip>
              );
            },
          },
          {
            title: "操作",
            width: 168,
            fixed: "right",
            render: (_: unknown, row: MaaSlot) => (
              <Space size={4}>
                <Button
                  size="small"
                  type="link"
                  onClick={() => openDetail(row.id, "overview")}
                >
                  详情
                </Button>
                <Dropdown
                  menu={{ items: slotActionItems(row) }}
                  trigger={["click"]}
                >
                  <Button size="small" loading={actionMut.isPending}>
                    更多
                  </Button>
                </Dropdown>
              </Space>
            ),
          },
        ]}
      />

      <Drawer
        title={detailSlotId != null ? `槽位 #${detailSlotId}` : "槽位详情"}
        open={detailSlotId != null}
        onClose={() => setDetailSlotId(null)}
        width={720}
        destroyOnClose
      >
        {detailSlot ? (
          <Tabs
            activeKey={detailTab}
            onChange={(k) => setDetailTab(k as DetailTab)}
            items={[
              {
                key: "overview",
                label: "概览",
                children: (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <div>
                      <StatusCell
                        status={detailSlot.status}
                        desired={detailSlot.desired_action}
                      />
                    </div>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      <Typography.Text type="secondary">绑定：</Typography.Text>
                      {detailSlot.bound_member_id
                        ? `${detailSlot.bound_member_nickname || "成员"} (#${detailSlot.bound_member_id})`
                        : "未绑定"}
                    </Typography.Paragraph>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      <Typography.Text type="secondary">容器：</Typography.Text>
                      {detailSlot.container_name || "—"}
                    </Typography.Paragraph>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      <Typography.Text type="secondary">ADB：</Typography.Text>
                      {detailSlot.adb_endpoint || "—"}
                    </Typography.Paragraph>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      <Typography.Text type="secondary">占用：</Typography.Text>
                      {detailSlot.cpu_percent || "—"}% /{" "}
                      {formatMem(detailSlot.memory_usage_mb)}
                    </Typography.Paragraph>
                    <Typography.Paragraph style={{ marginBottom: 0 }}>
                      <Typography.Text type="secondary">心跳：</Typography.Text>
                      {detailSlot.last_heartbeat_at || "—"}
                    </Typography.Paragraph>
                    {detailSlot.last_error ? (
                      <Typography.Paragraph
                        type={detailSlot.status === "error" ? "danger" : "secondary"}
                        style={{ marginBottom: 0 }}
                      >
                        {detailSlot.last_error}
                      </Typography.Paragraph>
                    ) : null}
                    <div>
                      <Typography.Text type="secondary">截图预览</Typography.Text>
                      <div style={{ marginTop: 8 }}>
                        <SlotScreenshot
                          slotId={detailSlot.id}
                          has={detailSlot.has_screenshot}
                          status={detailSlot.status}
                          width={240}
                        />
                      </div>
                    </div>
                  </Space>
                ),
              },
              {
                key: "logs",
                label: "日志",
                children: (
                  <>
                    {logsQuery.data?.last_error ? (
                      <Typography.Paragraph type="danger" style={{ marginBottom: 12 }}>
                        {logsQuery.data.last_error}
                      </Typography.Paragraph>
                    ) : null}
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
                      状态：{logsQuery.data?.status || detailSlot.status || "—"}
                      （约 3 秒自动刷新）
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
                        maxHeight: "65vh",
                        overflow: "auto",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                      }}
                    >
                      {logsQuery.isLoading
                        ? "加载中…"
                        : logsQuery.data?.text || "暂无日志"}
                    </pre>
                  </>
                ),
              },
              {
                key: "audits",
                label: "审计",
                children: (
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
                          <Tag color={r === "success" ? "success" : "error"}>
                            {r}
                          </Tag>
                        ),
                      },
                      { title: "说明", dataIndex: "message", ellipsis: true },
                    ]}
                  />
                ),
              },
              {
                key: "screenshot",
                label: "截图",
                children: (
                  <SlotScreenshot
                    slotId={detailSlot.id}
                    has={detailSlot.has_screenshot}
                    status={detailSlot.status}
                    width={360}
                  />
                ),
              },
            ]}
          />
        ) : (
          <Typography.Text type="secondary">槽位不存在或已销毁</Typography.Text>
        )}
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
