import { CloudDownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Space, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import {
  checkUpdate,
  fetchUpdateStatus,
  triggerUpdate,
} from "@/api/client";

async function waitForNewVersion(previous: string, timeoutMs = 180_000) {
  const prev = previous.replace(/^v/i, "").trim();
  if (!prev) {
    throw new Error("无法确认当前版本，请刷新页面后重试");
  }
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    await new Promise((r) => setTimeout(r, 2000));
    try {
      const res = await fetch("/health", { cache: "no-store" });
      if (!res.ok) continue;
      const data = (await res.json()) as { version?: string };
      const next = (data.version || "").replace(/^v/i, "").trim();
      if (next && next !== prev) {
        return next;
      }
    } catch {
      // 重建期间短暂不可用，继续等
    }
  }
  throw new Error("等待服务恢复超时，请手动刷新或检查服务器");
}

function formatVersion(v?: string | null) {
  const text = (v || "").replace(/^v/i, "").trim();
  return text ? `v${text}` : "—";
}

export default function SystemUpdatePage() {
  const queryClient = useQueryClient();
  const [waiting, setWaiting] = useState(false);
  const previousVersion = useRef("");

  const checkQuery = useQuery({
    queryKey: ["update-check"],
    queryFn: checkUpdate,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const statusQuery = useQuery({
    queryKey: ["update-status"],
    queryFn: fetchUpdateStatus,
    refetchInterval: (q) => {
      const state = q.state.data?.state;
      if (state === "pulling" || state === "recreating" || state === "checking") {
        return 1500;
      }
      return false;
    },
  });

  useEffect(() => {
    const current =
      checkQuery.data?.current_version || statusQuery.data?.current_version;
    if (current) {
      previousVersion.current = current;
    }
  }, [checkQuery.data?.current_version, statusQuery.data?.current_version]);

  const doUpdate = useMutation({
    mutationFn: triggerUpdate,
    onSuccess: async () => {
      message.info("已开始更新，服务会短暂中断…");
      setWaiting(true);
      queryClient.invalidateQueries({ queryKey: ["update-status"] });
      try {
        const prev =
          previousVersion.current ||
          checkQuery.data?.current_version ||
          statusQuery.data?.current_version ||
          "";
        const next = await waitForNewVersion(prev);
        message.success(`已更新到 v${next}`);
        window.location.reload();
      } catch (e: unknown) {
        message.error(e instanceof Error ? e.message : "更新等待失败");
      } finally {
        setWaiting(false);
        queryClient.invalidateQueries({ queryKey: ["update-check"] });
        queryClient.invalidateQueries({ queryKey: ["update-status"] });
        queryClient.invalidateQueries({ queryKey: ["app-version"] });
      }
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "启动更新失败"));
    },
  });

  const data = checkQuery.data;
  const status = statusQuery.data;
  const currentVersion =
    data?.current_version || status?.current_version || "";
  const busy =
    waiting ||
    doUpdate.isPending ||
    status?.state === "pulling" ||
    status?.state === "recreating";

  const checkHardError =
    checkQuery.isError &&
    ((checkQuery.error as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail ||
      (checkQuery.error instanceof Error
        ? checkQuery.error.message
        : "请稍后重试"));

  return (
    <div>
      {checkHardError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="检查更新失败"
          description={checkHardError}
        />
      ) : null}

      {data?.check_error ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="最新版本获取不完整"
          description={data.check_error}
        />
      ) : null}

      {data?.has_update ? (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          message={`发现新版本 ${formatVersion(data.latest_version)}`}
        />
      ) : null}

      <Descriptions
        bordered
        size="middle"
        column={1}
        style={{ maxWidth: 560, marginBottom: 20 }}
      >
        <Descriptions.Item label="当前版本">
          {formatVersion(currentVersion)}
        </Descriptions.Item>
        <Descriptions.Item label="最新版本">
          {data?.latest_version
            ? formatVersion(data.latest_version)
            : data?.check_error
              ? "获取失败"
              : "—"}
        </Descriptions.Item>
        <Descriptions.Item label="镜像">
          <Typography.Text code>{data?.image || "—"}</Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="仓库">
          <Typography.Text code>{data?.repo || "—"}</Typography.Text>
        </Descriptions.Item>
        <Descriptions.Item label="更新状态">
          {status?.state || "idle"}
          {status?.message ? ` · ${status.message}` : ""}
          {status?.error ? (
            <Typography.Text type="danger"> · {status.error}</Typography.Text>
          ) : null}
        </Descriptions.Item>
      </Descriptions>

      <Space size={12}>
        <Button
          icon={<ReloadOutlined />}
          size="large"
          loading={checkQuery.isFetching}
          onClick={() => {
            checkQuery.refetch();
            statusQuery.refetch();
          }}
        >
          检查更新
        </Button>
        <Button
          type="primary"
          icon={<CloudDownloadOutlined />}
          size="large"
          disabled={!data?.has_update || busy}
          loading={busy}
          onClick={() => {
            if (!data?.latest_version && !data?.has_update) return;
            doUpdate.mutate();
          }}
          style={{
            background: "#1a2332",
            borderColor: "#1a2332",
            color: "#fff",
          }}
        >
          {data?.has_update
            ? `更新到 ${formatVersion(data.latest_version)}`
            : "已是最新版本"}
        </Button>
      </Space>
    </div>
  );
}
