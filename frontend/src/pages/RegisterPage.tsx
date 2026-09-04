import { Alert, Button, Checkbox, Form, Input, Space, message } from "antd";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { fetchMe, register, sendRegisterCode } from "@/api/client";
import { apiError } from "@/lib/apiError";
import { AuthGuestShell } from "@/components/AuthGuestShell";
import { LegalLinks } from "@/components/LegalLinks";
import { LEGAL_PRIVACY_PATH, LEGAL_TERMS_PATH } from "@/lib/legalDocs";
import { QqLoginButton } from "@/components/QqLoginButton";
import { useAuthStore } from "@/stores/authStore";

export default function RegisterPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const setAuth = useAuthStore((s) => s.setAuth);
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
      const res = await register({
        email: values.email,
        password: values.password,
        code: values.code,
      });
      if (!res.access_token) {
        message.success(res.message || "注册成功，请登录");
        navigate("/login", { replace: true });
        return;
      }
      useAuthStore.setState({ token: res.access_token });
      const user = await fetchMe();
      setAuth(res.access_token, user);
      message.success(res.message || "注册成功");
      navigate("/", { replace: true });
    } catch (e: unknown) {
      setError(apiError(e, "注册失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthGuestShell title="注册账号">
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
              { min: 8, message: "至少 8 位" },
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
          <Form.Item
            name="agree"
            valuePropName="checked"
            rules={[
              {
                validator: (_, value) =>
                  value
                    ? Promise.resolve()
                    : Promise.reject(
                        new Error("请先阅读并同意服务条款与隐私说明"),
                      ),
              },
            ]}
          >
            <Checkbox>
              我已阅读并同意{" "}
              <Link to={LEGAL_TERMS_PATH}>服务条款</Link>
              {" 与 "}
              <Link to={LEGAL_PRIVACY_PATH}>隐私说明</Link>
            </Checkbox>
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={loading}
          >
            注册
          </Button>
          <div style={{ marginTop: 16, textAlign: "center" }}>
            <Link to="/login">已有账号？去登录</Link>
          </div>
        </Form>

        <QqLoginButton dividerText="或使用 QQ 登录" />
        <LegalLinks prefix="QQ 登录即表示同意" />
    </AuthGuestShell>
  );
}
