import { CloudSyncOutlined, ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useState } from "react";
import {
  checkAppUpdate,
  doAppUpdate,
  fetchAppUpdateStatus,
  waitForHealthVersion,
} from "@/api/appUpdateApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";

export default function SystemUpdatePage() {
  const queryClient = useQueryClient();
  const [proxy, setProxy] = useState("");
  const [waitingRestart, setWaitingRestart] = useState(false);

  const statusQuery = useQuery({
    queryKey: ["app-update-status"],
    queryFn: fetchAppUpdateStatus,
    refetchInterval: (q) => (q.state.data?.busy ? 2000 : false),
  });

  const checkMutation = useMutation({
    mutationFn: checkAppUpdate,
    onSuccess: (data) => {
      queryClient.setQueryData(["app-update-status"], data.status);
      if (data.status.has_new_version) {
        message.success(`发现新版本 v${data.status.latest_version}`);
      } else {
        message.info("已是最新版本");
      }
    },
    onError: (e: unknown) => message.error(apiError(e, "检查更新失败")),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      doAppUpdate({
        version: "latest",
        proxy: proxy.trim() || null,
        reboot: true,
      }),
    onSuccess: async (data) => {
      message.success(data.message);
      queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
      if (data.reboot && data.version) {
        setWaitingRestart(true);
        try {
          const ver = await waitForHealthVersion(data.version);
          message.success(`服务已恢复 · v${ver}`);
          queryClient.invalidateQueries({ queryKey: ["app-version"] });
          queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
        } catch (e: unknown) {
          message.warning(
            e instanceof Error ? e.message : "请手动刷新确认是否已更新",
          );
        } finally {
          setWaitingRestart(false);
        }
      }
    },
    onError: (e: unknown) => message.error(apiError(e, "更新失败")),
  });

  const status = statusQuery.data;
  const busy =
    Boolean(status?.busy) ||
    updateMutation.isPending ||
    waitingRestart ||
    checkMutation.isPending;

  return (
    <div>
      <PageHeader
        title="系统更新"
        subtitle="从 GitHub Release 下载源码与预构建前端，安装依赖后重启（类似 AstrBot 一键更新）"
      />

      {!status?.update_allowed && status && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前环境不可用应用内更新"
          description={
            status.update_blocked_reason ||
            "仅 production（LXC）默认开启；开发机请用 git / scripts/dev.ps1"
          }
        />
      )}

      <Card loading={statusQuery.isLoading} style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div>
            <Typography.Text type="secondary">当前版本</Typography.Text>
            <div>
              <Typography.Title level={3} style={{ margin: 0 }}>
                v{status?.current_version || "—"}
              </Typography.Title>
            </div>
          </div>

          <Space wrap>
            {status?.has_new_version ? (
              <Tag color="processing">有新版本 v{status.latest_version}</Tag>
            ) : (
              <Tag>已是最新或未检查</Tag>
            )}
            {status?.restart_strategy ? (
              <Tag>重启: {status.restart_strategy}</Tag>
            ) : null}
            {status?.busy || waitingRestart ? (
              <Tag color="warning">
                {waitingRestart
                  ? "等待服务恢复…"
                  : `${status?.phase || "busy"} · ${status?.message || ""}`}
              </Tag>
            ) : null}
          </Space>

          {status?.latest_body ? (
            <Typography.Paragraph
              type="secondary"
              style={{ whiteSpace: "pre-wrap", marginBottom: 0 }}
            >
              {status.latest_body.slice(0, 2000)}
            </Typography.Paragraph>
          ) : null}

          {status?.error ? (
            <Alert type="error" showIcon message={status.error} />
          ) : null}

          <Typography.Text type="secondary" copyable={Boolean(status?.install_dir)}>
            安装根：{status?.install_dir || "—"}
          </Typography.Text>

          <Form layout="vertical" style={{ maxWidth: 480 }}>
            <Form.Item
              label="GitHub 代理前缀（可选）"
              extra="例如 https://ghproxy.example.com ，将拼在下载 URL 前"
            >
              <Input
                value={proxy}
                onChange={(e) => setProxy(e.target.value)}
                placeholder="留空则直连 GitHub"
                disabled={busy}
              />
            </Form.Item>
          </Form>

          <Space wrap>
            <Button
              icon={<ReloadOutlined />}
              loading={checkMutation.isPending}
              disabled={busy && !checkMutation.isPending}
              onClick={() => checkMutation.mutate()}
            >
              检查更新
            </Button>
            <Button
              type="primary"
              icon={<CloudSyncOutlined />}
              loading={updateMutation.isPending || waitingRestart}
              disabled={!status?.update_allowed || busy}
              onClick={() => {
                if (!status?.has_new_version) {
                  message.info("未检测到新版本，仍将尝试更新到 latest");
                }
                updateMutation.mutate();
              }}
            >
              一键更新
            </Button>
          </Space>
        </Space>
      </Card>
    </div>
  );
}
