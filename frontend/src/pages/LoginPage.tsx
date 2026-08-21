import { Alert, Button, Card, Form, Input, Typography, message } from "antd";
import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { fetchMe, login, exchangeQqTicket } from "@/api/client";
import { apiError } from "@/lib/apiError";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";
import { QqLoginButton } from "@/components/QqLoginButton";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const token = useAuthStore((s) => s.token);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qqCompleting, setQqCompleting] = useState(false);
  const qqHandled = useRef(false);

  useEffect(() => {
    if (qqHandled.current) return;
    const status = searchParams.get("qq_login");
    if (!status) return;
    qqHandled.current = true;

    const ticket = searchParams.get("ticket");
    const name = searchParams.get("name");
    const detail = searchParams.get("detail");
    const needCompleteFlag = searchParams.get("need_complete") === "1";
    const next = new URLSearchParams(searchParams);
    next.delete("qq_login");
    next.delete("ticket");
    next.delete("access_token"); // 兼容旧回调
    next.delete("name");
    next.delete("detail");
    next.delete("need_complete");
    setSearchParams(next, { replace: true });

    if (status === "ok" && ticket) {
      setQqCompleting(true);
      void (async () => {
        try {
          const { access_token } = await exchangeQqTicket(ticket);
          useAuthStore.setState({ token: access_token });
          const user = await fetchMe();
          setAuth(access_token, user);
          message.success(name ? `欢迎，${name}` : "QQ 登录成功");
          const needComplete = needCompleteFlag || !user.email;
          navigate("/", {
            replace: true,
            state: needComplete ? { promptCompleteProfile: true } : undefined,
          });
        } catch {
          useAuthStore.getState().logout();
          setError("QQ 登录失败，请重试");
          setQqCompleting(false);
        }
      })();
      return;
    }

    setError(detail || "QQ 登录失败");
  }, [navigate, searchParams, setAuth, setSearchParams]);

  if (token && !qqCompleting && !searchParams.get("qq_login")) {
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
      navigate("/", {
        replace: true,
        state: !user.email ? { promptCompleteProfile: true } : undefined,
      });
    } catch (e: unknown) {
      setError(apiError(e, "账号或密码错误"));
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
                fontSize: 36,
                color: "#1a2332",
                letterSpacing: 2,
              }}
            >
              战鸽数据
            </Typography.Title>
          </div>
          <Typography.Paragraph
            type="secondary"
            style={{ marginTop: 8, marginBottom: 0 }}
          >
            Zhange Stats
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
          <div style={{ marginTop: -8, marginBottom: 8, textAlign: "right" }}>
            <Link to="/forgot-password">忘记密码？</Link>
          </div>
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

        <QqLoginButton />
      </Card>
      <div style={{ position: "fixed", left: 0, right: 0, bottom: 8 }}>
        <AppVersion light />
      </div>
    </div>
  );
}
