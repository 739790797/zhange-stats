import { CloudDownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Space, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  checkUpdate,
  fetchUpdateStatus,
  triggerUpdate,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

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

export default function SystemUpdatePage() {
  const queryClient = useQueryClient();
  const [waiting, setWaiting] = useState(false);
  const previousVersion = useRef("");

  const checkQuery = useQuery({
    queryKey: ["update-check"],
    queryFn: checkUpdate,
    refetchOnWindowFocus: false,
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
    if (checkQuery.data?.current_version) {
      previousVersion.current = checkQuery.data.current_version;
    }
  }, [checkQuery.data?.current_version]);

  const doUpdate = useMutation({
    mutationFn: triggerUpdate,
    onSuccess: async () => {
      message.info("已开始更新，服务会短暂中断…");
      setWaiting(true);
      queryClient.invalidateQueries({ queryKey: ["update-status"] });
      try {
        const prev =
          previousVersion.current || checkQuery.data?.current_version || "";
        const next = await waitForNewVersion(prev);
        message.success(`已更新到 v${next}`);
        window.location.reload();
      } catch (e: unknown) {
        message.error(e instanceof Error ? e.message : "更新等待失败");
      } finally {
        setWaiting(false);
        queryClient.invalidateQueries({ queryKey: ["update-check"] });
        queryClient.invalidateQueries({ queryKey: ["update-status"] });
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
  const busy =
    waiting ||
    doUpdate.isPending ||
    status?.state === "pulling" ||
    status?.state === "recreating";

  return (
    <div>
      <PageHeader
        title="系统更新"
        subtitle="拉取新镜像并重建应用容器（需 Docker 部署且启用 UPDATE_ENABLED）"
        extra={
          <Space>
            <Link to="/settings/users">用户管理</Link>
            <Link to="/settings/email">邮箱设置</Link>
          </Space>
        }
      />

      {checkQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="检查更新失败"
          description={
            (checkQuery.error as { response?: { data?: { detail?: string } } })
              ?.response?.data?.detail ||
            (checkQuery.error instanceof Error
              ? checkQuery.error.message
              : "请稍后重试")
          }
        />
      ) : null}

      {!data?.update_enabled ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前未启用在线更新"
          description={
            <>
              请确认已挂载 docker.sock 与 compose.yml，并设置{" "}
              <Typography.Text code>UPDATE_ENABLED=true</Typography.Text>。
              挂载 docker.sock 等同授予容器宿主机 Docker 管理权限，仅信任的管理员环境再开启。
            </>
          }
        />
      ) : (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="安全提示"
          description="在线更新通过 docker.sock 操作宿主机容器。请确保仅管理员可登录，并知晓此权限等同 Docker 主机管理能力。"
        />
      )}

      <Descriptions
        bordered
        size="middle"
        column={1}
        style={{ maxWidth: 560, marginBottom: 20 }}
      >
        <Descriptions.Item label="当前版本">
          {data?.current_version ? `v${data.current_version}` : "—"}
        </Descriptions.Item>
        <Descriptions.Item label="最新版本">
          {data?.latest_version ? `v${data.latest_version}` : "暂无 Release / Tag"}
        </Descriptions.Item>
        <Descriptions.Item label="镜像">
          <Typography.Text code>{data?.image || "—"}</Typography.Text>
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
          onClick={() => checkQuery.refetch()}
        >
          检查更新
        </Button>
        <Button
          type="primary"
          icon={<CloudDownloadOutlined />}
          size="large"
          disabled={!data?.update_enabled || !data?.has_update || busy}
          loading={busy}
          onClick={() => {
            if (!data?.latest_version) return;
            doUpdate.mutate();
          }}
          style={{ background: "#1a2332", borderColor: "#1a2332" }}
        >
          {data?.has_update
            ? `更新到 v${data.latest_version}`
            : "已是最新版本"}
        </Button>
      </Space>

      <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
        发版方式：在 GitHub 打 <Typography.Text code>v*</Typography.Text>{" "}
        标签，Actions 会构建并推送到 GHCR；此处检查的是仓库最新 Release/Tag。
      </Typography.Paragraph>
    </div>
  );
}
