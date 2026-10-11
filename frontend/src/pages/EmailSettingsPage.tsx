import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Typography,
  message,
} from "antd";
import { useState } from "react";
import { fetchEmailSettings, testEmailSettings, updateEmailSettings } from "@/api/client";
import type { EmailSettings } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { SecretFormItem } from "@/components/SecretFormItem";
import { hydrateForm, useHydrateUntouchedForm } from "@/hooks/useFormHydration";
import { apiError } from "@/lib/apiError";

/** 与后端发码时的上限一致（auth helpers MAX_CODE_EXPIRE_MINUTES）。 */
const CODE_EXPIRE_MAX_MINUTES = 30;

function clampCodeExpire(value: unknown): number {
  const n = Math.round(Number(value) || 15);
  return Math.min(CODE_EXPIRE_MAX_MINUTES, Math.max(1, n));
}

type FormValues = {
  enabled: boolean;
  smtp_user: string;
  smtp_from?: string;
  smtp_password?: string;
  display_name?: string;
  smtp_host: string;
  smtp_port: number;
  encryption: string;
  code_expire_minutes: number;
};

function toPayload(values: FormValues, clearPassword: boolean) {
  return {
    enabled: !!values.enabled,
    smtp_user: values.smtp_user || "",
    smtp_from: values.smtp_from || "",
    smtp_password: clearPassword ? null : values.smtp_password || null,
    clear_smtp_password: clearPassword,
    display_name: values.display_name || "",
    smtp_host: values.smtp_host || "",
    smtp_port: Number(values.smtp_port) || 465,
    encryption: values.encryption || "SSL",
    code_expire_minutes: clampCodeExpire(values.code_expire_minutes),
  };
}

function formValuesOf(data: EmailSettings): FormValues {
  return {
    enabled: data.enabled,
    smtp_user: data.smtp_user,
    smtp_from: data.smtp_from,
    smtp_password: "",
    display_name: data.display_name,
    smtp_host: data.smtp_host,
    smtp_port: data.smtp_port,
    encryption: data.encryption || "SSL",
    code_expire_minutes: clampCodeExpire(data.code_expire_minutes),
  };
}

export default function EmailSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [testOpen, setTestOpen] = useState(false);
  const [testTo, setTestTo] = useState("");
  const [clearPassword, setClearPassword] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["email-settings"],
    queryFn: fetchEmailSettings,
  });
  const passwordSet = Boolean(data?.smtp_password_set);

  useHydrateUntouchedForm(form, data, formValuesOf);

  const applySaved = (saved: EmailSettings) => {
    queryClient.setQueryData(["email-settings"], saved);
    hydrateForm(form, formValuesOf(saved));
    setClearPassword(false);
  };

  const save = useMutation({
    mutationFn: (payload: ReturnType<typeof toPayload>) =>
      updateEmailSettings(payload),
    onSuccess: (saved) => {
      applySaved(saved);
      message.success("邮箱设置已保存");
    },
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const test = useMutation({
    mutationFn: async ({
      payload,
      to,
    }: {
      payload: ReturnType<typeof toPayload>;
      to: string;
    }) => {
      applySaved(await updateEmailSettings(payload));
      return testEmailSettings(to);
    },
    onSuccess: (res) => {
      if (res.ok) message.success(res.message);
      else message.warning(res.message);
      setTestOpen(false);
    },
    onError: (e: unknown) => message.error(apiError(e, "测试失败")),
  });

  return (
    <div>
      <PageHeader title="邮箱设置" subtitle="注册验证码与系统通知所用的 SMTP 配置。" />
      <Form
        form={form}
        layout="vertical"
        requiredMark
        disabled={isLoading}
        onFinish={(values) => {
          save.mutate(toPayload(values, clearPassword));
        }}
        initialValues={{
          enabled: false,
          encryption: "SSL",
          smtp_port: 465,
          code_expire_minutes: 15,
        }}
      >
        <Form.Item name="enabled" valuePropName="checked" style={{ marginBottom: 20 }}>
          <Checkbox>启用邮件通知器</Checkbox>
        </Form.Item>

        <Form.Item
          name="code_expire_minutes"
          label="验证码有效期（分钟）"
          rules={[{ required: true, message: "请填写有效期" }]}
          extra={`最长 ${CODE_EXPIRE_MAX_MINUTES} 分钟`}
        >
          <InputNumber
            min={1}
            max={CODE_EXPIRE_MAX_MINUTES}
            precision={0}
            style={{ width: "100%" }}
          />
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.enabled !== cur.enabled}>
          {({ getFieldValue }) => {
            const enabled = !!getFieldValue("enabled");
            return (
              <>
                <Form.Item
                  name="smtp_user"
                  label="用户名"
                  rules={
                    enabled
                      ? [{ required: true, message: "请输入用户名" }]
                      : undefined
                  }
                >
                  <Input placeholder="user@example.com" />
                </Form.Item>

                <Form.Item
                  name="smtp_from"
                  label="发信地址"
                  extra={
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      如果用户名为实际发信地址，可忽略
                    </Typography.Text>
                  }
                >
                  <Input placeholder="noreply@example.com" />
                </Form.Item>

                <SecretFormItem
                  name="smtp_password"
                  label="密码"
                  required={enabled && !passwordSet}
                  rules={
                    enabled
                      ? [
                          {
                            validator: async (_, value) => {
                              if (clearPassword) {
                                throw new Error("启用时不能清除密码，可直接输入新密码替换");
                              }
                              if (value && String(value).trim()) return;
                              if (passwordSet) return;
                              throw new Error("请输入密码");
                            },
                          },
                        ]
                      : undefined
                  }
                  set={passwordSet}
                  clearing={clearPassword}
                  onClearingChange={setClearPassword}
                  emptyPlaceholder="请输入 SMTP 密码"
                  clearText="清除密码"
                />

                <Form.Item name="display_name" label="显示名称">
                  <Input placeholder="站点名称" />
                </Form.Item>

                <Form.Item
                  name="smtp_host"
                  label="SMTP 服务器地址"
                  rules={
                    enabled
                      ? [{ required: true, message: "请输入 SMTP 服务器地址" }]
                      : undefined
                  }
                >
                  <Input placeholder="smtp.example.com" />
                </Form.Item>

                <Form.Item
                  name="smtp_port"
                  label="端口号"
                  rules={
                    enabled
                      ? [{ required: true, message: "请输入端口号" }]
                      : undefined
                  }
                >
                  <InputNumber
                    min={1}
                    max={65535}
                    style={{ width: "100%" }}
                    placeholder="465"
                  />
                </Form.Item>

                <Form.Item name="encryption" label="加密方式">
                  <Select
                    options={[
                      { value: "SSL", label: "SSL" },
                      { value: "STARTTLS", label: "STARTTLS" },
                      { value: "NONE", label: "无（仅本机 SMTP）" },
                    ]}
                  />
                </Form.Item>
              </>
            );
          }}
        </Form.Item>

        <Space size={12} style={{ marginTop: 8 }}>
          <Button
            onClick={() => {
              const user = form.getFieldValue("smtp_user") || "";
              setTestTo(user);
              setTestOpen(true);
            }}
          >
            测试邮箱
          </Button>
          <Button
            type="primary"
            htmlType="submit"
            loading={save.isPending}
          >
            保存
          </Button>
        </Space>
      </Form>

      <Modal
        title="测试邮箱"
        open={testOpen}
        onCancel={() => setTestOpen(false)}
        onOk={() => {
          if (!testTo.trim()) {
            message.error("请填写收件邮箱");
            return;
          }
          form
            .validateFields()
            .then((values) => {
              test.mutate({
                payload: toPayload(values, clearPassword),
                to: testTo.trim(),
              });
            })
            .catch(() => {
              /* 校验错误已标在表单栏上 */
            });
        }}
        confirmLoading={test.isPending}
        okText="发送测试"
        cancelText="取消"
      >
        <Typography.Paragraph type="secondary">
          将先保存当前配置，再向该地址发送测试邮件。
        </Typography.Paragraph>
        <Input
          value={testTo}
          onChange={(e) => setTestTo(e.target.value)}
          placeholder="收件邮箱"
        />
      </Modal>
    </div>
  );
}
