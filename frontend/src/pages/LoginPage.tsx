import { Alert, Button, Card, Form, Input, Typography, message } from "antd";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { fetchMe, login } from "@/api/client";
import { AppVersion } from "@/components/AppVersion";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (token) {
    return <Navigate to="/" replace />;
  }

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    setError(null);
    try {
      const { access_token } = await login(values.username, values.password);
      useAuthStore.setState({ token: access_token });
      const user = await fetchMe();
      setAuth(access_token, user);
      message.success("登录成功");
      if (!user.steam_id) {
        navigate("/profile", {
          replace: true,
          state: { promptSteamBind: true },
        });
      } else {
        navigate("/", { replace: true });
      }
    } catch (e: unknown) {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string }; status?: number } })
          .response?.data?.detail;
      const status =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { status?: number } }).response?.status;
      if (status === 403) {
        setError(String(detail || "请先完成邮箱验证"));
      } else {
        setError(String(detail || "账号或密码错误"));
      }
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
          width: 420,
          maxWidth: "100%",
          boxShadow: "0 16px 48px rgba(0,0,0,0.35)",
          border: "1px solid rgba(232,184,109,0.25)",
        }}
        styles={{ body: { padding: "40px 36px" } }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Typography.Title
            level={1}
            style={{
              margin: 0,
              fontSize: 36,
              color: "#1a2332",
              letterSpacing: 2,
            }}
          >
            战鸽数据
          </Typography.Title>
          <Typography.Paragraph
            type="secondary"
            style={{ marginTop: 8, marginBottom: 0 }}
          >
            Zhange Stats · Steam 游玩统计
          </Typography.Paragraph>
        </div>

        {error ? (
          <Alert
            type="error"
            message={error}
            showIcon
            style={{ marginBottom: 16 }}
            action={
              error.includes("邮箱验证") ? (
                <Link to="/verify-email">去验证</Link>
              ) : undefined
            }
          />
        ) : null}

        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item
            name="username"
            label="邮箱"
            rules={[{ required: true, message: "请输入邮箱" }]}
          >
            <Input
              size="large"
              placeholder="邮箱"
              autoComplete="email"
            />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password
              size="large"
              placeholder="密码"
              autoComplete="current-password"
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={loading}
            style={{
              background: "#1a2332",
              borderColor: "#1a2332",
              marginTop: 8,
            }}
          >
            登录
          </Button>
          <Button
            size="large"
            block
            style={{ marginTop: 12 }}
            onClick={() => navigate("/register")}
          >
            注册账号
          </Button>
        </Form>
      </Card>
      <div style={{ position: "fixed", left: 0, right: 0, bottom: 8 }}>
        <AppVersion light />
      </div>
    </div>
  );
}
