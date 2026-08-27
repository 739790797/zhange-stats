import { Alert, Button, Card, Space, Tag, Typography } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchMinecraftModTools } from "@/api/minecraftApi";
import type {
  MinecraftModInventoryJar,
  MinecraftModTools,
} from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftModToolCard } from "./MinecraftModToolCard";
import styles from "./MinecraftModToolsPanel.module.css";

function extraJars(data: MinecraftModTools) {
  const known = new Set((data.tools || []).map((row) => row.id));
  return (data.inventory?.jars || []).filter(
    (row) => !row.tool_id || !known.has(row.tool_id),
  );
}

function ExtraJarRow({ row }: { row: MinecraftModInventoryJar }) {
  const title = row.mod_names?.[0] || row.filename;
  return (
    <Card size="small" className={styles.extraCard}>
      <div className={styles.extraHead}>
        <Space align="center" wrap>
          {row.icon_url ? (
            <img className={styles.extraIcon} src={row.icon_url} alt="" />
          ) : null}
          <Typography.Text strong>{title}</Typography.Text>
          {row.mod_version ? <Tag>{row.mod_version}</Tag> : null}
          {!row.identified && !row.identify_error ? <Tag>识别中</Tag> : null}
          {row.identified && !row.project_id ? <Tag>仅本地</Tag> : null}
          {row.identify_error ? <Tag>无法读取</Tag> : null}
        </Space>
      </div>
      <div className={styles.extraMeta}>
        {row.directory}/{row.filename}
      </div>
    </Card>
  );
}

export function MinecraftModToolsPanel() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["minecraft-mod-tools"],
    queryFn: () => fetchMinecraftModTools(false),
    refetchInterval: (current) => {
      if (current.state.data?.reconcile?.running) return 2_000;
      if (current.state.data?.chunky?.state === "running") return 8_000;
      if (current.state.data?.bluemap?.state === "running") return 8_000;
      return false;
    },
    retry: 1,
  });

  if (query.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message={apiError(query.error, "无法探测模组")}
      />
    );
  }

  if (query.isLoading && !query.data) {
    return <Typography.Text type="secondary">正在读取模组库存…</Typography.Text>;
  }

  const data = query.data;
  const tools = data?.tools || [];
  const extras = data ? extraJars(data) : [];
  const reconcile = data?.reconcile;

  return (
    <div className={styles.wrap}>
      {reconcile?.running ? (
        <Alert
          type="info"
          showIcon
          message={
            reconcile.message ||
            `磁盘有变化，正在更新 ${reconcile.pending || 0} 个`
          }
        />
      ) : null}

      {data?.message ? (
        <Alert type="info" showIcon message={data.message} />
      ) : null}

      {!data?.pelican_configured && !data?.rcon_configured ? (
        <Card>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="尚未连接 Pelican / RCON"
            description="探测模组要看 /mods 与 /plugins；安装和发指令分别需要 Pelican 与 RCON。"
          />
          <Link to="/settings/integrations">
            <Button type="primary">去集成密钥配置</Button>
          </Link>
        </Card>
      ) : null}

      {data
        ? tools.map((tool) => (
            <MinecraftModToolCard key={tool.id} tool={tool} data={data} />
          ))
        : null}

      {extras.length ? (
        <div className={styles.extraList}>
          <Typography.Text type="secondary">未登记的 jar</Typography.Text>
          {extras.map((row) => (
            <ExtraJarRow key={row.path || row.filename} row={row} />
          ))}
        </div>
      ) : null}

      <div>
        <Button
          size="small"
          loading={query.isFetching}
          onClick={() =>
            queryClient.fetchQuery({
              queryKey: ["minecraft-mod-tools"],
              queryFn: () => fetchMinecraftModTools(true),
            })
          }
        >
          重新扫描
        </Button>
      </div>
    </div>
  );
}
