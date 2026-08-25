import {
  CaretRightOutlined,
  ReloadOutlined,
  BorderOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Popconfirm,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { Link } from "react-router-dom";
import { Suspense, lazy, type ReactNode } from "react";
import {
  fetchMinecraftStatus,
  sendMinecraftPower,
  type MinecraftPowerSignal,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftConsoleView } from "./MinecraftConsole";
import { MinecraftResourceCharts } from "./MinecraftResourceCharts";
import {
  formatBytes,
  formatLimit,
  formatUptime,
  isServerLive,
  powerLabel,
} from "./minecraftUi";
import { useMinecraftConsole } from "./useMinecraftConsole";

const MinecraftFileManager = lazy(() =>
  import("./MinecraftFileManager").then((m) => ({
    default: m.MinecraftFileManager,
  })),
);

function InfoTile({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <Card
      size="small"
      styles={{ body: { minHeight: 72, padding: "12px 16px" } }}
    >
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {label}
      </Typography.Text>
      <div
        style={{
          fontSize: 16,
          fontWeight: 600,
          marginTop: 6,
          lineHeight: 1.35,
          wordBreak: "break-all",
        }}
      >
        {value}
      </div>
    </Card>
  );
}

export function MinecraftManagePanel() {
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ["minecraft-status"],
    queryFn: fetchMinecraftStatus,
    refetchInterval: 10_000,
    retry: 1,
  });

  const status = statusQuery.data;
  const pelicanConfigured = Boolean(status?.pelican_configured);
  const console = useMinecraftConsole(pelicanConfigured);
  const liveState = console.status || status?.power_state;
  const live = isServerLive(liveState);
  const tag = powerLabel(liveState);

  const power = useMutation({
    mutationFn: (signal: MinecraftPowerSignal) => sendMinecraftPower(signal),
    onSuccess: (res) => {
      message.success(res.message);
      queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "电源指令失败")),
  });

  if (statusQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message={apiError(statusQuery.error, "无法读取服况")}
      />
    );
  }

  if (statusQuery.isLoading) {
    return (
      <Typography.Text type="secondary">加载中…</Typography.Text>
    );
  }

  if (!pelicanConfigured) {
    return (
      <Card>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="尚未连接 Pelican"
          description="填好 Panel 地址、Client Token 和这台服的 UUID 之后，才能在这里启停和控制台。游戏进程仍在 Pelican 里，战鸽只作为操作入口。"
        />
        <Link to="/settings/integrations">
          <Button type="primary">
            去集成密钥配置
          </Button>
        </Link>
      </Card>
    );
  }

  const stats = console.stats;
  const meta = console.meta;
  // 上限只用来自 Pelican 面板的 limits（开服/资源配置，0 = 不限制）。
  // 不要用 Wings stats.*_limit_bytes：限额为 0 时它会回报整机内存。
  const memLimit = meta?.memory_limit_mb
    ? meta.memory_limit_mb * 1024 * 1024
    : 0;
  const diskLimit = meta?.disk_limit_mb
    ? meta.disk_limit_mb * 1024 * 1024
    : 0;
  const cpuLimit = meta?.cpu_limit || 0;
  const name = meta?.name || "Minecraft";
  const address = meta?.address || status?.address || "—";
  const uptime =
    stats?.uptime_ms && liveState === "running"
      ? formatUptime(stats.uptime_ms)
      : "";

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <Space align="center" wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>
            控制台
          </Typography.Title>
          {console.error ? (
            <Tag color="red">已断开</Tag>
          ) : console.ready ? (
            <Tag color="green">已连接</Tag>
          ) : (
            <Tag>连接中</Tag>
          )}
        </Space>
        <Space wrap>
          <Button
            type="primary"
            icon={<CaretRightOutlined />}
            loading={power.isPending}
            disabled={live}
            onClick={() => power.mutate("start")}
          >
            启动
          </Button>
          <Popconfirm
            title="确定重启这台服？"
            okText="重启"
            cancelText="取消"
            disabled={!live || power.isPending}
            onConfirm={() => power.mutate("restart")}
          >
            <Button
              icon={<ReloadOutlined />}
              loading={power.isPending}
              disabled={!live}
            >
              重启
            </Button>
          </Popconfirm>
          <Popconfirm
            title="确定停止这台服？"
            okText="停止"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            disabled={!live || power.isPending}
            onConfirm={() => power.mutate("stop")}
          >
            <Button
              danger
              type="primary"
              icon={<BorderOutlined />}
              loading={power.isPending}
              disabled={!live}
            >
              停止
            </Button>
          </Popconfirm>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <InfoTile label="名称" value={name} />
        </Col>
        <Col xs={24} md={8}>
          <InfoTile
            label="状态"
            value={
              <span>
                <Tag color={tag.color} style={{ marginInlineEnd: 8 }}>
                  {tag.text}
                </Tag>
                {liveState === "running" && status?.rcon_connected === true ? (
                  <Tag color="green" style={{ marginInlineEnd: 8 }}>
                    RCON
                  </Tag>
                ) : liveState === "running" && status?.rcon_connected === false ? (
                  <Tag style={{ marginInlineEnd: 8 }}>RCON 断开</Tag>
                ) : null}
                {uptime ? (
                  <Typography.Text type="secondary" style={{ fontWeight: 400 }}>
                    {uptime}
                  </Typography.Text>
                ) : null}
              </span>
            }
          />
        </Col>
        <Col xs={24} md={8}>
          <InfoTile
            label="地址"
            value={
              address && address !== "—" ? (
                <Typography.Text copyable={{ text: address }} style={{ fontSize: 16, fontWeight: 600 }}>
                  {address}
                </Typography.Text>
              ) : (
                "—"
              )
            }
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <InfoTile
            label="CPU"
            value={
              stats
                ? `${stats.cpu.toFixed(1)}% / ${cpuLimit > 0 ? `${cpuLimit}%` : "∞"}`
                : "—"
            }
          />
        </Col>
        <Col xs={24} md={8}>
          <InfoTile
            label="内存"
            value={
              stats
                ? `${formatBytes(stats.memory_bytes)} / ${formatLimit(memLimit)}`
                : "—"
            }
          />
        </Col>
        <Col xs={24} md={8}>
          <InfoTile
            label="磁盘"
            value={
              stats
                ? `${formatBytes(stats.disk_bytes)} / ${formatLimit(diskLimit)}`
                : "—"
            }
          />
        </Col>
      </Row>

      <MinecraftConsoleView
        preRef={console.preRef}
        command={console.command}
        onCommandChange={console.setCommand}
        onSend={console.sendCommand}
        ready={console.ready}
        error={console.error}
        empty={!console.hasOutput}
      />

      <MinecraftResourceCharts
        history={console.history}
        cpu={stats?.cpu || 0}
        cpuLimit={cpuLimit}
        memory={stats?.memory_bytes || 0}
        memoryLimit={memLimit}
        rxTotal={stats?.network_rx_bytes || 0}
        txTotal={stats?.network_tx_bytes || 0}
      />

      <Divider style={{ margin: "32px 0 16px" }} />

      <Suspense
        fallback={
          <div style={{ padding: 48, textAlign: "center" }}>
            <Spin>
              <Typography.Text type="secondary">加载文件管理…</Typography.Text>
            </Spin>
          </div>
        }
      >
        <MinecraftFileManager />
      </Suspense>
    </div>
  );
}
