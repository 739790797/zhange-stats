import { Alert, Button, Card, Typography } from "antd";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchMinecraftModTools } from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftModToolCard } from "./MinecraftModToolCard";
import styles from "./MinecraftModToolsPanel.module.css";

export function MinecraftModToolsPanel() {
  const query = useQuery({
    queryKey: ["minecraft-mod-tools"],
    queryFn: () => fetchMinecraftModTools(true),
    refetchInterval: (current) =>
      current.state.data?.chunky?.state === "running" ? 8_000 : false,
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
    return <Typography.Text type="secondary">正在探测服内模组…</Typography.Text>;
  }

  const data = query.data;
  const tools = data?.tools || [];

  return (
    <div className={styles.wrap}>
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
    </div>
  );
}
