import {
  GithubOutlined,
  QqOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Col,
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
  testNapCatConnection,
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
  napcat_base_url?: string;
  napcat_token?: string;
  github_token?: string;
  pelican_base_url?: string;
  pelican_client_token?: string;
  pelican_server_uuid?: string;
  minecraft_rcon_host?: string;
  minecraft_rcon_port?: number;
  minecraft_rcon_password?: string;
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
  description,
  configured,
  extra,
  children,
  divider = true,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  configured?: boolean;
  extra?: ReactNode;
  children: ReactNode;
  divider?: boolean;
}) {
  return (
    <>
      <Row gutter={[32, 16]} style={{ padding: "4px 0 8px" }}>
        <Col xs={24} md={8} xl={7}>
          <Space align="start" size={12} style={{ width: "100%" }}>
            {icon}
            <div style={{ minWidth: 0 }}>
              <Space size={8} wrap>
                <Typography.Text strong style={{ fontSize: 15 }}>
                  {title}
                </Typography.Text>
                {configured == null ? null : (
                  <Tag color={configured ? "success" : "default"}>
                    {configured ? "已配置" : "未配置"}
                  </Tag>
                )}
              </Space>
              <Typography.Paragraph
                type="secondary"
                style={{ margin: "4px 0 0", fontSize: 13 }}
              >
                {description}
              </Typography.Paragraph>
              {extra ? <div style={{ marginTop: 8 }}>{extra}</div> : null}
            </div>
          </Space>
        </Col>
        <Col xs={24} md={16} xl={17}>
          {children}
        </Col>
      </Row>
      {divider ? <Divider style={{ margin: "12px 0 20px" }} /> : null}
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
      napcat_base_url: data.napcat_base_url || "",
      napcat_token: data.napcat_token || "",
      github_token: data.github_token || "",
      pelican_base_url: data.pelican_base_url || "",
      pelican_client_token: data.pelican_client_token || "",
      pelican_server_uuid: data.pelican_server_uuid || "",
      minecraft_rcon_host: data.minecraft_rcon_host || "",
      minecraft_rcon_port: data.minecraft_rcon_port || 25575,
      minecraft_rcon_password: data.minecraft_rcon_password || "",
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: updateIntegrationsSettings,
    onSuccess: () => {
      message.success("集成密钥已保存");
      queryClient.invalidateQueries({ queryKey: ["integrations-settings"] });
      queryClient.invalidateQueries({ queryKey: ["integrations-status"] });
      queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["napcat-groups"] });
      queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
      queryClient.invalidateQueries({ queryKey: ["minecraft-perf"] });
      queryClient.invalidateQueries({ queryKey: ["minecraft-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const testNapcat = useMutation({
    mutationFn: async () => {
      const values = form.getFieldsValue();
      const base_url = (values.napcat_base_url || "").trim();
      const token = (values.napcat_token || "").trim();
      return testNapCatConnection({
        base_url,
        token: token || null,
      });
    },
    onSuccess: (res) => {
      if (res.ok) message.success(res.message);
      else message.warning(res.message);
    },
    onError: (e: unknown) => message.error(apiError(e, "测试失败")),
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

  const callbackUrl = data?.qq_callback_url || "";
  const saveButton = (
    <Button
      type="primary"
      htmlType="submit"
      loading={save.isPending}
      style={{ background: "#1a2332", borderColor: "#1a2332" }}
    >
      保存
    </Button>
  );

  return (
    <Form
      form={form}
      layout="vertical"
      style={{ maxWidth: 960 }}
      disabled={isLoading}
      onFinish={(values) => {
        const steam = values.steam_api_key?.trim() || "";
        const qqKey = values.qq_app_key?.trim() || "";
        const napcatToken = values.napcat_token?.trim() || "";
        const githubToken = values.github_token?.trim() || "";
        const pelicanToken = values.pelican_client_token?.trim() || "";
        const rconPassword = values.minecraft_rcon_password?.trim() || "";
        save.mutate({
          steam_api_key: steam || null,
          qq_app_id: values.qq_app_id ?? "",
          qq_app_key: qqKey || null,
          clear_steam_api_key: !steam,
          clear_qq_app_key: !qqKey,
          napcat_base_url: values.napcat_base_url ?? "",
          napcat_token: napcatToken || null,
          clear_napcat_token: !napcatToken,
          github_token: githubToken || null,
          clear_github_token: !githubToken,
          pelican_base_url: values.pelican_base_url ?? "",
          pelican_client_token: pelicanToken || null,
          pelican_server_uuid: values.pelican_server_uuid ?? "",
          clear_pelican_client_token: !pelicanToken,
          minecraft_rcon_host: values.minecraft_rcon_host ?? "",
          minecraft_rcon_port: values.minecraft_rcon_port || 25575,
          minecraft_rcon_password: rconPassword || null,
          clear_minecraft_rcon_password: !rconPassword,
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
        description="游玩日历与 Steam 绑定所需的 Web API Key。"
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
        description="用于登录与账号绑定。回调地址填到 QQ 开放平台。"
        configured={data?.qq_configured}
      >
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item name="qq_app_id" label="App ID">
              <Input placeholder="应用 ID" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="qq_app_key" label="App Key">
              <Input.Password
                placeholder="请输入 QQ App Key"
                autoComplete="new-password"
              />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item label="回调地址" style={{ marginBottom: 0 }}>
          <Space.Compact style={{ width: "100%" }}>
            <Input value={callbackUrl} readOnly />
            <Button
              htmlType="button"
              disabled={!callbackUrl}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(callbackUrl);
                  message.success("已复制回调地址");
                } catch {
                  message.error("复制失败，请手动选择复制");
                }
              }}
            >
              复制
            </Button>
          </Space.Compact>
        </Form.Item>
      </IntegrationBlock>

      <IntegrationBlock
        icon={
          <IntegrationMark>
            <RobotOutlined />
          </IntegrationMark>
        }
        title="NapCat"
        description="OneBot HTTP 服务，用于 QQ 群成员同步。"
        configured={data?.napcat_configured}
        extra={
          <Button
            size="small"
            htmlType="button"
            loading={testNapcat.isPending}
            onClick={() => testNapcat.mutate()}
          >
            测试连接
          </Button>
        }
      >
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="napcat_base_url"
              label="Base URL"
              extra="填 OneBot HTTP 服务地址，不要填 /webui 管理页"
              style={{ marginBottom: 0 }}
            >
              <Input placeholder="http://127.0.0.1:3000" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="napcat_token"
              label="Token"
              style={{ marginBottom: 0 }}
            >
              <Input.Password
                placeholder="请输入 HTTP 服务 Token"
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
        title="Pelican"
        description="Minecraft 面板控制：与网页操作同一台服，不要填 Wings。"
        configured={data?.pelican_configured}
        extra={
          <Button
            size="small"
            htmlType="button"
            loading={testPelican.isPending}
            onClick={() => testPelican.mutate()}
          >
            测试连接
          </Button>
        }
      >
        <Form.Item
          name="pelican_base_url"
          label="Panel 地址"
          extra="填 Pelican 网页根地址"
        >
          <Input placeholder="https://panel.example.com" />
        </Form.Item>
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="pelican_client_token"
              label="Client API Token"
              extra="账号右上角 → API Credentials；权限含 console / files / power，不要用管理后台的 Application API Key"
              style={{ marginBottom: 0 }}
            >
              <Input.Password
                placeholder="账号设置里创建的 Client API key"
                autoComplete="new-password"
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              name="pelican_server_uuid"
              label="Server UUID"
              extra="短码或完整 UUID 均可"
              style={{ marginBottom: 0 }}
            >
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
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
        title="Minecraft RCON"
        description="总览 TPS / MSPT 与在线名单。服内自行开启 enable-rcon；填战鸽能连上的地址，不要对公网开放。"
        configured={data?.minecraft_rcon_configured}
        extra={
          <Button
            size="small"
            htmlType="button"
            loading={testRcon.isPending}
            onClick={() => testRcon.mutate()}
          >
            测试连接
          </Button>
        }
      >
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="minecraft_rcon_host"
              label="地址"
              extra="内网或 Pelican 映射后的主机名"
            >
              <Input placeholder="127.0.0.1" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={6}>
            <Form.Item
              name="minecraft_rcon_port"
              label="端口"
              extra="默认 25575"
            >
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={6}>
            <Form.Item name="minecraft_rcon_password" label="密码">
              <Input.Password
                placeholder="rcon.password"
                autoComplete="new-password"
              />
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
        description="提高 Releases API 限额，避免未认证 60 次/小时限流。"
        configured={data?.github_configured}
        divider={false}
      >
        <Form.Item
          name="github_token"
          label="Personal Access Token"
          extra="清空并保存将删除库内配置（仍可回落 .env 的 UPDATE_GITHUB_TOKEN）。"
          style={{ marginBottom: 0 }}
        >
          <Input.Password
            placeholder="github_pat_… 或 ghp_…"
            autoComplete="new-password"
          />
        </Form.Item>
      </IntegrationBlock>
    </Form>
  );
}
