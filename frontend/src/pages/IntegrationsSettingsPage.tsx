import { GithubOutlined, QqOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Col,
  ConfigProvider,
  Divider,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import { useEffect, type ReactNode } from "react";
import {
  fetchIntegrationsSettings,
  testPelicanConnection,
  testMinecraftRconConnection,
  updateIntegrationsSettings,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { PlatformIcon } from "@/components/PlatformIcon";
import { apiError } from "@/lib/apiError";

type FormValues = {
  steam_api_key?: string;
  qq_app_id?: string;
  qq_app_key?: string;
  github_token?: string;
  pelican_base_url?: string;
  pelican_client_token?: string;
  pelican_application_token?: string;
  pelican_server_uuid?: string;
  minecraft_rcon_host?: string;
  minecraft_rcon_port?: number;
  minecraft_rcon_password?: string;
  minecraft_public_host?: string;
  minecraft_public_port?: number;
};

function IntegrationMark({ children }: { children: ReactNode }) {
  const { token } = theme.useToken();
  return (
    <span
      style={{
        width: 40,
        height: 40,
        borderRadius: 10,
        background: token.colorFillSecondary,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        color: token.colorText,
        fontSize: 20,
      }}
    >
      {children}
    </span>
  );
}

function IntegrationBlock({
  icon,
  title,
  configured,
  status,
  children,
  divider = true,
}: {
  icon: ReactNode;
  title: string;
  configured?: boolean;
  status?: ReactNode;
  children: ReactNode;
  divider?: boolean;
}) {
  return (
    <>
      <Row gutter={[32, 16]} style={{ padding: "8px 0 12px" }}>
        <Col xs={24} md={8} xl={7}>
          <Space align="start" size={12} style={{ width: "100%" }}>
            {icon}
            <div style={{ minWidth: 0 }}>
              <Typography.Text strong style={{ fontSize: 15 }}>
                {title}
              </Typography.Text>
              {status ? (
                <div style={{ marginTop: 4 }}>{status}</div>
              ) : configured == null ? null : (
                <div style={{ marginTop: 4 }}>
                  <Tag color={configured ? "success" : "default"}>
                    {configured ? "已配置" : "未配置"}
                  </Tag>
                </div>
              )}
            </div>
          </Space>
        </Col>
        <Col xs={24} md={16} xl={17}>
          {children}
        </Col>
      </Row>
      {divider ? <Divider style={{ margin: "20px 0 28px" }} /> : null}
    </>
  );
}

export default function IntegrationsSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();

  const { data, isLoading } = useQuery({
    queryKey: ["integrations-settings"],
    queryFn: fetchIntegrationsSettings,
  });

  useEffect(() => {
    if (!data) return;
    form.setFieldsValue({
      steam_api_key: data.steam_api_key || "",
      qq_app_id: data.qq_app_id || "",
      qq_app_key: data.qq_app_key || "",
      github_token: data.github_token || "",
      pelican_base_url: data.pelican_base_url || "",
      pelican_client_token: data.pelican_client_token || "",
      pelican_application_token: data.pelican_application_token || "",
      pelican_server_uuid: data.pelican_server_uuid || "",
      minecraft_rcon_host: data.minecraft_rcon_host || "",
      minecraft_rcon_port: data.minecraft_rcon_port || 25575,
      minecraft_rcon_password: data.minecraft_rcon_password || "",
      minecraft_public_host: data.minecraft_public_host || "",
      minecraft_public_port: data.minecraft_public_port || 25565,
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: updateIntegrationsSettings,
    onSuccess: () => {
      message.success("集成密钥已保存");
      queryClient.invalidateQueries({ queryKey: ["integrations-settings"] });
      queryClient.invalidateQueries({ queryKey: ["integrations-status"] });
      queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
      queryClient.invalidateQueries({ queryKey: ["minecraft-perf"] });
      queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const testPelican = useMutation({
    mutationFn: async () => {
      const values = form.getFieldsValue();
      return testPelicanConnection({
        base_url: (values.pelican_base_url || "").trim(),
        token: (values.pelican_client_token || "").trim() || null,
        server_uuid: (values.pelican_server_uuid || "").trim(),
      });
    },
    onSuccess: (res) => {
      if (res.ok) {
        const extra = [res.server_name, res.power_state]
          .filter(Boolean)
          .join(" · ");
        message.success(extra ? `${res.message}（${extra}）` : res.message);
      } else message.warning(res.message);
    },
    onError: (e: unknown) => message.error(apiError(e, "测试失败")),
  });

  const testRcon = useMutation({
    mutationFn: async () => {
      const values = form.getFieldsValue();
      return testMinecraftRconConnection({
        host: (values.minecraft_rcon_host || "").trim(),
        port: values.minecraft_rcon_port || 0,
        password: (values.minecraft_rcon_password || "").trim() || null,
      });
    },
    onSuccess: (res) => {
      if (res.ok) message.success(res.message);
      else message.warning(res.message);
    },
    onError: (e: unknown) => message.error(apiError(e, "测试失败")),
  });

  const saveButton = (
    <Button type="primary" htmlType="submit" loading={save.isPending}>
      保存
    </Button>
  );

  return (
    <ConfigProvider theme={{ components: { Form: { itemMarginBottom: 36 } } }}>
      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 960, margin: "0 auto" }}
        disabled={isLoading}
        onFinish={(values) => {
        const steam = values.steam_api_key?.trim() || "";
        const qqKey = values.qq_app_key?.trim() || "";
        const githubToken = values.github_token?.trim() || "";
        const pelicanToken = values.pelican_client_token?.trim() || "";
        const pelicanAppToken = values.pelican_application_token?.trim() || "";
        const rconPassword = values.minecraft_rcon_password?.trim() || "";
        save.mutate({
          steam_api_key: steam || null,
          qq_app_id: values.qq_app_id ?? "",
          qq_app_key: qqKey || null,
          clear_steam_api_key: !steam,
          clear_qq_app_key: !qqKey,
          github_token: githubToken || null,
          clear_github_token: !githubToken,
          pelican_base_url: values.pelican_base_url ?? "",
          pelican_client_token: pelicanToken || null,
          pelican_application_token: pelicanAppToken || null,
          pelican_server_uuid: values.pelican_server_uuid ?? "",
          clear_pelican_client_token: !pelicanToken,
          clear_pelican_application_token: !pelicanAppToken,
          minecraft_rcon_host: values.minecraft_rcon_host ?? "",
          minecraft_rcon_port: values.minecraft_rcon_port || 25575,
          minecraft_rcon_password: rconPassword || null,
          clear_minecraft_rcon_password: !rconPassword,
          minecraft_public_host: values.minecraft_public_host ?? "",
          minecraft_public_port: values.minecraft_public_port || 25565,
        });
      }}
    >
      <PageHeader
        title="集成密钥"
        subtitle="第三方密钥与连接配置"
        extra={saveButton}
      />
      <IntegrationBlock
        icon={
          <IntegrationMark>
            <PlatformIcon name="steam" size={22} />
          </IntegrationMark>
        }
        title="Steam"
        configured={data?.steam_configured}
      >
        <Form.Item
          name="steam_api_key"
          label="Web API Key"
          extra={
            <Typography.Link
              href="https://steamcommunity.com/dev/apikey"
              target="_blank"
              rel="noreferrer"
            >
              前往 Steam 申请 / 查看
            </Typography.Link>
          }
          style={{ marginBottom: 0 }}
        >
          <Input.Password
            placeholder="请输入 Steam Web API Key"
            autoComplete="new-password"
          />
        </Form.Item>
      </IntegrationBlock>

      <IntegrationBlock
        icon={
          <IntegrationMark>
            <QqOutlined />
          </IntegrationMark>
        }
        title="QQ 互联"
        configured={data?.qq_configured}
      >
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="qq_app_id"
              label="App ID"
              style={{ marginBottom: 0 }}
            >
              <Input placeholder="应用 ID" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="qq_app_key"
              label="App Key"
              style={{ marginBottom: 0 }}
            >
              <Input.Password
                placeholder="请输入 QQ App Key"
                autoComplete="new-password"
              />
            </Form.Item>
          </Col>
        </Row>
      </IntegrationBlock>

      <IntegrationBlock
        icon={
          <IntegrationMark>
            <PlatformIcon name="minecraft" size={22} />
          </IntegrationMark>
        }
        title="Minecraft"
        status={
          <Space size={8} wrap>
            <Tag color={data?.pelican_configured ? "success" : "default"}>
              {data?.pelican_configured ? "面板已配置" : "面板未配置"}
            </Tag>
            <Tag
              color={data?.minecraft_public_configured ? "success" : "default"}
            >
              {data?.minecraft_public_configured
                ? "公开地址已配置"
                : "公开地址未配置"}
            </Tag>
            <Tag
              color={data?.minecraft_rcon_configured ? "success" : "default"}
            >
              {data?.minecraft_rcon_configured ? "RCON 已配置" : "RCON 未配置"}
            </Tag>
          </Space>
        }
      >
        <Form.Item name="pelican_base_url" label="Panel 地址">
          <Input placeholder="https://panel.example.com" />
        </Form.Item>
        <Form.Item name="pelican_client_token" label="Client API Token">
          <Input.Password
            placeholder="账号设置里创建的 Client API key"
            autoComplete="new-password"
          />
        </Form.Item>
        <Form.Item label="Server UUID">
          <Space.Compact style={{ width: "100%" }}>
            <Form.Item name="pelican_server_uuid" noStyle>
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Form.Item>
            <Button
              htmlType="button"
              loading={testPelican.isPending}
              onClick={() => testPelican.mutate()}
            >
              测试面板
            </Button>
          </Space.Compact>
        </Form.Item>
        <Form.Item name="pelican_application_token" label="Application API Token">
          <Input.Password
            placeholder="管理后台 Application API key"
            autoComplete="new-password"
          />
        </Form.Item>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.Item name="minecraft_public_host" label="公开地址">
              <Input placeholder="mc.example.com" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="minecraft_public_port" label="端口">
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={8}>
            <Form.Item
              name="minecraft_rcon_host"
              label="RCON 地址"
              style={{ marginBottom: 0 }}
            >
              <Input placeholder="127.0.0.1" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={4}>
            <Form.Item
              name="minecraft_rcon_port"
              label="端口"
              style={{ marginBottom: 0 }}
            >
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item label="密码" style={{ marginBottom: 0 }}>
              <Space.Compact style={{ width: "100%" }}>
                <Form.Item name="minecraft_rcon_password" noStyle>
                  <Input.Password
                    placeholder="rcon.password"
                    autoComplete="new-password"
                  />
                </Form.Item>
                <Button
                  htmlType="button"
                  loading={testRcon.isPending}
                  onClick={() => testRcon.mutate()}
                >
                  测试 RCON
                </Button>
              </Space.Compact>
            </Form.Item>
          </Col>
        </Row>
      </IntegrationBlock>

      <IntegrationBlock
        icon={
          <IntegrationMark>
            <GithubOutlined />
          </IntegrationMark>
        }
        title="GitHub"
        configured={data?.github_configured}
        divider={false}
      >
        <Form.Item
          name="github_token"
          label="Personal Access Token"
          style={{ marginBottom: 0 }}
        >
          <Input.Password
            placeholder="github_pat_… 或 ghp_…"
            autoComplete="new-password"
          />
        </Form.Item>
      </IntegrationBlock>
    </Form>
    </ConfigProvider>
  );
}
