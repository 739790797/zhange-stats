import { Button, Form, Input, Modal, Space, Tabs, Typography, message } from "antd";
import { useEffect, useState } from "react";
import {
  bindEmail,
  linkExistingAccount,
  sendBindEmailCode,
} from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

const SKIP_KEY = "zhange-skip-complete-profile";

type Props = {
  open: boolean;
  onClose: () => void;
  onCompleted: () => void;
};

export function CompleteProfileModal({ open, onClose, onCompleted }: Props) {
  const setAuth = useAuthStore((s) => s.setAuth);
  const setUser = useAuthStore((s) => s.setUser);
  const [bindForm] = Form.useForm();
  const [linkForm] = Form.useForm();
  const [tab, setTab] = useState("bind");
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [linking, setLinking] = useState(false);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = window.setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => window.clearTimeout(t);
  }, [countdown]);

  useEffect(() => {
    if (!open) {
      bindForm.resetFields();
      linkForm.resetFields();
      setCountdown(0);
      setTab("bind");
    }
  }, [open, bindForm, linkForm]);

  const onSendCode = async () => {
    try {
      const { email } = await bindForm.validateFields(["email"]);
      setSending(true);
      const res = await sendBindEmailCode(email);
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
      message.error(String(detail || "发送验证码失败"));
    } finally {
      setSending(false);
    }
  };

  const onBindEmail = async (values: {
    email: string;
    code: string;
    password?: string;
  }) => {
    setSaving(true);
    try {
      const res = await bindEmail({
        email: values.email,
        code: values.code,
        password: values.password?.trim() || undefined,
      });
      setUser(res.user);
      message.success(res.message || "账号已完善");
      sessionStorage.removeItem(SKIP_KEY);
      onCompleted();
    } catch (e: unknown) {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "完善失败"));
    } finally {
      setSaving(false);
    }
  };

  const onLinkExisting = async (values: { email: string; password: string }) => {
    setLinking(true);
    try {
      const res = await linkExistingAccount({
        email: values.email,
        password: values.password,
      });
      setAuth(res.access_token, res.user);
      message.success(res.message || "已合并到已有账号");
      sessionStorage.removeItem(SKIP_KEY);
      onCompleted();
    } catch (e: unknown) {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "合并失败"));
    } finally {
      setLinking(false);
    }
  };

  const onSkip = () => {
    sessionStorage.setItem(SKIP_KEY, "1");
    onClose();
  };

  return (
    <Modal
      title="完善账号"
      open={open}
      footer={null}
      onCancel={onSkip}
      destroyOnClose
      maskClosable={false}
    >
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: "bind",
            label: "绑定邮箱",
            children: (
              <>
                <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                  为当前 QQ 账号绑定邮箱以便找回；密码可选，不设则继续用 QQ
                  登录。
                </Typography.Paragraph>
                <Form
                  form={bindForm}
                  layout="vertical"
                  onFinish={onBindEmail}
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
                      placeholder="用于登录与找回"
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
                    label="密码（可选）"
                    rules={[
                      {
                        validator: (_, value) => {
                          const v = String(value || "").trim();
                          if (!v) return Promise.resolve();
                          if (v.length < 8) {
                            return Promise.reject(new Error("至少 8 位"));
                          }
                          return Promise.resolve();
                        },
                      },
                    ]}
                  >
                    <Input.Password
                      size="large"
                      placeholder="不填则仅能用 QQ 登录"
                      autoComplete="new-password"
                    />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    size="large"
                    block
                    loading={saving}
                  >
                    完成
                  </Button>
                </Form>
              </>
            ),
          },
          {
            key: "link",
            label: "绑已有账号",
            children: (
              <>
                <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                  若你以前用邮箱注册过，可验证后把当前 QQ
                  挂到老账号（临时号将被删除）。
                </Typography.Paragraph>
                <Form
                  form={linkForm}
                  layout="vertical"
                  onFinish={onLinkExisting}
                  requiredMark={false}
                >
                  <Form.Item
                    name="email"
                    label="已有账号邮箱"
                    rules={[
                      { required: true, message: "请输入邮箱" },
                      { type: "email", message: "邮箱格式不正确" },
                    ]}
                  >
                    <Input
                      size="large"
                      placeholder="原账号邮箱"
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
                      placeholder="原账号密码"
                      autoComplete="current-password"
                    />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    size="large"
                    block
                    loading={linking}
                  >
                    合并到已有账号
                  </Button>
                </Form>
              </>
            ),
          },
        ]}
      />
      <Button size="large" block style={{ marginTop: 16 }} onClick={onSkip}>
        稍后完善
      </Button>
    </Modal>
  );
}

export function shouldPromptCompleteProfile(email?: string | null): boolean {
  if (email) return false;
  return sessionStorage.getItem(SKIP_KEY) !== "1";
}
