import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Form, InputNumber, Typography, message } from "antd";
import { useEffect } from "react";
import { fetchAuthSettings, updateAuthSettings } from "@/api/client";

type FormValues = {
  access_token_expire_days: number;
};

export default function AuthSettingsPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();

  const { data, isLoading } = useQuery({
    queryKey: ["auth-settings"],
    queryFn: fetchAuthSettings,
  });

  useEffect(() => {
    if (!data) return;
    form.setFieldsValue({
      access_token_expire_days: data.access_token_expire_days || 30,
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: updateAuthSettings,
    onSuccess: () => {
      message.success("安全设置已保存（仅影响之后新登录的 token）");
      queryClient.invalidateQueries({ queryKey: ["auth-settings"] });
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

  return (
    <div>
      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 420 }}
        disabled={isLoading}
        onFinish={(values) => {
          const days = Number(values.access_token_expire_days) || 30;
          save.mutate({
            access_token_expire_minutes: Math.round(days * 24 * 60),
          });
        }}
      >
        <Form.Item
          name="access_token_expire_days"
          label="登录有效期（天）"
          extra="修改后仅对新登录生效；已发出的 token 仍按原过期时间。"
          rules={[
            { required: true, message: "请填写有效期" },
            { type: "number", min: 1, max: 365, message: "范围 1～365 天" },
          ]}
        >
          <InputNumber
            min={1}
            max={365}
            step={1}
            precision={0}
            style={{ width: "100%" }}
            size="large"
          />
        </Form.Item>

        <Button
          type="primary"
          htmlType="submit"
          size="large"
          loading={save.isPending}
          style={{ background: "#1a2332", borderColor: "#1a2332" }}
        >
          保存
        </Button>
      </Form>

      {data ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
          当前约 {data.access_token_expire_minutes} 分钟（
          {data.access_token_expire_days} 天）。
        </Typography.Paragraph>
      ) : null}
    </div>
  );
}
