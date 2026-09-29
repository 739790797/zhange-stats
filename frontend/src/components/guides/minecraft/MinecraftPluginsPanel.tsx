import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Typography } from "antd";
import { fetchMinecraftFiles } from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";

export function MinecraftPluginsPanel() {
  const query = useQuery({
    queryKey: ["minecraft-files", "/plugins"],
    queryFn: () => fetchMinecraftFiles("/plugins"),
    retry: 1,
  });
  const jars = (query.data?.entries || []).filter(
    (row) => row.is_file && row.name.toLowerCase().endsWith(".jar"),
  );

  return (
    <Card size="small" title="插件">
      {query.isError ? (
        <Alert
          type="info"
          showIcon
          message={apiError(query.error, "还不能读取 plugins 目录")}
          description="核心启动一次之后，插件 jar 会列在这里。"
        />
      ) : (
        <>
          <Typography.Paragraph type="secondary">
            目录 plugins/。把 jar 放进来或从这里核对已有文件。
          </Typography.Paragraph>
          {jars.length ? (
            jars.map((row) => (
              <div key={row.name}>{row.name}</div>
            ))
          ) : (
            <Typography.Text type="secondary">目录里还没有 jar。</Typography.Text>
          )}
        </>
      )}
    </Card>
  );
}
