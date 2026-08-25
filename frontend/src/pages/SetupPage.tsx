import { Alert, Button, Form, Input, message } from "antd";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { completeSetupAdmin, fetchMe, fetchSetupStatus } from "@/api/client";
import { AuthGuestShell } from "@/components/AuthGuestShell";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

type FormValues = {
  display_name: string;
  email: string;
  password: string;
  confirm: string;
};

export default function SetupPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minLen, setMinLen] = useState(8);
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await fetchSetupStatus();
        if (cancelled) return;
        setNeedsSetup(status.needs_setup);
        setMinLen(status.min_password_length || 8);
      } catch {
        if (!cancelled) setNeedsSetup(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (needsSetup === false) {
    return <Navigate to="/login" replace />;
  }

  const onFinish = async (values: FormValues) => {
    if (values.password !== values.confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await completeSetupAdmin({
        email: values.email,
        display_name: values.display_name,
        password: values.password,
      });
      useAuthStore.setState({ token: res.access_token });
      const user = await fetchMe();
      setAuth(res.access_token, user);
      message.success("初始化完成");
      navigate("/", { replace: true });
    } catch (e: unknown) {
      setError(apiError(e, "初始化失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthGuestShell
      width={440}
      brand
      brandTitleSize={32}
      headerMarginBottom={28}
      subtitle="首次安装 · 创建管理员账号"
    >
        {error ? (
          <Alert
            type="error"
            message={error}
            showIcon
            style={{ marginBottom: 16 }}
          />
        ) : null}

        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item
            name="display_name"
            label="显示名"
            rules={[{ required: true, message: "请输入显示名" }]}
          >
            <Input size="large" placeholder="例如：管理员" autoComplete="nickname" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input size="large" placeholder="用于登录" autoComplete="email" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: minLen, message: `至少 ${minLen} 位` },
            ]}
            extra={`至少 ${minLen} 位，勿使用常见弱口令`}
          >
            <Input.Password size="large" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            rules={[{ required: true, message: "请再次输入密码" }]}
          >
            <Input.Password size="large" autoComplete="new-password" />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={loading || needsSetup === null}
            style={{ marginTop: 8 }}
          >
            完成安装并进入
          </Button>
        </Form>
    </AuthGuestShell>
  );
}
