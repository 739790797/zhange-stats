import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
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
import {
  fetchRuntimeEnv,
  testRuntimeDatabase,
  testRuntimeRedis,
  updateRuntimeEnv,
} from "@/api/client";
import { fetchRuntimeHealth } from "@/api/runtimeHealthApi";
import type { RuntimeHealthService } from "@/api/runtimeHealthApi";
import type { RuntimeEnvUpdate } from "@/api/settingsApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import {
  MYSQL_CONN_DEFAULTS,
  REDIS_CONN_DEFAULTS,
  composeMysqlUrl,
  composeRedisUrl,
  parseMysqlUrl,
  parseRedisUrl,
} from "@/lib/runtimeConn";
import { healthById, healthHint, healthMeta } from "@/lib/runtimeHealth";

type DbForm = {
  db_engine: "sqlite" | "mysql";
  db_path: string;
  host: string;
  port: number | null;
  user: string;
  password: string;
  database: string;
};

type RedisForm = {
  host: string;
  port: number | null;
  user: string;
  password: string;
  db: number | null;
  tls: boolean;
};

type EnvForm = {
  app_env: string;
  cors_origins: string;
  cors_origin_regex: string;
  csp_enforce: boolean;
  trust_x_forwarded_for: boolean;
};

function isFormValidateError(e: unknown): boolean {
  return Boolean(
    e &&
      typeof e === "object" &&
      Array.isArray((e as { errorFields?: unknown }).errorFields),
  );
}

function HealthChip({ item }: { item?: RuntimeHealthService }) {
  if (!item) return null;
  const meta = healthMeta(item.status);
  return (
    <Tag color={meta.color} title={healthHint(item) || undefined} style={{ margin: 0 }}>
      {meta.label}
    </Tag>
  );
}

function CardActions({
  onTest,
  testLoading,
  saveLoading,
}: {
  onTest?: () => void;
  testLoading?: boolean;
  saveLoading: boolean;
}) {
  return (
    <div style={{ marginTop: "auto", paddingTop: 8 }}>
      <Space>
        {onTest ? (
          <Button htmlType="button" loading={testLoading} onClick={onTest}>
            测试连接
          </Button>
        ) : null}
        <Button type="primary" htmlType="submit" loading={saveLoading}>
          保存
        </Button>
      </Space>
    </div>
  );
}

const portItemRules = [
  { required: true, message: "请填写端口" },
  { type: "number" as const, min: 1, max: 65535, message: "端口 1～65535" },
];

function mysqlUrlFromForm(values: DbForm): string {
  return composeMysqlUrl({
    host: values.host,
    port: values.port ?? MYSQL_CONN_DEFAULTS.port,
    user: values.user,
    password: values.password,
    database: values.database,
  });
}

function redisUrlFromForm(values: RedisForm): string {
  return composeRedisUrl({
    host: values.host,
    port: values.port ?? REDIS_CONN_DEFAULTS.port,
    user: values.user || "",
    password: values.password || "",
    db: values.db ?? REDIS_CONN_DEFAULTS.db,
    tls: Boolean(values.tls),
  });
}

export default function RuntimeEnvPage() {
  const queryClient = useQueryClient();
  const { token } = theme.useToken();
  const [dbForm] = Form.useForm<DbForm>();
  const [redisForm] = Form.useForm<RedisForm>();
  const [envForm] = Form.useForm<EnvForm>();
  const dbEngine = Form.useWatch("db_engine", dbForm);

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
    const mysql = parseMysqlUrl(data.db_url || "");
    dbForm.setFieldsValue({
      db_engine: data.db_engine === "mysql" ? "mysql" : "sqlite",
      db_path: data.db_path || "",
      host: mysql.host,
      port: mysql.port,
      user: mysql.user,
      password: mysql.password,
      database: mysql.database,
    });
    redisForm.setFieldsValue(parseRedisUrl(data.redis_url || ""));
    envForm.setFieldsValue({
      app_env: data.app_env || "development",
      cors_origins: data.cors_origins || "",
      cors_origin_regex: data.cors_origin_regex || "",
      csp_enforce: Boolean(data.csp_enforce),
      trust_x_forwarded_for: Boolean(data.trust_x_forwarded_for),
    });
  }, [data, dbForm, redisForm, envForm]);

  const onSaved = (res: Awaited<ReturnType<typeof updateRuntimeEnv>>) => {
    queryClient.setQueryData(["runtime-env"], res);
    void queryClient.invalidateQueries({ queryKey: ["runtime-health"] });
    if (res.restart_required) {
      message.success("已写入配置，请重启后端使运行环境生效");
    } else {
      message.success("运行环境已保存");
    }
  };

  const saveOpts = {
    mutationFn: (payload: RuntimeEnvUpdate) => updateRuntimeEnv(payload),
    onSuccess: onSaved,
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  };
  const saveDb = useMutation(saveOpts);
  const saveRedis = useMutation(saveOpts);
  const saveEnv = useMutation(saveOpts);

  const onTested = (res: Awaited<ReturnType<typeof testRuntimeDatabase>>) => {
    if (res.ok) {
      const ms =
        res.latency_ms != null && Number.isFinite(res.latency_ms)
          ? `（${Math.round(res.latency_ms)}ms）`
          : "";
      message.success(`${res.message}${ms}`);
    } else {
      message.warning(res.message);
    }
  };

  const testDb = useMutation({
    mutationFn: async () => {
      const values = await dbForm.validateFields();
      if (values.db_engine === "mysql") {
        return testRuntimeDatabase({
          db_engine: "mysql",
          db_path: values.db_path || "",
          db_url: mysqlUrlFromForm(values),
        });
      }
      return testRuntimeDatabase({
        db_engine: "sqlite",
        db_path: values.db_path || "",
        db_url: "",
      });
    },
    onSuccess: onTested,
    onError: (e: unknown) => {
      if (isFormValidateError(e)) return;
      message.error(apiError(e, "测试失败"));
    },
  });

  const testRedis = useMutation({
    mutationFn: async () => {
      const redis_url = redisUrlFromForm(redisForm.getFieldsValue());
      if (!redis_url) {
        return { ok: false, message: "请填写主机后再测试", latency_ms: null };
      }
      return testRuntimeRedis({ redis_url });
    },
    onSuccess: onTested,
    onError: (e: unknown) => message.error(apiError(e, "测试失败")),
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
  const cardLoading = loading && !data;
  const colStyle = { display: "flex" as const };
  const mysqlRequired = dbEngine === "mysql";

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
        <Col xs={24} md={12} xl={8} style={colStyle}>
          <Card
            title="数据库"
            size="small"
            extra={<HealthChip item={dbHealth} />}
            style={cardStyle}
            styles={{ body: cardBody }}
            loading={cardLoading}
          >
            <Form
              form={dbForm}
              layout="vertical"
              requiredMark={false}
              disabled={loading}
              initialValues={{
                db_engine: "sqlite",
                ...MYSQL_CONN_DEFAULTS,
              }}
              style={formStyle}
              onFinish={(values) => {
                if (values.db_engine === "mysql") {
                  saveDb.mutate({
                    db_engine: "mysql",
                    db_path: values.db_path || "",
                    db_url: mysqlUrlFromForm(values),
                  });
                  return;
                }
                saveDb.mutate({
                  db_engine: "sqlite",
                  db_path: values.db_path || "",
                  db_url: "",
                });
              }}
            >
              <Form.Item
                name="db_engine"
                label="引擎"
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
              {mysqlRequired ? (
                <>
                  <Row gutter={8}>
                    <Col span={16}>
                      <Form.Item
                        name="host"
                        label="主机"
                        rules={[{ required: true, message: "请填写主机" }]}
                      >
                        <Input placeholder="127.0.0.1" autoComplete="off" />
                      </Form.Item>
                    </Col>
                    <Col span={8}>
                      <Form.Item name="port" label="端口" rules={portItemRules}>
                        <InputNumber
                          min={1}
                          max={65535}
                          precision={0}
                          style={{ width: "100%" }}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={8}>
                    <Col span={12}>
                      <Form.Item
                        name="user"
                        label="用户名"
                        rules={[{ required: true, message: "请填写用户名" }]}
                      >
                        <Input placeholder="root" autoComplete="off" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="password" label="密码">
                        <Input.Password autoComplete="new-password" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item
                    name="database"
                    label="数据库"
                    rules={[{ required: true, message: "请填写数据库名" }]}
                  >
                    <Input placeholder="zhange" autoComplete="off" />
                  </Form.Item>
                </>
              ) : (
                <Form.Item name="db_path" label="数据文件">
                  <Input placeholder="data/runtime/zhange.sqlite" />
                </Form.Item>
              )}
              <CardActions
                onTest={() => testDb.mutate()}
                testLoading={testDb.isPending}
                saveLoading={saveDb.isPending}
              />
            </Form>
          </Card>
        </Col>

        <Col xs={24} md={12} xl={8} style={colStyle}>
          <Card
            title="Redis"
            size="small"
            extra={<HealthChip item={redisHealth} />}
            style={cardStyle}
            styles={{ body: cardBody }}
            loading={cardLoading}
          >
            <Form
              form={redisForm}
              layout="vertical"
              requiredMark={false}
              disabled={loading}
              initialValues={REDIS_CONN_DEFAULTS}
              style={formStyle}
              onFinish={(values) => {
                saveRedis.mutate({
                  redis_url: redisUrlFromForm(values),
                });
              }}
            >
              <Form.Item name="user" hidden>
                <Input />
              </Form.Item>
              <Row gutter={8}>
                <Col span={16}>
                  <Form.Item name="host" label="主机">
                    <Input placeholder="127.0.0.1" autoComplete="off" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="port" label="端口">
                    <InputNumber
                      min={1}
                      max={65535}
                      precision={0}
                      placeholder="6379"
                      style={{ width: "100%" }}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="password" label="密码">
                <Input.Password autoComplete="new-password" />
              </Form.Item>
              <Row gutter={8}>
                <Col span={12}>
                  <Form.Item name="db" label="库号">
                    <InputNumber min={0} precision={0} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="tls" label="TLS" valuePropName="checked">
                    <Switch checkedChildren="rediss" unCheckedChildren="redis" />
                  </Form.Item>
                </Col>
              </Row>
              <CardActions
                onTest={() => testRedis.mutate()}
                testLoading={testRedis.isPending}
                saveLoading={saveRedis.isPending}
              />
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={8} style={colStyle}>
          <Card
            title="环境"
            size="small"
            style={cardStyle}
            styles={{ body: cardBody }}
            loading={cardLoading}
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
              <CardActions saveLoading={saveEnv.isPending} />
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
