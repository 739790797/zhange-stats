import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  message,
  theme,
} from "antd";
import { Link } from "react-router-dom";
import { fetchAuthSettings, fetchSiteSettings, updateAuthSettings, updateSiteSettings } from "@/api/client";
import type { AuthSettings, AuthSettingsUpdate, SiteSettings } from "@/api/settingsApi";
import { PageHeader } from "@/components/PageHeader";
import { hydrateForm, useHydrateUntouchedForm } from "@/hooks/useFormHydration";
import { SITE_PUBLIC_QUERY_KEY } from "@/hooks/useSitePublic";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

type SessionForm = {
  access_token_expire_days: number;
};

type PolicyForm = {
  min_password_length: number;
  reject_mode: "follow" | "reject" | "warn";
  enforce_single_admin: boolean;
};

type SiteForm = {
  icp_beian_no: string;
};

const AUTH_SETTINGS_KEY = ["auth-settings"];
/** 弱口令探测要跑 bcrypt 字典，单独一个键；保存配置不应连带重跑。 */
const AUTH_WEAK_KEY = ["auth-settings", "weak"];

/** 与后端 MAX_ACCESS_TOKEN_MINUTES（30 天）一致。 */
const MAX_SESSION_DAYS = 30;

function clampSessionDays(value: unknown): number {
  const days = Number(value) || 1;
  return Math.min(MAX_SESSION_DAYS, Math.max(1, days));
}

function sessionValuesOf(data: AuthSettings): SessionForm {
  return { access_token_expire_days: clampSessionDays(data.access_token_expire_days) };
}

function policyValuesOf(data: AuthSettings): PolicyForm {
  let reject_mode: PolicyForm["reject_mode"] = "follow";
  if (data.reject_weak_admin_password === true) reject_mode = "reject";
  if (data.reject_weak_admin_password === false) reject_mode = "warn";
  return {
    min_password_length: data.min_password_length || 8,
    reject_mode,
    enforce_single_admin: Boolean(data.enforce_single_admin),
  };
}

function siteValuesOf(data: SiteSettings): SiteForm {
  return { icp_beian_no: data.icp_beian_no || "" };
}

export default function AuthSettingsPage() {
  const queryClient = useQueryClient();
  const { token } = theme.useToken();
  const me = useAuthStore((s) => s.user);
  const [sessionForm] = Form.useForm<SessionForm>();
  const [policyForm] = Form.useForm<PolicyForm>();
  const [siteForm] = Form.useForm<SiteForm>();

  const { data, isLoading } = useQuery({
    queryKey: AUTH_SETTINGS_KEY,
    queryFn: () => fetchAuthSettings(),
  });

  const siteQuery = useQuery({
    queryKey: ["site-settings"],
    queryFn: fetchSiteSettings,
  });

  const weakCheck = useQuery({
    queryKey: AUTH_WEAK_KEY,
    queryFn: () => fetchAuthSettings({ check_weak: true }),
    enabled: Boolean(data),
    staleTime: 60_000,
  });

  useHydrateUntouchedForm(sessionForm, data, sessionValuesOf);
  useHydrateUntouchedForm(policyForm, data, policyValuesOf);
  useHydrateUntouchedForm(siteForm, siteQuery.data, siteValuesOf);

  const saveSession = useMutation({
    mutationFn: (payload: AuthSettingsUpdate) => updateAuthSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(AUTH_SETTINGS_KEY, saved);
      hydrateForm(sessionForm, sessionValuesOf(saved));
      message.success("登录有效期已保存（仅影响之后新登录的 token）");
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const savePolicy = useMutation({
    mutationFn: (payload: AuthSettingsUpdate) => updateAuthSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(AUTH_SETTINGS_KEY, saved);
      hydrateForm(policyForm, policyValuesOf(saved));
      message.success("口令策略已保存");
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const saveSite = useMutation({
    mutationFn: updateSiteSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(["site-settings"], saved);
      hydrateForm(siteForm, siteValuesOf(saved));
      message.success("备案号已保存");
      void queryClient.invalidateQueries({ queryKey: SITE_PUBLIC_QUERY_KEY, exact: true });
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const recheckWeak = async () => {
    const res = await weakCheck.refetch();
    if (res.error) {
      message.error(apiError(res.error, "检查失败"));
      return;
    }
    const n = (res.data?.admins || []).filter((a) => a.weak_password).length;
    if (n > 0) message.warning(`发现 ${n} 个管理员弱口令`);
    else message.success("未发现常见弱口令");
  };

  const submitPolicy = async (values: PolicyForm) => {
    const reject =
      values.reject_mode === "follow" ? null : values.reject_mode === "reject";
    const payload: AuthSettingsUpdate = {
      min_password_length: values.min_password_length,
      reject_weak_admin_password: reject,
      enforce_single_admin: values.enforce_single_admin,
    };
    if (!values.enforce_single_admin) {
      savePolicy.mutate(payload);
      return;
    }
    let admins: AuthSettings["admins"];
    try {
      admins = (await fetchAuthSettings()).admins;
    } catch (e) {
      message.error(apiError(e, "读取管理员列表失败"));
      return;
    }
    const demoted = (admins || []).filter((a) => a.id !== me?.id);
    if (!demoted.length) {
      savePolicy.mutate(payload);
      return;
    }
    Modal.confirm({
      title: "只保留你一名管理员？",
      content: (
        <>
          <Typography.Paragraph style={{ marginBottom: 8 }}>
            保存后以下 {demoted.length} 名管理员会被降为普通用户；之后再给别人提权，也会自动降级其他管理员。
          </Typography.Paragraph>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {demoted.map((a) => (
              <li key={a.id}>
                {a.display_name || a.username}
                {a.email ? ` · ${a.email}` : ""}
              </li>
            ))}
          </ul>
        </>
      ),
      okText: "降级并保存",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: () => {
        savePolicy.mutate(payload);
      },
    });
  };

  const cardStyle = {
    marginBottom: 16,
    borderColor: token.colorBorderSecondary,
    background: token.colorFillAlter,
  } as const;

  const admins = data?.admins || [];
  const probe = weakCheck.data;
  const weakChecked = Boolean(probe?.weak_password_checked);
  const weakById = new Map((probe?.admins || []).map((a) => [a.id, a.weak_password]));
  const weakAdmins = weakChecked ? admins.filter((a) => weakById.get(a.id)) : [];
  const weakChecking = Boolean(data) && weakCheck.isFetching;

  return (
    <div>
      <PageHeader
        title="安全设置"
        subtitle="登录会话、口令策略、页脚备案号与管理员安全状态。改密请到个人中心。"
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
            const days = clampSessionDays(values.access_token_expire_days);
            saveSession.mutate({
              access_token_expire_minutes: Math.round(days * 24 * 60),
            });
          }}
        >
          <Form.Item
            name="access_token_expire_days"
            label="登录有效期（天）"
            extra={`最长 ${MAX_SESSION_DAYS} 天。修改后仅对新登录生效；已发出的 token 仍按原过期时间。`}
            rules={[
              { required: true, message: "请填写有效期" },
              {
                type: "number",
                min: 1,
                max: MAX_SESSION_DAYS,
                message: `范围 1～${MAX_SESSION_DAYS} 天`,
              },
            ]}
          >
            <InputNumber
              min={1}
              max={MAX_SESSION_DAYS}
              step={1}
              precision={0}
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={saveSession.isPending}
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
            void submitPolicy(values);
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
            <InputNumber min={6} max={72} style={{ width: "100%" }} />
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
            loading={savePolicy.isPending}
          >
            保存策略
          </Button>
        </Form>
      </Card>

      <Card title="ICP 备案" size="small" style={cardStyle}>
        <Form
          form={siteForm}
          layout="vertical"
          disabled={siteQuery.isLoading}
          onFinish={(values) => {
            saveSite.mutate({
              icp_beian_no: (values.icp_beian_no || "").trim(),
            });
          }}
        >
          <Form.Item
            name="icp_beian_no"
            label="备案号"
            extra="展示在全站页脚（登录页与工作台各页），点进工信部查询页。留空则不展示。自托管请填本站自己的号。"
            rules={[{ max: 64, message: "最多 64 字" }]}
          >
            <Input
              placeholder="例如 浙ICP备xxxxxxxx号"
              maxLength={64}
              allowClear
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={saveSite.isPending}
          >
            保存备案号
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
              loading={weakChecking}
              onClick={() => void recheckWeak()}
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
          {admins.map((admin) => (
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
              ) : !weakChecked || !weakById.has(admin.id) ? (
                <Tag>未检查</Tag>
              ) : weakById.get(admin.id) ? (
                <Tag color="warning">弱口令</Tag>
              ) : (
                <Tag color="success">口令正常</Tag>
              )}
            </div>
          ))}
          {!admins.length ? (
            <Typography.Text type="secondary">暂无管理员</Typography.Text>
          ) : null}
        </Space>
      </Card>
    </div>
  );
}
