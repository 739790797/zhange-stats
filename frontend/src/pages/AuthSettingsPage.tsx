import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  InputNumber,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import { Link } from "react-router-dom";
import { useEffect } from "react";
import { fetchAuthSettings, updateAuthSettings } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";

type SessionForm = {
  access_token_expire_days: number;
};

type PolicyForm = {
  min_password_length: number;
  reject_mode: "follow" | "reject" | "warn";
  enforce_single_admin: boolean;
};

export default function AuthSettingsPage() {
  const queryClient = useQueryClient();
  const { token } = theme.useToken();
  const [sessionForm] = Form.useForm<SessionForm>();
  const [policyForm] = Form.useForm<PolicyForm>();

  const { data, isLoading } = useQuery({
    queryKey: ["auth-settings"],
    queryFn: () => fetchAuthSettings(),
  });

  const weakCheck = useQuery({
    queryKey: ["auth-settings", "weak"],
    queryFn: () => fetchAuthSettings({ check_weak: true }),
    enabled: Boolean(data),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!weakCheck.data) return;
    queryClient.setQueryData(["auth-settings"], weakCheck.data);
  }, [weakCheck.data, queryClient]);

  useEffect(() => {
    if (!data) return;
    sessionForm.setFieldsValue({
      access_token_expire_days: data.access_token_expire_days || 1,
    });
    let reject_mode: PolicyForm["reject_mode"] = "follow";
    if (data.reject_weak_admin_password === true) reject_mode = "reject";
    if (data.reject_weak_admin_password === false) reject_mode = "warn";
    policyForm.setFieldsValue({
      min_password_length: data.min_password_length || 8,
      reject_mode,
      enforce_single_admin: Boolean(data.enforce_single_admin),
    });
  }, [data, sessionForm, policyForm]);

  const saveSession = useMutation({
    mutationFn: updateAuthSettings,
    onSuccess: () => {
      message.success("登录有效期已保存（仅影响之后新登录的 token）");
      queryClient.invalidateQueries({ queryKey: ["auth-settings"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const savePolicy = useMutation({
    mutationFn: updateAuthSettings,
    onSuccess: () => {
      message.success("口令策略已保存");
      queryClient.invalidateQueries({ queryKey: ["auth-settings"] });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const checkWeak = useMutation({
    mutationFn: () => fetchAuthSettings({ check_weak: true }),
    onSuccess: (res) => {
      queryClient.setQueryData(["auth-settings"], res);
      queryClient.setQueryData(["auth-settings", "weak"], res);
      const n = (res.admins || []).filter((a) => a.weak_password).length;
      if (n > 0) message.warning(`发现 ${n} 个管理员弱口令`);
      else message.success("未发现常见弱口令");
    },
    onError: (e: unknown) => message.error(apiError(e, "检查失败")),
  });

  const cardStyle = {
    marginBottom: 16,
    borderColor: token.colorBorderSecondary,
    background: token.colorFillAlter,
  } as const;

  const weakAdmins = (data?.admins || []).filter((a) => a.weak_password);
  const weakChecked = Boolean(data?.weak_password_checked);
  const weakChecking =
    Boolean(data) && !weakChecked && (weakCheck.isFetching || weakCheck.isPending);

  return (
    <div>
      <PageHeader
        title="安全设置"
        subtitle="登录会话、口令策略与管理员安全状态。改密请到个人中心。"
      />

      {weakChecked && weakAdmins.length > 0 ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="存在管理员弱口令"
          description={`${weakAdmins
            .map((a) => a.display_name || a.username)
            .join("、")} 的密码过于简单，请尽快在个人中心修改。`}
        />
      ) : null}

      <Card title="登录会话" size="small" style={cardStyle}>
        <Form
          form={sessionForm}
          layout="vertical"
          disabled={isLoading}
          onFinish={(values) => {
            const days = Number(values.access_token_expire_days) || 30;
            saveSession.mutate({
              access_token_expire_minutes: Math.round(days * 24 * 60),
            });
          }}
        >
          <Form.Item
            name="access_token_expire_days"
            label="登录有效期（天）"
            extra="修改后仅对新登录生效；已发出的 token 仍按原过期时间。"
            rules={[
              { required: true, message: "请填写有效期" },
              { type: "number", min: 1, max: 365, message: "范围 1～365 天" },
            ]}
          >
            <InputNumber
              min={1}
              max={365}
              step={1}
              precision={0}
              style={{ width: "100%" }}
              size="large"
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            loading={saveSession.isPending}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            保存
          </Button>
          {data ? (
            <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              当前约 {data.access_token_expire_minutes} 分钟（
              {data.access_token_expire_days} 天）。
            </Typography.Paragraph>
          ) : null}
        </Form>
      </Card>

      <Card title="口令策略" size="small" style={cardStyle}>
        <Form
          form={policyForm}
          layout="vertical"
          disabled={isLoading}
          onFinish={(values) => {
            const reject =
              values.reject_mode === "follow"
                ? null
                : values.reject_mode === "reject";
            savePolicy.mutate({
              min_password_length: values.min_password_length,
              reject_weak_admin_password: reject,
              enforce_single_admin: values.enforce_single_admin,
            });
          }}
        >
          <Form.Item
            name="min_password_length"
            label="最短密码长度"
            rules={[
              { required: true, message: "请填写长度" },
              { type: "number", min: 6, max: 72, message: "范围 6～72" },
            ]}
          >
            <InputNumber min={6} max={72} style={{ width: "100%" }} size="large" />
          </Form.Item>
          <Form.Item
            name="reject_mode"
            label="管理员弱口令启动策略"
            extra={
              data
                ? `当前生效：${
                    data.reject_weak_admin_password_effective
                      ? "拒绝启动"
                      : "仅警告"
                  }（环境 ${data.app_env || "development"}）`
                : undefined
            }
          >
            <Select
              size="large"
              options={[
                {
                  value: "follow",
                  label: "跟随环境（生产拒绝 / 开发仅警告）",
                },
                { value: "reject", label: "强制拒绝启动" },
                { value: "warn", label: "仅警告，允许启动" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="enforce_single_admin"
            label="仅保留一名管理员"
            valuePropName="checked"
            extra="开启后保存时会将其他管理员降为普通用户；之后新提权也会自动降级其他人。"
          >
            <Switch />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            loading={savePolicy.isPending}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            保存策略
          </Button>
        </Form>
      </Card>

      <Card
        title="管理员"
        size="small"
        style={cardStyle}
        extra={
          <Space size={8}>
            <Button
              size="small"
              loading={checkWeak.isPending || weakChecking}
              onClick={() => checkWeak.mutate()}
            >
              重新检查弱口令
            </Button>
            <Link to="/settings/users">用户管理</Link>
          </Space>
        }
      >
        <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
          角色与账号在用户管理中维护；弱口令在后台异步检查。改密请到{" "}
          <Link to="/profile">个人中心</Link>。全新部署请通过安装向导创建首位管理员。
        </Typography.Paragraph>
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          {(data?.admins || []).map((admin) => (
            <div
              key={admin.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
              }}
            >
              <span>
                {admin.display_name || admin.username}
                {admin.email ? (
                  <Typography.Text type="secondary"> · {admin.email}</Typography.Text>
                ) : null}
              </span>
              {weakChecking ? (
                <Tag>检查中…</Tag>
              ) : !weakChecked ? (
                <Tag>未检查</Tag>
              ) : admin.weak_password ? (
                <Tag color="warning">弱口令</Tag>
              ) : (
                <Tag color="success">口令正常</Tag>
              )}
            </div>
          ))}
          {!data?.admins?.length ? (
            <Typography.Text type="secondary">暂无管理员</Typography.Text>
          ) : null}
        </Space>
      </Card>
    </div>
  );
}
