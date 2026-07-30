import { Alert, Button, Card, Form, Input, Space, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { register, sendRegisterCode } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

export default function RegisterPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = window.setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [countdown]);

  if (token) {
    return <Navigate to="/" replace />;
  }

  const onSendCode = async () => {
    setError(null);
    try {
      const email = await form.validateFields(["email"]);
      setSending(true);
      const res = await sendRegisterCode(email.email);
      message.success(res.message);
      setCountdown(60);
    } catch (e: unknown) {
      if (e && typeof e === "object" && "errorFields" in e) return;
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      setError(String(detail || "发送验证码失败"));
    } finally {
      setSending(false);
    }
  };

  const onFinish = async (values: {
    email: string;
    code: string;
    password: string;
    confirm: string;
  }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await register({
        email: values.email,
        password: values.password,
        code: values.code,
      });
      message.success(res.message);
      navigate("/login", { replace: true });
    } catch (e: unknown) {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      setError(String(detail || "注册失败"));
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
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Typography.Title level={2} style={{ margin: 0, color: "#1a2332" }}>
            注册账号
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
            邮箱注册；用户名自动生成，可稍后在个人设置修改
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

        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          requiredMark={false}
        >
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input
              size="large"
              placeholder="用于登录的邮箱"
              autoComplete="email"
            />
          </Form.Item>

          <Form.Item label="验证码" required>
            <Space.Compact style={{ width: "100%" }}>
              <Form.Item
                name="code"
                noStyle
                rules={[{ required: true, message: "请输入验证码" }]}
              >
                <Input
                  size="large"
                  placeholder="6 位验证码"
                  maxLength={6}
                  style={{ width: "100%" }}
                />
              </Form.Item>
              <Button
                size="large"
                loading={sending}
                disabled={countdown > 0}
                onClick={onSendCode}
              >
                {countdown > 0 ? `${countdown}s` : "发送验证码"}
              </Button>
            </Space.Compact>
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 6, message: "至少 6 位" },
            ]}
          >
            <Input.Password size="large" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error("两次密码不一致"));
                },
              }),
            ]}
          >
            <Input.Password size="large" autoComplete="new-password" />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={loading}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            注册
          </Button>
          <div style={{ marginTop: 16, textAlign: "center" }}>
            <Link to="/login">已有账号？去登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
