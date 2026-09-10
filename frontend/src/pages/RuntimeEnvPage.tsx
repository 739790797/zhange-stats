import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Radio,
  Row,
  Select,
  Space,
  Switch,
  Tag,
  message,
  theme,
} from "antd";
import { useEffect } from "react";
import { fetchRuntimeEnv, updateRuntimeEnv } from "@/api/client";
import { fetchRuntimeHealth } from "@/api/runtimeHealthApi";
import type { RuntimeHealthService } from "@/api/runtimeHealthApi";
import type { RuntimeEnvUpdate } from "@/api/settingsApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import { healthById, healthHint, healthMeta } from "@/lib/runtimeHealth";

type DepsForm = {
  db_engine: "sqlite" | "mysql";
  db_path: string;
  db_url: string;
  redis_url: string;
};

type EnvForm = {
  app_env: string;
  cors_origins: string;
  cors_origin_regex: string;
  csp_enforce: boolean;
  trust_x_forwarded_for: boolean;
};

function HealthChip({
  label,
  item,
}: {
  label: string;
  item?: RuntimeHealthService;
}) {
  if (!item) return null;
  const meta = healthMeta(item.status);
  return (
    <Tag color={meta.color} title={healthHint(item) || undefined} style={{ margin: 0 }}>
      {label} · {meta.label}
    </Tag>
  );
}

export default function RuntimeEnvPage() {
  const queryClient = useQueryClient();
  const { token } = theme.useToken();
  const [depsForm] = Form.useForm<DepsForm>();
  const [envForm] = Form.useForm<EnvForm>();
  const dbEngine = Form.useWatch("db_engine", depsForm);

  const envQuery = useQuery({
    queryKey: ["runtime-env"],
    queryFn: fetchRuntimeEnv,
  });
  const healthQuery = useQuery({
    queryKey: ["runtime-health"],
    queryFn: fetchRuntimeHealth,
  });

  const data = envQuery.data;
  const dbHealth = healthById(healthQuery.data?.services, "database");
  const redisHealth = healthById(healthQuery.data?.services, "redis");

  useEffect(() => {
    if (!data) return;
    depsForm.setFieldsValue({
      db_engine: data.db_engine === "mysql" ? "mysql" : "sqlite",
      db_path: data.db_path || "",
      db_url: data.db_url || "",
      redis_url: data.redis_url || "",
    });
    envForm.setFieldsValue({
      app_env: data.app_env || "development",
      cors_origins: data.cors_origins || "",
      cors_origin_regex: data.cors_origin_regex || "",
      csp_enforce: Boolean(data.csp_enforce),
      trust_x_forwarded_for: Boolean(data.trust_x_forwarded_for),
    });
  }, [data, depsForm, envForm]);

  const onSaved = (res: Awaited<ReturnType<typeof updateRuntimeEnv>>) => {
    queryClient.setQueryData(["runtime-env"], res);
    void queryClient.invalidateQueries({ queryKey: ["runtime-health"] });
    if (res.restart_required) {
      message.success("已写入配置，请重启后端使运行环境生效");
    } else {
      message.success("运行环境已保存");
    }
  };

  const saveDeps = useMutation({
    mutationFn: (payload: RuntimeEnvUpdate) => updateRuntimeEnv(payload),
    onSuccess: onSaved,
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const saveEnv = useMutation({
    mutationFn: (payload: RuntimeEnvUpdate) => updateRuntimeEnv(payload),
    onSuccess: onSaved,
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const cardStyle = {
    width: "100%",
    display: "flex",
    flexDirection: "column" as const,
    borderColor: token.colorBorderSecondary,
    background: token.colorFillAlter,
  };
  const cardBody = {
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
  };
  const formStyle = {
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
    minHeight: 0,
  };
  const loading = envQuery.isLoading;

  return (
    <div>
      <PageHeader title="运行环境" />
      {data?.restart_required ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="配置已保存，请重启后端进程后再核对。"
        />
      ) : null}

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} lg={12} style={{ display: "flex" }}>
          <Card
            title="本机依赖"
            size="small"
            extra={
              <Space size={8} wrap>
                <HealthChip label="数据库" item={dbHealth} />
                <HealthChip label="Redis" item={redisHealth} />
              </Space>
            }
            style={cardStyle}
            styles={{ body: cardBody }}
            loading={loading && !data}
          >
            <Form
              form={depsForm}
              layout="vertical"
              requiredMark={false}
              disabled={loading}
              initialValues={{ db_engine: "sqlite" }}
              style={formStyle}
              onFinish={(values) => {
                saveDeps.mutate({
                  db_engine: values.db_engine,
                  db_path: values.db_path || "",
                  db_url: values.db_url || "",
                  redis_url: values.redis_url || "",
                });
              }}
            >
              <Form.Item
                name="db_engine"
                label="数据库"
                rules={[{ required: true, message: "请选择数据库" }]}
              >
                <Radio.Group
                  optionType="button"
                  block
                  options={[
                    { value: "sqlite", label: "SQLite" },
                    { value: "mysql", label: "MySQL / MariaDB" },
                  ]}
                />
              </Form.Item>
              {dbEngine === "mysql" ? (
                <Form.Item
                  name="db_url"
                  label="连接串"
                  rules={[{ required: true, message: "请填写连接串" }]}
                >
                  <Input placeholder="mysql+pymysql://user:pass@127.0.0.1:3306/zhange" />
                </Form.Item>
              ) : (
                <Form.Item name="db_path" label="数据文件">
                  <Input placeholder="data/runtime/zhange.sqlite" />
                </Form.Item>
              )}
              <Form.Item name="redis_url" label="Redis">
                <Input placeholder="redis://127.0.0.1:6379/0" />
              </Form.Item>
              <div style={{ marginTop: "auto", paddingTop: 8 }}>
                <Button type="primary" htmlType="submit" loading={saveDeps.isPending}>
                  保存
                </Button>
              </div>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={12} style={{ display: "flex" }}>
          <Card
            title="环境"
            size="small"
            style={cardStyle}
            styles={{ body: cardBody }}
            loading={loading && !data}
          >
            <Form
              form={envForm}
              layout="vertical"
              requiredMark={false}
              disabled={loading}
              style={formStyle}
              onFinish={(values) => {
                saveEnv.mutate({
                  app_env: values.app_env,
                  cors_origins: values.cors_origins || "",
                  cors_origin_regex: values.cors_origin_regex || "",
                  csp_enforce: Boolean(values.csp_enforce),
                  trust_x_forwarded_for: Boolean(values.trust_x_forwarded_for),
                });
              }}
            >
              <Form.Item
                name="app_env"
                label="APP_ENV"
                rules={[{ required: true, message: "请选择环境" }]}
              >
                <Select
                  options={[
                    { value: "development", label: "development" },
                    { value: "production", label: "production" },
                  ]}
                />
              </Form.Item>
              <Form.Item name="cors_origins" label="CORS_ORIGINS">
                <Input placeholder="https://stats.example.com" />
              </Form.Item>
              <Form.Item name="cors_origin_regex" label="CORS_ORIGIN_REGEX">
                <Input />
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="csp_enforce"
                    label="强制 CSP"
                    valuePropName="checked"
                  >
                    <Switch
                      checkedChildren="enforce"
                      unCheckedChildren="Report-Only"
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="trust_x_forwarded_for"
                    label="信任 X-Forwarded-For"
                    valuePropName="checked"
                  >
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>
              <div style={{ marginTop: "auto", paddingTop: 8 }}>
                <Button type="primary" htmlType="submit" loading={saveEnv.isPending}>
                  保存
                </Button>
              </div>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
