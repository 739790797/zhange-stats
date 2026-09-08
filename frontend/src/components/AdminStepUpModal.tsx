import { Alert, Button, Form, Input, Modal, Space, Typography } from "antd";
import { useEffect, useState } from "react";
import { sendStepUpCode } from "@/api/authApi";
import { adminCanStepUp } from "@/lib/adminCanStepUp";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";

type Props = {
  open: boolean;
  title?: string;
  confirmLoading?: boolean;
  onCancel: () => void;
  onConfirm: (code: string) => void;
};

export function AdminStepUpModal({
  open,
  title = "邮箱验证码确认",
  confirmLoading,
  onCancel,
  onConfirm,
}: Props) {
  const [form] = Form.useForm<{ code: string }>();
  const [sending, setSending] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const user = useAuthStore((s) => s.user);
  const can = adminCanStepUp(user);

  useEffect(() => {
    if (!open) {
      form.resetFields();
      setHint(null);
    }
  }, [open, form]);

  const send = async () => {
    setSending(true);
    try {
      const res = await sendStepUpCode();
      setHint(res.message);
    } catch (e: unknown) {
      setHint(apiError(e, "发送失败"));
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onCancel}
      okText="确认"
      confirmLoading={confirmLoading}
      destroyOnClose
      okButtonProps={{ disabled: !can }}
      onOk={() => form.submit()}
    >
      {!can ? (
        <Alert
          type="warning"
          showIcon
          message="请先在个人中心绑定并验证邮箱，才能执行此操作"
        />
      ) : (
        <>
          <Typography.Paragraph type="secondary">
            系统更新、删除用户、保存集成密钥等操作需要邮箱验证码。
          </Typography.Paragraph>
          {hint ? (
            <Alert type="info" showIcon message={hint} style={{ marginBottom: 12 }} />
          ) : null}
          <Form
            form={form}
            layout="vertical"
            onFinish={(values) => onConfirm(values.code.trim())}
          >
            <Form.Item label="验证码" required>
              <Space.Compact style={{ width: "100%" }}>
                <Form.Item
                  name="code"
                  noStyle
                  rules={[{ required: true, message: "请输入验证码" }]}
                >
                  <Input maxLength={16} autoComplete="one-time-code" />
                </Form.Item>
                <Button loading={sending} onClick={() => void send()}>
                  发送验证码
                </Button>
              </Space.Compact>
            </Form.Item>
          </Form>
        </>
      )}
    </Modal>
  );
}
