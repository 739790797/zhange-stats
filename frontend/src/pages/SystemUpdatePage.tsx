import { CloudSyncOutlined, ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Modal,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useRef, useState } from "react";
import {
  checkAppUpdate,
  doAppUpdate,
  fetchAppUpdateStatus,
  waitForHealthVersion,
} from "@/api/appUpdateApi";
import type { AppUpdateStatus } from "@/api/appUpdateApi";
import { PageHeader } from "@/components/PageHeader";
import { APP_VERSION_QUERY_KEY } from "@/hooks/useServerAppVersion";
import { apiError } from "@/lib/apiError";

/** 新版本起来后留一会儿提示再整页刷新，换上新版本的前端包。 */
const RELOAD_AFTER_UPDATE_MS = 1500;

export default function SystemUpdatePage() {
  const queryClient = useQueryClient();
  const [waitingRestart, setWaitingRestart] = useState(false);
  const [reloadingPage, setReloadingPage] = useState(false);
  const waitAbortRef = useRef<AbortController | null>(null);

  useEffect(() => () => waitAbortRef.current?.abort(), []);

  const statusQuery = useQuery({
    queryKey: ["app-update-status"],
    queryFn: fetchAppUpdateStatus,
    refetchInterval: (q) =>
      q.state.data?.busy || waitingRestart ? 2000 : false,
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
        reboot: true,
      }),
    onSuccess: async (data) => {
      message.success(data.message);
      queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
      if (data.reboot && data.version) {
        waitAbortRef.current?.abort();
        const controller = new AbortController();
        waitAbortRef.current = controller;
        setWaitingRestart(true);
        try {
          const ver = await waitForHealthVersion(data.version, {
            signal: controller.signal,
            shouldAbort: async () => {
              // 后台任务失败时尽早退出，不要干等 /health 版本
              await queryClient.refetchQueries({
                queryKey: ["app-update-status"],
              });
              const st = queryClient.getQueryData<AppUpdateStatus>([
                "app-update-status",
              ]);
              return st?.error || null;
            },
          });
          message.success(`服务已恢复 · v${ver}，即将刷新页面`);
          queryClient.invalidateQueries({ queryKey: APP_VERSION_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
          setReloadingPage(true);
          window.setTimeout(() => window.location.reload(), RELOAD_AFTER_UPDATE_MS);
        } catch (e: unknown) {
          if (controller.signal.aborted) return;
          const st = queryClient.getQueryData<AppUpdateStatus>([
            "app-update-status",
          ]);
          if (st?.error) {
            message.error(st.error);
          } else {
            message.error(apiError(e, "请手动刷新确认是否已更新"));
          }
        } finally {
          if (waitAbortRef.current === controller) waitAbortRef.current = null;
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
    reloadingPage ||
    checkMutation.isPending;

  return (
    <div>
      <PageHeader title="系统更新" />

      <Card loading={statusQuery.isLoading}>
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <Space align="center" wrap size={8}>
              <Typography.Text type="secondary">当前版本</Typography.Text>
              <Typography.Title level={3} style={{ margin: 0, lineHeight: 1.2 }}>
                v{status?.current_version || "—"}
              </Typography.Title>
              {status?.has_new_version ? (
                <Tag color="processing">有新版本 v{status.latest_version}</Tag>
              ) : (
                <Tag>已是最新或未检查</Tag>
              )}
              {reloadingPage ? (
                <Tag color="success">即将刷新页面…</Tag>
              ) : status?.busy || waitingRestart ? (
                <Tag color="warning">
                  {waitingRestart
                    ? "等待服务恢复…"
                    : `${status?.phase || "busy"} · ${status?.message || ""}`}
                </Tag>
              ) : null}
            </Space>
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
                loading={updateMutation.isPending || waitingRestart || reloadingPage}
                disabled={!status?.update_allowed || busy}
                onClick={() => {
                  if (!status?.update_allowed || busy) return;
                  const hasNew = Boolean(status.has_new_version);
                  Modal.confirm({
                    title: hasNew
                      ? `更新到 v${status.latest_version}？`
                      : "没有检测到新版本，仍要更新？",
                    content: hasNew
                      ? "会下载发布包、执行数据库迁移并重启服务，期间站点会短暂不可用；迁移失败会回滚，不重启。"
                      : "可能已是最新，也可能还没点「检查更新」。继续会重新拉取 latest、执行迁移并重启服务，期间站点会短暂不可用。",
                    okText: hasNew ? "更新并重启" : "仍要更新",
                    okButtonProps: hasNew ? undefined : { danger: true },
                    onOk: () => updateMutation.mutate(),
                  });
                }}
              >
                一键更新
              </Button>
            </Space>
          </div>

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
        </Space>
      </Card>
    </div>
  );
}
