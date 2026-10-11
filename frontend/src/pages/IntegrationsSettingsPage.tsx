import { GithubOutlined, QqOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Col,
  ConfigProvider,
  Divider,
  Form,
  Input,
  Row,
  Space,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import { useState, type ReactNode } from "react";
import {
  fetchIntegrationsSettings,
  updateIntegrationsSettings,
} from "@/api/client";
import type { IntegrationsSettings, IntegrationsUpdate } from "@/api/settingsApi";
import { PageHeader } from "@/components/PageHeader";
import { PlatformIcon } from "@/components/PlatformIcon";
import { SecretFormItem } from "@/components/SecretFormItem";
import { hydrateForm, useHydrateUntouchedForm } from "@/hooks/useFormHydration";
import { apiError } from "@/lib/apiError";
import { secretPayloadValue } from "@/lib/secretInput";

type FormValues = {
  steam_api_key?: string;
  qq_app_id?: string;
  qq_app_key?: string;
  github_token?: string;
  // Minecraft 页面已停用，面板 / RCON / 公开地址不再出现在表单里。
};

type SecretKey = "steam_api_key" | "qq_app_key" | "github_token";
type ClearFlags = Record<SecretKey, boolean>;

const NO_CLEAR: ClearFlags = {
  steam_api_key: false,
  qq_app_key: false,
  github_token: false,
};

function formValuesOf(data: IntegrationsSettings): FormValues {
  return {
    steam_api_key: "",
    qq_app_id: data.qq_app_id || "",
    qq_app_key: "",
    github_token: "",
  };
}

function toPayload(values: FormValues, clearing: ClearFlags): IntegrationsUpdate {
  return {
    steam_api_key: secretPayloadValue(values.steam_api_key, clearing.steam_api_key),
    qq_app_id: values.qq_app_id ?? "",
    qq_app_key: secretPayloadValue(values.qq_app_key, clearing.qq_app_key),
    github_token: secretPayloadValue(values.github_token, clearing.github_token),
    clear_steam_api_key: clearing.steam_api_key,
    clear_qq_app_key: clearing.qq_app_key,
    clear_github_token: clearing.github_token,
    // 不回写 Minecraft 面板 / RCON / 公开地址，避免保存其它密钥时清空已有值。
    clear_pelican_client_token: false,
    clear_pelican_application_token: false,
    clear_minecraft_rcon_password: false,
  };
}

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
  const [clearing, setClearing] = useState<ClearFlags>(NO_CLEAR);

  const { data, isLoading } = useQuery({
    queryKey: ["integrations-settings"],
    queryFn: fetchIntegrationsSettings,
  });

  useHydrateUntouchedForm(form, data, formValuesOf);

  const clearProps = (key: SecretKey) => ({
    clearing: clearing[key],
    onClearingChange: (next: boolean) => setClearing((prev) => ({ ...prev, [key]: next })),
  });

  const save = useMutation({
    mutationFn: (payload: IntegrationsUpdate) =>
      updateIntegrationsSettings(payload),
    onSuccess: (saved) => {
      message.success("集成密钥已保存");
      queryClient.setQueryData(["integrations-settings"], saved);
      hydrateForm(form, formValuesOf(saved));
      setClearing(NO_CLEAR);
      queryClient.invalidateQueries({ queryKey: ["integrations-status"] });
      queryClient.invalidateQueries({ queryKey: ["scheduled-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["app-update-status"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
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
        disabled={isLoading}
        onFinish={(values) => {
          save.mutate(toPayload(values, clearing));
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
        <SecretFormItem
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
          set={Boolean(data?.steam_api_key_set)}
          hint={data?.steam_api_key_hint}
          emptyPlaceholder="请输入 Steam Web API Key"
          {...clearProps("steam_api_key")}
        />
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
            <SecretFormItem
              name="qq_app_key"
              label="App Key"
              style={{ marginBottom: 0 }}
              set={Boolean(data?.qq_app_key_set)}
              hint={data?.qq_app_key_hint}
              emptyPlaceholder="请输入 QQ App Key"
              {...clearProps("qq_app_key")}
            />
          </Col>
        </Row>
      </IntegrationBlock>

      {/* Minecraft 页面已停用：面板、公开地址、RCON。
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
              color={data?.pelican_application_token_set ? "success" : "default"}
            >
              {data?.pelican_application_token_set
                ? "管理端已配置"
                : "管理端未配置"}
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
        <Form.Item name="pelican_application_token" label="管理端 API Token">
          <Input.Password
            placeholder="管理后台 Application API 里创建的 key"
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
      */}

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
        <SecretFormItem
          name="github_token"
          label="Personal Access Token"
          style={{ marginBottom: 0 }}
          set={Boolean(data?.github_token_set)}
          hint={data?.github_token_hint}
          emptyPlaceholder="github_pat_… 或 ghp_…"
          {...clearProps("github_token")}
        />
      </IntegrationBlock>
    </Form>
    </ConfigProvider>
  );
}
