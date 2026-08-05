import { Alert, Button, Card, Form, Input, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { completeSetupAdmin, fetchMe, fetchSetupStatus } from "@/api/client";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";
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
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "radial-gradient(ellipse at top left, #2c3e50 0%, #1a2332 45%, #0f1419 100%)",
        padding: 24,
      }}
    >
      <Card
        style={{
          width: 440,
          maxWidth: "100%",
          boxShadow: "0 16px 48px rgba(0,0,0,0.35)",
          border: "1px solid rgba(232,184,109,0.25)",
        }}
        styles={{ body: { padding: "40px 36px" } }}
      >
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              marginBottom: 8,
            }}
          >
            <BrandLogo size={48} color="#1a2332" />
            <Typography.Title
              level={1}
              style={{
                margin: 0,
                fontSize: 32,
                color: "#1a2332",
                letterSpacing: 2,
              }}
            >
              战鸽数据
            </Typography.Title>
          </div>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            首次安装 · 创建管理员账号
          </Typography.Paragraph>
        </div>

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
            style={{
              background: "#1a2332",
              borderColor: "#1a2332",
              marginTop: 8,
            }}
          >
            完成安装并进入
          </Button>
        </Form>
      </Card>
      <div style={{ position: "fixed", left: 0, right: 0, bottom: 8 }}>
        <AppVersion light />
      </div>
    </div>
  );
}
