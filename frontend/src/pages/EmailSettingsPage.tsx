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
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchEmailSettings,
  testEmailSettings,
  updateEmailSettings,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

type FormValues = {
  enabled: boolean;
  smtp_user: string;
  smtp_from?: string;
  smtp_password?: string;
  display_name?: string;
  smtp_host: string;
  smtp_port: number;
  encryption: string;
};

function toPayload(values: FormValues) {
  return {
    enabled: !!values.enabled,
    smtp_user: values.smtp_user || "",
    smtp_from: values.smtp_from || "",
    smtp_password: values.smtp_password || null,
    display_name: values.display_name || "",
    smtp_host: values.smtp_host || "",
    smtp_port: Number(values.smtp_port) || 465,
    encryption: values.encryption || "SSL",
  };
}

export default function EmailSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const [testOpen, setTestOpen] = useState(false);
  const [testTo, setTestTo] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["email-settings"],
    queryFn: fetchEmailSettings,
  });

  useEffect(() => {
    if (!data) return;
    form.setFieldsValue({
      enabled: data.enabled,
      smtp_user: data.smtp_user,
      smtp_from: data.smtp_from,
      smtp_password: "",
      display_name: data.display_name,
      smtp_host: data.smtp_host,
      smtp_port: data.smtp_port,
      encryption: data.encryption || "SSL",
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: updateEmailSettings,
    onSuccess: () => {
      message.success("邮箱设置已保存");
      queryClient.invalidateQueries({ queryKey: ["email-settings"] });
      form.setFieldValue("smtp_password", "");
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "保存失败"));
    },
  });

  const test = useMutation({
    mutationFn: async (to: string) => {
      const values = await form.validateFields();
      await updateEmailSettings(toPayload(values));
      return testEmailSettings(to);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["email-settings"] });
      form.setFieldValue("smtp_password", "");
      if (res.ok) message.success(res.message);
      else message.warning(res.message);
      setTestOpen(false);
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "测试失败"));
    },
  });

  return (
    <div>
      <PageHeader
        title="邮箱设置"
        subtitle="配置注册验证码等系统邮件发送"
        extra={<Link to="/settings/users">用户管理</Link>}
      />

      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 480 }}
        requiredMark
        disabled={isLoading}
        onFinish={(values) => save.mutate(toPayload(values))}
        initialValues={{ enabled: false, encryption: "SSL", smtp_port: 465 }}
      >
        <Form.Item name="enabled" valuePropName="checked" style={{ marginBottom: 20 }}>
          <Checkbox>启用邮件通知器</Checkbox>
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
                  <Input placeholder="如 2753478236@qq.com" size="large" />
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
                  <Input placeholder="可选" size="large" />
                </Form.Item>

                <Form.Item
                  name="smtp_password"
                  label="密码"
                  rules={
                    enabled
                      ? [
                          {
                            validator: async (_, value) => {
                              if (value && String(value).trim()) return;
                              if (data?.smtp_password_set) return;
                              throw new Error("请输入密码");
                            },
                          },
                        ]
                      : undefined
                  }
                >
                  <Input.Password
                    placeholder={
                      data?.smtp_password_set ? "已保存，留空不修改" : "请输入密码"
                    }
                    size="large"
                    autoComplete="new-password"
                  />
                </Form.Item>

                <Form.Item name="display_name" label="显示名称">
                  <Input placeholder="如 战鸽波波" size="large" />
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
                  <Input placeholder="如 smtp.qq.com" size="large" />
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
                    size="large"
                    placeholder="如 465"
                  />
                </Form.Item>

                <Form.Item name="encryption" label="加密方式">
                  <Select
                    size="large"
                    options={[
                      { value: "SSL", label: "SSL" },
                      { value: "STARTTLS", label: "STARTTLS" },
                      { value: "NONE", label: "无" },
                    ]}
                  />
                </Form.Item>
              </>
            );
          }}
        </Form.Item>

        <Space size={12} style={{ marginTop: 8 }}>
          <Button
            size="large"
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
            size="large"
            loading={save.isPending}
            style={{ background: "#1a2332", borderColor: "#1a2332" }}
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
          test.mutate(testTo.trim());
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
