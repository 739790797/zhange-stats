import { Alert, Button, Form, Input, message } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { fetchMe, login, exchangeQqTicket } from "@/api/client";
import { apiError } from "@/lib/apiError";
import { AuthGuestShell } from "@/components/AuthGuestShell";
import { LegalLinks } from "@/components/LegalLinks";
import { QqLoginButton } from "@/components/QqLoginButton";
import {
  consumePostLoginPath,
  postLoginPath,
  rememberPostLoginPath,
  type LoginFromLocation,
} from "@/lib/postLoginPath";
import { useAuthStore } from "@/stores/authStore";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const token = useAuthStore((s) => s.token);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qqCompleting, setQqCompleting] = useState(false);
  const qqHandled = useRef(false);
  const from = (location.state as { from?: LoginFromLocation } | null)?.from;

  useEffect(() => {
    const path = postLoginPath(from);
    if (path !== "/") rememberPostLoginPath(path);
  }, [from]);

  const goHome = useCallback(
    (extraState?: { promptCompleteProfile?: boolean }) => {
      const path = consumePostLoginPath() || postLoginPath(from);
      navigate(path, { replace: true, state: extraState });
    },
    [from, navigate],
  );

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
          goHome(needComplete ? { promptCompleteProfile: true } : undefined);
        } catch (e: unknown) {
          useAuthStore.getState().logout();
          setError(apiError(e, "QQ 登录失败，请重试"));
          setQqCompleting(false);
        }
      })();
      return;
    }

    setError(detail || "QQ 登录失败");
  }, [goHome, navigate, searchParams, setAuth, setSearchParams]);

  const loggedInDest = useRef<string | null>(null);
  if (token && !qqCompleting && !searchParams.get("qq_login")) {
    if (loggedInDest.current == null) {
      loggedInDest.current = consumePostLoginPath() || postLoginPath(from);
    }
    return <Navigate to={loggedInDest.current} replace />;
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
      goHome(!user.email ? { promptCompleteProfile: true } : undefined);
    } catch (e: unknown) {
      setError(apiError(e, "账号或密码错误"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthGuestShell brand subtitle="圈子成员站">
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
            style={{ marginTop: 8 }}
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
        <LegalLinks prefix="登录即表示同意" />
    </AuthGuestShell>
  );
}
