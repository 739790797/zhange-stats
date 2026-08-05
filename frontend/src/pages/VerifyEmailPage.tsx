import { Alert, Button, Card, Form, Input, Typography, message } from "antd";
import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { resendCode, verifyEmail } from "@/api/client";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

export default function VerifyEmailPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = useAuthStore((s) => s.token);
  const initialEmail = useMemo(
    () => params.get("email") || "",
    [params],
  );
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  if (token) {
    return <Navigate to="/" replace />;
  }

  const onFinish = async (values: { email: string; code: string }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await verifyEmail(values.email, values.code);
      message.success(res.message);
      navigate("/login", { replace: true });
    } catch (e: unknown) {
      setError(apiError(e, "验证失败"));
    } finally {
      setLoading(false);
    }
  };

  const onResend = async (email: string) => {
    if (!email) {
      setError("请先填写邮箱");
      return;
    }
    setResending(true);
    setError(null);
    try {
      const res = await resendCode(email);
      setHint(res.message);
      message.success(res.message);
    } catch (e: unknown) {
      setError(apiError(e, "发送失败"));
    } finally {
      setResending(false);
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
            验证邮箱
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
            输入邮箱收到的 6 位验证码
          </Typography.Paragraph>
        </div>

        {error ? (
          <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />
        ) : null}
        {hint ? (
          <Alert type="info" message={hint} showIcon style={{ marginBottom: 16 }} />
        ) : null}

        <Form
          layout="vertical"
          onFinish={onFinish}
          requiredMark={false}
          initialValues={{ email: initialEmail }}
        >
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input size="large" />
          </Form.Item>
          <Form.Item
            name="code"
            label="验证码"
            rules={[{ required: true, message: "请输入验证码" }]}
          >
            <Input size="large" placeholder="6 位数字" maxLength={6} />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={loading}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
          >
            完成验证
          </Button>
          <Form.Item shouldUpdate noStyle>
            {({ getFieldValue }) => (
              <Button
                size="large"
                block
                style={{ marginTop: 12 }}
                loading={resending}
                onClick={() => onResend(getFieldValue("email"))}
              >
                重新发送验证码
              </Button>
            )}
          </Form.Item>
          <div style={{ marginTop: 16, textAlign: "center" }}>
            <Link to="/login">返回登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
}
