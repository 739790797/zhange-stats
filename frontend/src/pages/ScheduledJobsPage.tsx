import { ReloadOutlined, ScheduleOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  InputNumber,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type ThHTMLAttributes,
} from "react";
import {
  fetchScheduledJobs,
  updateScheduledJobs,
  type ScheduledJob,
} from "@/api/client";

type Draft = {
  enabled: boolean;
  interval_minutes?: number;
  hour?: number;
  minute?: number;
};

type ColKey =
  | "name"
  | "enabled"
  | "config"
  | "status"
  | "next_run_at"
  | "last_run";

const DEFAULT_COL_WIDTHS: Record<ColKey, number> = {
  name: 220,
  enabled: 88,
  config: 200,
  status: 110,
  next_run_at: 180,
  last_run: 280,
};

type ResizableTitleProps = ThHTMLAttributes<HTMLTableCellElement> & {
  width?: number;
  onResize?: (width: number) => void;
};

function ResizableTitle({
  width,
  onResize,
  children,
  ...rest
}: ResizableTitleProps) {
  const onMouseDown = useCallback(
    (event: ReactMouseEvent) => {
      if (!onResize || !width) return;
      event.preventDefault();
      event.stopPropagation();
      const startX = event.clientX;
      const startWidth = width;

      const onMove = (ev: MouseEvent) => {
        const next = Math.max(72, startWidth + (ev.clientX - startX));
        onResize(next);
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    },
    [onResize, width],
  );

  if (!width || !onResize) {
    return <th {...rest}>{children}</th>;
  }

  return (
    <th {...rest} style={{ ...rest.style, position: "relative" }}>
      {children}
      <span
        onMouseDown={onMouseDown}
        style={{
          position: "absolute",
          right: -4,
          top: 0,
          bottom: 0,
          width: 8,
          cursor: "col-resize",
          zIndex: 1,
        }}
      />
    </th>
  );
}

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

function draftsFromJobs(jobs: ScheduledJob[]): Record<string, Draft> {
  const next: Record<string, Draft> = {};
  for (const job of jobs) {
    next[job.id] = {
      enabled: Boolean(job.config_enabled),
      interval_minutes: job.interval_minutes ?? 3,
      hour: job.hour ?? 0,
      minute: job.minute ?? 0,
    };
  }
  return next;
}

export default function ScheduledJobsPage() {
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [fakePoll, setFakePoll] = useState(false);
  const [colWidths, setColWidths] =
    useState<Record<ColKey, number>>(DEFAULT_COL_WIDTHS);

  const jobsQuery = useQuery({
    queryKey: ["scheduled-jobs"],
    queryFn: fetchScheduledJobs,
    refetchInterval: 30_000,
  });

  useEffect(() => {
    if (!jobsQuery.data?.jobs) return;
    setDrafts(draftsFromJobs(jobsQuery.data.jobs));
    setFakePoll(Boolean(jobsQuery.data.steam_fake_poll));
  }, [jobsQuery.data]);

  const save = useMutation({
    mutationFn: updateScheduledJobs,
    onSuccess: (data) => {
      message.success("定时任务已保存并应用");
      queryClient.setQueryData(["scheduled-jobs"], data);
      setDrafts(draftsFromJobs(data.jobs));
      setFakePoll(Boolean(data.steam_fake_poll));
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "保存失败"));
    },
  });

  const patchDraft = (id: string, patch: Partial<Draft>) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || { enabled: false }), ...patch },
    }));
  };

  const resizeCol = useCallback((key: ColKey, width: number) => {
    setColWidths((prev) => ({ ...prev, [key]: width }));
  }, []);

  const columns: ColumnsType<ScheduledJob> = useMemo(() => {
    const base: ColumnsType<ScheduledJob> = [
      {
        title: "任务",
        dataIndex: "name",
        key: "name",
        width: colWidths.name,
        onHeaderCell: () =>
          ({
            width: colWidths.name,
            onResize: (w: number) => resizeCol("name", w),
          }) as ResizableTitleProps,
        render: (_, row) => (
          <div style={{ lineHeight: 1.45 }}>
            <Typography.Text strong style={{ display: "block" }}>
              {row.name}
            </Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {row.id}
            </Typography.Text>
          </div>
        ),
      },
      {
        title: "启用",
        key: "enabled",
        width: colWidths.enabled,
        align: "center",
        onHeaderCell: () =>
          ({
            width: colWidths.enabled,
            onResize: (w: number) => resizeCol("enabled", w),
          }) as ResizableTitleProps,
        render: (_, row) => {
          const draft = drafts[row.id];
          const fakeLocked = row.id === "steam_presence" && fakePoll;
          return (
            <Switch
              checked={draft?.enabled ?? Boolean(row.config_enabled)}
              disabled={fakeLocked}
              onChange={(checked) => patchDraft(row.id, { enabled: checked })}
            />
          );
        },
      },
      {
        title: "调度",
        key: "config",
        width: colWidths.config,
        onHeaderCell: () =>
          ({
            width: colWidths.config,
            onResize: (w: number) => resizeCol("config", w),
          }) as ResizableTitleProps,
        render: (_, row) => {
          const draft = drafts[row.id];
          if (!draft) return null;
          if (row.kind === "interval" || row.id === "steam_presence") {
            return (
              <Space size={6}>
                <Typography.Text type="secondary">每</Typography.Text>
                <InputNumber
                  min={1}
                  max={1440}
                  style={{ width: 72 }}
                  value={draft.interval_minutes}
                  onChange={(v) =>
                    patchDraft(row.id, { interval_minutes: Number(v) || 1 })
                  }
                />
                <Typography.Text type="secondary">分钟</Typography.Text>
              </Space>
            );
          }
          return (
            <Space size={4}>
              <InputNumber
                min={0}
                max={23}
                style={{ width: 64 }}
                value={draft.hour}
                onChange={(v) => patchDraft(row.id, { hour: Number(v) || 0 })}
              />
              <Typography.Text type="secondary">:</Typography.Text>
              <InputNumber
                min={0}
                max={59}
                style={{ width: 64 }}
                value={draft.minute}
                onChange={(v) =>
                  patchDraft(row.id, { minute: Number(v) || 0 })
                }
              />
            </Space>
          );
        },
      },
      {
        title: "状态",
        key: "status",
        width: colWidths.status,
        onHeaderCell: () =>
          ({
            width: colWidths.status,
            onResize: (w: number) => resizeCol("status", w),
          }) as ResizableTitleProps,
        render: (_, row) => statusTag(row),
      },
      {
        title: "下次执行",
        dataIndex: "next_run_at",
        key: "next_run_at",
        width: colWidths.next_run_at,
        onHeaderCell: () =>
          ({
            width: colWidths.next_run_at,
            onResize: (w: number) => resizeCol("next_run_at", w),
          }) as ResizableTitleProps,
        render: (v: string | null | undefined) =>
          v || <Typography.Text type="secondary">-</Typography.Text>,
      },
      {
        title: "最近执行",
        key: "last_run",
        width: colWidths.last_run,
        onHeaderCell: () =>
          ({
            width: colWidths.last_run,
            onResize: (w: number) => resizeCol("last_run", w),
          }) as ResizableTitleProps,
        render: (_, row) => {
          const last = row.last_run;
          if (!last) {
            return <Typography.Text type="secondary">暂无记录</Typography.Text>;
          }
          return (
            <div style={{ lineHeight: 1.45 }}>
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
                  style={{ fontSize: 12, display: "block" }}
                  title={last.message}
                >
                  {last.message}
                </Typography.Text>
              ) : null}
            </div>
          );
        },
      },
    ];
    return base;
  }, [colWidths, drafts, fakePoll, resizeCol]);

  const onSave = () => {
    const jobs: Record<
      string,
      {
        enabled?: boolean;
        interval_minutes?: number;
        hour?: number;
        minute?: number;
      }
    > = {};
    for (const job of jobsQuery.data?.jobs || []) {
      const draft = drafts[job.id];
      if (!draft) continue;
      if (job.kind === "interval" || job.id === "steam_presence") {
        jobs[job.id] = {
          enabled: draft.enabled,
          interval_minutes: draft.interval_minutes,
        };
      } else if (job.kind === "unknown") {
        continue;
      } else {
        jobs[job.id] = {
          enabled: draft.enabled,
          hour: draft.hour,
          minute: draft.minute,
        };
      }
    }
    save.mutate({ jobs, steam_fake_poll: fakePoll });
  };

  const fakeAvailable = jobsQuery.data?.steam_fake_available !== false;

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "flex-start",
          marginBottom: 16,
          gap: 16,
        }}
      >
        <Space>
          <Button
            icon={<ReloadOutlined />}
            loading={jobsQuery.isFetching}
            onClick={() => jobsQuery.refetch()}
          >
            刷新
          </Button>
          <Button
            type="primary"
            loading={save.isPending}
            onClick={onSave}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            保存并应用
          </Button>
        </Space>
      </div>

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
        description={
          fakePoll
            ? "本地假监控开启时，Steam 任务走假数据轮询（与真实 API 互斥）；关闭后恢复真实轮询配置。"
            : "已关闭的任务不会注册到调度器；「未启动」表示配置开启但缺少密钥或未成功注册。"
        }
      />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 16,
          padding: "12px 14px",
          background: "#f7f8fa",
          borderRadius: 6,
        }}
      >
        <div style={{ lineHeight: 1.5 }}>
          <Typography.Text strong style={{ display: "block" }}>
            本地假监控
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {fakeAvailable
              ? "仅伪造在线/游玩状态；游戏资料仍走真实请求。开启时会补齐演示账号。"
              : "当前环境未包含假监控模块，无法开启。"}
          </Typography.Text>
        </div>
        <Switch
          checked={fakePoll}
          disabled={!fakeAvailable || jobsQuery.isLoading}
          onChange={setFakePoll}
        />
      </div>

      <Table
        rowKey="id"
        loading={jobsQuery.isLoading}
        columns={columns}
        dataSource={jobsQuery.data?.jobs || []}
        pagination={false}
        size="middle"
        tableLayout="fixed"
        style={{ width: "100%" }}
        components={{
          header: {
            cell: ResizableTitle as (props: {
              children?: ReactNode;
            }) => ReactNode,
          },
        }}
      />
    </div>
  );
}
