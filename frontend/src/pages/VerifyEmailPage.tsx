import { Alert, Button, Form, Input, message } from "antd";
import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { resendCode, verifyEmail } from "@/api/client";
import { apiError } from "@/lib/apiError";
import { AuthGuestShell } from "@/components/AuthGuestShell";
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
    <AuthGuestShell
      title="验证邮箱"
      subtitle="输入邮箱收到的 6 位验证码"
      showVersion={false}
    >
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
    </AuthGuestShell>
  );
}
