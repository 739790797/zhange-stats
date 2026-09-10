import { Alert, Button, Form, Input, Radio, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  completeSetupAdmin,
  completeSetupDatabase,
  fetchMe,
  fetchSetupStatus,
} from "@/api/client";
import { AuthGuestShell } from "@/components/AuthGuestShell";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

type AdminFormValues = {
  display_name: string;
  email: string;
  password: string;
  confirm: string;
};

type DbFormValues = {
  engine: "sqlite" | "mysql";
  url?: string;
};

export default function SetupPage() {
  const navigate = useNavigate();
  const setUser = useAuthStore((s) => s.setUser);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minLen, setMinLen] = useState(8);
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [needsDatabase, setNeedsDatabase] = useState(true);
  const [sqlitePath, setSqlitePath] = useState("var/data/zhange.sqlite");

  const refreshStatus = async () => {
    const status = await fetchSetupStatus();
    setNeedsSetup(status.needs_setup);
    setNeedsDatabase(Boolean(status.needs_database));
    setMinLen(status.min_password_length || 8);
    if (status.sqlite_path) setSqlitePath(status.sqlite_path);
    return status;
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await refreshStatus();
        if (cancelled) return;
        setNeedsSetup(status.needs_setup);
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

  const onDatabase = async (values: DbFormValues) => {
    setLoading(true);
    setError(null);
    try {
      const res = await completeSetupDatabase({
        engine: values.engine,
        url: values.engine === "mysql" ? values.url : undefined,
      });
      message.success(res.message);
      await refreshStatus();
    } catch (e: unknown) {
      setError(apiError(e, "配置数据库失败"));
    } finally {
      setLoading(false);
    }
  };

  const onAdmin = async (values: AdminFormValues) => {
    if (values.password !== values.confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await completeSetupAdmin({
        email: values.email,
        display_name: values.display_name,
        password: values.password,
      });
      const user = await fetchMe();
      setUser(user);
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
      width={480}
      brand
      brandTitleSize={32}
      headerMarginBottom={28}
      title="安装"
      subtitle={
        needsDatabase
          ? "首次安装 · 选择数据库"
          : "首次安装 · 创建管理员账号"
      }
    >
      {error ? (
        <Alert
          type="error"
          message={error}
          showIcon
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {needsDatabase ? (
        <Form
          layout="vertical"
          onFinish={onDatabase}
          requiredMark={false}
          initialValues={{ engine: "sqlite" }}
        >
          <Form.Item name="engine" label="存储引擎">
            <Radio.Group>
              <Radio value="sqlite">SQLite（本机文件库）</Radio>
              <Radio value="mysql">外部 MySQL / MariaDB</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item noStyle shouldUpdate>
            {({ getFieldValue }) =>
              getFieldValue("engine") === "sqlite" ? (
                <Typography.Paragraph type="secondary">
                  数据文件：{sqlitePath}。适合本机试用；生产多人建议外部库。
                </Typography.Paragraph>
              ) : (
                <Form.Item
                  name="url"
                  label="连接串"
                  rules={[{ required: true, message: "请填写连接串" }]}
                  extra="例如 mysql+pymysql://user:pass@127.0.0.1:3306/zhange_stats"
                >
                  <Input size="large" placeholder="mysql+pymysql://..." />
                </Form.Item>
              )
            }
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            size="large"
            block
            loading={loading || needsSetup === null}
            style={{ marginTop: 8 }}
          >
            下一步
          </Button>
        </Form>
      ) : (
        <Form layout="vertical" onFinish={onAdmin} requiredMark={false}>
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
      )}
    </AuthGuestShell>
  );
}
