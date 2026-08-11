import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Image, Space, Tag, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import {
  fetchMaaMe,
  fetchMaaMeLogs,
  startMaaDaily,
  stopMaaDaily,
} from "@/api/maaApi";
import { useAuthedImage } from "@/hooks/useAuthedImage";
import { apiError } from "@/lib/apiError";

type Props = {
  enabled?: boolean;
};

export function ArknightsMaaPanel({ enabled = true }: Props) {
  const queryClient = useQueryClient();
  const [shotTick, setShotTick] = useState(0);
  const [pageVisible, setPageVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState === "visible",
  );
  const logPreRef = useRef<HTMLPreElement | null>(null);
  const logStickBottom = useRef(true);

  const statusQuery = useQuery({
    queryKey: ["maa-me"],
    queryFn: fetchMaaMe,
    enabled,
    refetchInterval: 4000,
    retry: false,
  });

  const assigned = statusQuery.data?.assigned;
  const slot = statusQuery.data?.slot;
  const job = statusQuery.data?.active_job;
  const online = slot?.status === "online";

  const logsQuery = useQuery({
    queryKey: ["maa-me-logs"],
    queryFn: fetchMaaMeLogs,
    enabled: Boolean(enabled && assigned),
    refetchInterval: enabled && assigned && pageVisible ? 3000 : false,
    retry: false,
  });

  useEffect(() => {
    if (!enabled || !assigned || document.visibilityState === "hidden") return;
    const t = window.setInterval(() => setShotTick((x) => x + 1), 3000);
    return () => window.clearInterval(t);
  }, [enabled, assigned]);

  useEffect(() => {
    const onVis = () => {
      const visible = document.visibilityState === "visible";
      setPageVisible(visible);
      if (visible) setShotTick((x) => x + 1);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    const el = logPreRef.current;
    if (!el || !logStickBottom.current) return;
    el.scrollTop = el.scrollHeight;
  }, [logsQuery.data?.text]);

  const { url: shotUrl, error: shotError } = useAuthedImage(
    assigned && slot?.has_screenshot ? "/maa/me/screenshot" : null,
    shotTick,
  );

  const startMut = useMutation({
    mutationFn: startMaaDaily,
    onSuccess: () => {
      message.success("已下发日常任务");
      queryClient.invalidateQueries({ queryKey: ["maa-me"] });
      queryClient.invalidateQueries({ queryKey: ["maa-me-logs"] });
    },
    onError: (e) => message.error(apiError(e, "下发失败")),
  });

  const stopMut = useMutation({
    mutationFn: stopMaaDaily,
    onSuccess: () => {
      message.success("已请求停止");
      queryClient.invalidateQueries({ queryKey: ["maa-me"] });
      queryClient.invalidateQueries({ queryKey: ["maa-me-logs"] });
    },
    onError: (e) => message.error(apiError(e, "停止失败")),
  });

  if (!enabled) {
    return <Alert type="info" showIcon message="请先绑定森空岛后再使用 MAA" />;
  }

  if (statusQuery.isError) {
    return (
      <Alert
        type="warning"
        showIcon
        message={apiError(statusQuery.error, "无法加载 MAA 状态（功能可能未启用）")}
      />
    );
  }

  if (statusQuery.isLoading) {
    return <Typography.Text type="secondary">加载中…</Typography.Text>;
  }

  if (!assigned || !slot) {
    const avail = statusQuery.data?.availability;
    const alertType =
      avail === "available" ? "success" : avail === "waiting" ? "info" : "warning";
    return (
      <Alert
        type={alertType}
        showIcon
        message={statusQuery.data?.message || "暂未分配 MAA 槽位"}
      />
    );
  }

  return (
    <div>
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="服务器全托管自动化存在账号风险，请自行评估；首次登录需管理员在实例内完成。"
      />
      <Space wrap style={{ marginBottom: 12 }}>
        <Tag color={online ? "success" : "default"}>槽位 #{slot.id}</Tag>
        <Tag>{slot.status}</Tag>
        {job ? (
          <Tag color="processing">
            任务 {job.job_type} · {job.status}
          </Tag>
        ) : (
          <Tag>空闲</Tag>
        )}
        {slot.cpu_percent || slot.memory_usage_mb ? (
          <Typography.Text type="secondary" style={{ whiteSpace: "pre-line" }}>
            {`CPU：${slot.cpu_percent || "—"}%\n内存：${
              Number(slot.memory_usage_mb) >= 1024
                ? `${(Number(slot.memory_usage_mb) / 1024).toFixed(2)}GB`
                : `${slot.memory_usage_mb || "—"}MB`
            }`}
          </Typography.Text>
        ) : null}
      </Space>
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          disabled={!online || !!job}
          loading={startMut.isPending}
          onClick={() => startMut.mutate()}
        >
          开始日常
        </Button>
        <Button
          disabled={!job}
          loading={stopMut.isPending}
          onClick={() => stopMut.mutate()}
        >
          停止
        </Button>
      </Space>
      <div style={{ marginBottom: 16 }}>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          运行截图（约每 3 秒刷新；页面不可见时暂停）
        </Typography.Paragraph>
        {shotError || !shotUrl ? (
          <Typography.Text type="secondary">暂无截图</Typography.Text>
        ) : (
          <Image
            src={shotUrl}
            alt="MAA screenshot"
            style={{ maxWidth: "100%", maxHeight: 480, objectFit: "contain" }}
          />
        )}
      </div>
      <div>
        {logsQuery.data?.last_error ? (
          <Typography.Paragraph type="danger" style={{ marginBottom: 8 }}>
            {logsQuery.data.last_error}
          </Typography.Paragraph>
        ) : null}
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          运行日志（约每 3 秒刷新；页面不可见时暂停）
        </Typography.Paragraph>
        <pre
          ref={logPreRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            logStickBottom.current =
              el.scrollHeight - el.scrollTop - el.clientHeight < 48;
          }}
          style={{
            margin: 0,
            padding: 12,
            background: "#0f172a",
            color: "#e2e8f0",
            borderRadius: 8,
            fontSize: 12,
            lineHeight: 1.45,
            maxHeight: 320,
            overflow: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {logsQuery.isLoading
            ? "加载中…"
            : logsQuery.isError
              ? apiError(logsQuery.error, "无法加载运行日志")
              : logsQuery.data?.text || "暂无日志"}
        </pre>
      </div>
    </div>
  );
}
