import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Input, Space, message, theme } from "antd";
import { useEffect } from "react";
import {
  fetchIntegrationsSettings,
  testNapCatConnection,
  updateIntegrationsSettings,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";

type FormValues = {
  steam_api_key?: string;
  qq_app_id?: string;
  qq_app_key?: string;
  napcat_base_url?: string;
  napcat_token?: string;
};

export default function IntegrationsSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const { token } = theme.useToken();

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

  const callbackUrl = data?.qq_callback_url || "";

  const cardStyle = {
    marginBottom: 16,
    borderColor: token.colorBorderSecondary,
    background: token.colorFillAlter,
  } as const;

  return (
    <div>
      <PageHeader
        title="集成密钥"
        subtitle="第三方密钥与连接配置"
      />
      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 560 }}
        disabled={isLoading}
        onFinish={(values) => {
          const steam = values.steam_api_key?.trim() || "";
          const qqKey = values.qq_app_key?.trim() || "";
          const napcatToken = values.napcat_token?.trim() || "";
          save.mutate({
            steam_api_key: steam || null,
            qq_app_id: values.qq_app_id ?? "",
            qq_app_key: qqKey || null,
            clear_steam_api_key: !steam,
            clear_qq_app_key: !qqKey,
            napcat_base_url: values.napcat_base_url ?? "",
            napcat_token: napcatToken || null,
            clear_napcat_token: !napcatToken,
          });
        }}
      >
        <Card title="Steam" size="small" style={cardStyle}>
          <Form.Item
            name="steam_api_key"
            label={
              <span>
                Steam Web API Key{" "}
                <a
                  href="https://steamcommunity.com/dev/apikey"
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: token.colorLink }}
                >
                  （点击前往申请/查看）
                </a>
              </span>
            }
            style={{ marginBottom: 0 }}
          >
            <Input.Password
              placeholder="请输入 Steam Web API Key"
              autoComplete="new-password"
              size="large"
            />
          </Form.Item>
        </Card>

        <Card title="QQ 互联" size="small" style={cardStyle}>
          <Form.Item name="qq_app_id" label="QQ App ID">
            <Input placeholder="应用 ID" size="large" />
          </Form.Item>
          <Form.Item name="qq_app_key" label="QQ App Key">
            <Input.Password
              placeholder="请输入 QQ App Key"
              autoComplete="new-password"
              size="large"
            />
          </Form.Item>
          <Form.Item label="QQ 回调地址" style={{ marginBottom: 0 }}>
            <Space.Compact style={{ width: "100%" }}>
              <Input value={callbackUrl} readOnly size="large" />
              <Button
                size="large"
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
        </Card>

        <Card
          title="NapCat"
          size="small"
          style={cardStyle}
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
          <Form.Item
            name="napcat_base_url"
            label="Base URL"
            extra="填 OneBot HTTP 服务地址（网络配置里的 HTTP），不要填 /webui 管理页"
          >
            <Input placeholder="http://127.0.0.1:3000" size="large" />
          </Form.Item>
          <Form.Item
            name="napcat_token"
            label="Token"
            style={{ marginBottom: 0 }}
          >
            <Input.Password
              placeholder="请输入 HTTP 服务 Token"
              autoComplete="new-password"
              size="large"
            />
          </Form.Item>
        </Card>

        <Button
          type="primary"
          htmlType="submit"
          size="large"
          loading={save.isPending}
          style={{ background: "#1a2332", borderColor: "#1a2332" }}
        >
          保存
        </Button>
      </Form>
    </div>
  );
}
