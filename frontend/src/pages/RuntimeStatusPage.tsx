import { ReloadOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Tag, Typography, theme } from "antd";
import { fetchRuntimeHealth } from "@/api/runtimeHealthApi";
import type { RuntimeHealthService } from "@/api/runtimeHealthApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import {
  healthHint,
  healthMeta,
  pickHealthServices,
  RUNTIME_NOTE_IDS,
  RUNTIME_STATUS_IDS,
  runtimeNoteLabel,
} from "@/lib/runtimeHealth";

function StatusChip({ item }: { item: RuntimeHealthService }) {
  const { token } = theme.useToken();
  const meta = healthMeta(item.status);
  return (
    <div
      style={{
        minWidth: 140,
        flex: "1 1 140px",
        padding: "10px 12px",
        borderRadius: 8,
        border: `1px solid ${token.colorBorderSecondary}`,
        background: token.colorFillAlter,
      }}
      title={healthHint(item) || undefined}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <Typography.Text strong style={{ fontSize: 13 }}>
          {item.name}
        </Typography.Text>
        <Tag color={meta.color} style={{ margin: 0 }}>
          {meta.label}
        </Tag>
      </div>
    </div>
  );
}

export default function RuntimeStatusPage() {
  const { token } = theme.useToken();
  const healthQuery = useQuery({
    queryKey: ["runtime-health"],
    queryFn: fetchRuntimeHealth,
  });

  const services = healthQuery.data?.services ?? [];
  const chips = pickHealthServices(services, RUNTIME_STATUS_IDS);
  const notes = pickHealthServices(services, RUNTIME_NOTE_IDS);
  const cardStyle = {
    marginBottom: 16,
    borderColor: token.colorBorderSecondary,
    background: token.colorFillAlter,
  } as const;

  return (
    <div>
      <PageHeader
        title="运行状态"
        subtitle="本机依赖是否可用。运行环境与访客 IP 是部署核对，不是独立服务。"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => healthQuery.refetch()}
            loading={healthQuery.isFetching}
          >
            刷新
          </Button>
        }
      />

      {healthQuery.isError ? (
        <Typography.Text type="danger">
          {apiError(healthQuery.error, "加载运行状态失败")}
        </Typography.Text>
      ) : (
        <>
          <Card title="本机依赖" size="small" loading={healthQuery.isLoading} style={cardStyle}>
            {chips.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                {chips.map((item) => (
                  <StatusChip key={item.id} item={item} />
                ))}
              </div>
            ) : (
              <Typography.Text type="secondary">暂无依赖状态</Typography.Text>
            )}
            {healthQuery.data?.checked_at ? (
              <Typography.Paragraph type="secondary" style={{ margin: "12px 0 0" }}>
                探测于 {healthQuery.data.checked_at}
              </Typography.Paragraph>
            ) : null}
          </Card>

          <Card title="部署核对" size="small" loading={healthQuery.isLoading} style={cardStyle}>
            {notes.length ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {notes.map((item) => (
                  <div key={item.id}>
                    <Typography.Text strong>{runtimeNoteLabel(item)}</Typography.Text>
                    <Typography.Paragraph type="secondary" style={{ margin: "4px 0 0" }}>
                      {item.detail || "—"}
                    </Typography.Paragraph>
                  </div>
                ))}
              </div>
            ) : (
              <Typography.Text type="secondary">暂无部署说明</Typography.Text>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
