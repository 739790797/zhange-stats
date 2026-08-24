import {
  ClearOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Input,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchRuntimeHealth,
  type RuntimeHealthService,
} from "@/api/runtimeHealthApi";
import { clearRuntimeLogs, fetchRuntimeLogs } from "@/api/runtimeLogsApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";

const LEVEL_COLOR: Record<string, string> = {
  DEBUG: "default",
  INFO: "blue",
  WARNING: "orange",
  WARN: "orange",
  ERROR: "red",
  CRITICAL: "magenta",
};

const HEALTH_TAG: Record<string, { color: string; label: string }> = {
  ok: { color: "success", label: "正常" },
  degraded: { color: "warning", label: "降级" },
  error: { color: "error", label: "异常" },
  offline: { color: "error", label: "离线" },
  skipped: { color: "default", label: "未启用" },
};

function healthMeta(status: string) {
  return HEALTH_TAG[status] ?? { color: "default", label: status || "—" };
}

function ServiceChip({ item }: { item: RuntimeHealthService }) {
  const meta = healthMeta(item.status);
  const latency =
    item.latency_ms != null && Number.isFinite(item.latency_ms)
      ? ` · ${Math.round(item.latency_ms)}ms`
      : "";

  return (
    <div
      style={{
        minWidth: 160,
        maxWidth: 280,
        flex: "1 1 160px",
        padding: "10px 12px",
        borderRadius: 8,
        border: "1px solid rgba(0,0,0,0.06)",
        background: "rgba(0,0,0,0.02)",
      }}
      title={item.detail}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          marginBottom: 4,
        }}
      >
        <Typography.Text strong style={{ fontSize: 13 }}>
          {item.name}
        </Typography.Text>
        <Tag color={meta.color} style={{ margin: 0 }}>
          {meta.label}
        </Tag>
      </div>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {item.detail || "—"}
        {latency}
      </Typography.Text>
    </div>
  );
}

export default function PlatformLogsPage() {
  const queryClient = useQueryClient();
  const [level, setLevel] = useState<string | undefined>("INFO");
  const [loggerPrefix, setLoggerPrefix] = useState("");
  const [bizPrefix, setBizPrefix] = useState("");
  const [logSource, setLogSource] = useState<"all" | "ring" | "file">("all");
  const [q, setQ] = useState("");
  const [qApplied, setQApplied] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [stickBottom, setStickBottom] = useState(true);
  const scrollerRef = useRef<HTMLDivElement>(null);

  const healthQuery = useQuery({
    queryKey: ["runtime-health"],
    queryFn: fetchRuntimeHealth,
    refetchInterval: autoRefresh ? 5000 : false,
  });

  const logsQuery = useQuery({
    queryKey: ["runtime-logs", level, loggerPrefix, bizPrefix, logSource, qApplied],
    queryFn: () =>
      fetchRuntimeLogs({
        limit: 400,
        level: level || null,
        logger: loggerPrefix.trim() || null,
        biz: bizPrefix.trim() || null,
        q: qApplied.trim() || null,
        source: logSource,
      }),
    refetchInterval: autoRefresh ? 2500 : false,
  });

  const clearMutation = useMutation({
    mutationFn: clearRuntimeLogs,
    onSuccess: () => {
      message.success("已清空内存日志");
      queryClient.invalidateQueries({ queryKey: ["runtime-logs"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "清空失败")),
  });

  const lines = logsQuery.data?.lines ?? [];
  const lastLineId = lines.length ? lines[lines.length - 1].id : 0;
  const services = healthQuery.data?.services ?? [];

  useEffect(() => {
    if (!stickBottom) return;
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lastLineId, stickBottom]);

  const sourceOptions = useMemo(
    () => [
      { value: "all", label: "全部（推荐）" },
      { value: "ring", label: "实时缓冲" },
      { value: "file", label: "持久化文件" },
    ],
    [],
  );

  const levelOptions = useMemo(
    () => [
      { value: "DEBUG", label: "DEBUG+" },
      { value: "INFO", label: "INFO+" },
      { value: "WARNING", label: "WARNING+" },
      { value: "ERROR", label: "ERROR+" },
    ],
    [],
  );

  const refreshing = logsQuery.isFetching || healthQuery.isFetching;

  return (
    <div>
      <PageHeader
        title="平台日志"
        extra={
          <Space wrap>
            <Switch
              checkedChildren={<PlayCircleOutlined />}
              unCheckedChildren={<PauseCircleOutlined />}
              checked={autoRefresh}
              onChange={setAutoRefresh}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              自动刷新
            </Typography.Text>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                logsQuery.refetch();
                healthQuery.refetch();
              }}
              loading={refreshing}
            >
              刷新
            </Button>
            <Button
              danger
              icon={<ClearOutlined />}
              loading={clearMutation.isPending}
              onClick={() => clearMutation.mutate()}
            >
              清空缓冲
            </Button>
          </Space>
        }
      />

      <div style={{ marginBottom: 16 }}>
        {healthQuery.isError ? (
          <Typography.Text type="danger">
            {apiError(healthQuery.error, "加载服务健康失败")}
          </Typography.Text>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {services.map((item) => (
              <ServiceChip key={item.id} item={item} />
            ))}
            {!healthQuery.isLoading && services.length === 0 ? (
              <Typography.Text type="secondary">暂无服务状态</Typography.Text>
            ) : null}
          </div>
        )}
      </div>

      <Space wrap style={{ marginBottom: 16 }} size="middle">
        <Select
          style={{ width: 150 }}
          value={logSource}
          options={sourceOptions}
          onChange={setLogSource}
        />
        <Select
          style={{ width: 140 }}
          value={level}
          options={levelOptions}
          onChange={setLevel}
          allowClear
          placeholder="最低级别"
        />
        <Select
          style={{ width: 160 }}
          value={loggerPrefix || undefined}
          allowClear
          placeholder="全部 logger"
          onChange={(v) => setLoggerPrefix(v ?? "")}
          options={[
            { value: "app", label: "app.*" },
            { value: "zhange", label: "zhange.*" },
            { value: "uvicorn", label: "uvicorn.*" },
            { value: "alembic", label: "alembic.*" },
          ]}
        />
        <Select
          style={{ width: 170 }}
          value={bizPrefix || undefined}
          allowClear
          placeholder="全部业务"
          onChange={(v) => setBizPrefix(v ?? "")}
          options={[
            { value: "skland", label: "skland.*" },
            { value: "taygedo", label: "taygedo.*" },
            { value: "exilium", label: "exilium.*" },
            { value: "kujiequ", label: "kujiequ.*" },
            { value: "mihoyo", label: "mihoyo.*" },
            { value: "checkin", label: "checkin.*" },
            { value: "steam", label: "steam.*" },
            { value: "minecraft", label: "minecraft.*" },
            { value: "tarkov", label: "tarkov.*" },
            { value: "arknights", label: "arknights.*" },
            { value: "infra", label: "infra.*" },
            { value: "http", label: "http.*" },
            { value: "scheduler", label: "scheduler" },
          ]}
        />
        <Input.Search
          style={{ width: 280 }}
          allowClear
          placeholder="搜索消息 / logger"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onSearch={(v) => setQApplied(v)}
        />
        <Space size={6}>
          <Switch checked={stickBottom} onChange={setStickBottom} size="small" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            跟随底部
          </Typography.Text>
        </Space>
      </Space>

      <div
        ref={scrollerRef}
        style={{
          background: "#0f1419",
          color: "#d6deeb",
          borderRadius: 8,
          padding: "12px 14px",
          fontFamily:
            'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
          fontSize: 12,
          lineHeight: 1.55,
          height: "min(70vh, 640px)",
          overflow: "auto",
          border: "1px solid rgba(0,0,0,0.08)",
        }}
      >
        {logsQuery.isError ? (
          <Typography.Text type="danger">
            {apiError(logsQuery.error, "加载日志失败")}
          </Typography.Text>
        ) : null}
        {!logsQuery.isError && lines.length === 0 ? (
          <Typography.Text style={{ color: "rgba(214,222,235,0.55)" }}>
            暂无匹配日志。可放宽级别 / 业务 / logger，或触发一次签到与调度后再看。
          </Typography.Text>
        ) : null}
        {lines.map((line) => (
          <div
            key={line.id}
            style={{
              display: "grid",
              gridTemplateColumns: "148px 78px 120px minmax(100px, 140px) minmax(120px, 180px) 1fr",
              gap: 8,
              padding: "2px 0",
              borderBottom: "1px solid rgba(255,255,255,0.04)",
            }}
          >
            <span style={{ color: "rgba(214,222,235,0.55)", whiteSpace: "nowrap" }}>
              {line.ts}
            </span>
            <span>
              <Tag
                color={LEVEL_COLOR[line.level] || "default"}
                style={{ margin: 0, fontSize: 11, lineHeight: "18px" }}
              >
                {line.level}
              </Tag>
            </span>
            <span
              style={{
                color: "#c3e88d",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={line.biz || "—"}
            >
              {line.biz || "—"}
            </span>
            <span
              style={{
                color: "#82aaff",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={line.logger}
            >
              {line.logger}
            </span>
            <span
              style={{
                color: "rgba(214,222,235,0.45)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={line.context || undefined}
            >
              {line.context || "—"}
            </span>
            <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {line.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

