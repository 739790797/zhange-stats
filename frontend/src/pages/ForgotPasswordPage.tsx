import { Alert, Button, Form, Input, Space, message } from "antd";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { resetPassword, sendResetPasswordCode } from "@/api/client";
import { apiError } from "@/lib/apiError";
import { AuthGuestShell } from "@/components/AuthGuestShell";
import { useAuthStore } from "@/stores/authStore";

export default function ForgotPasswordPage() {
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
      const res = await sendResetPasswordCode(email.email);
      message.success(res.message);
      setCountdown(60);
    } catch (e: unknown) {
      if (e && typeof e === "object" && "errorFields" in e) return;
      setError(apiError(e, "发送验证码失败"));
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
      const res = await resetPassword({
        email: values.email,
        code: values.code,
        new_password: values.password,
      });
      message.success(res.message || "密码已重置，请登录");
      navigate("/login", { replace: true });
    } catch (e: unknown) {
      setError(apiError(e, "重置密码失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthGuestShell
      title="找回密码"
      subtitle="通过已验证邮箱接收验证码并设置新密码"
    >
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
              placeholder="账号绑定的邮箱"
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
            label="新密码"
            rules={[
              { required: true, message: "请输入新密码" },
              { min: 8, message: "至少 8 位" },
            ]}
          >
            <Input.Password size="large" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认新密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入新密码" },
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
          >
            重置密码
          </Button>
          <div style={{ marginTop: 16, textAlign: "center" }}>
            <Link to="/login">返回登录</Link>
          </div>
        </Form>
    </AuthGuestShell>
  );
}
