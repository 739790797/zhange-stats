import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Space,
  message,
} from "antd";
import { useEffect } from "react";
import { fetchMyProfile, updateMyProfile } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { useAuthStore } from "@/stores/authStore";

export default function ProfileSettingsPage() {
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const token = useAuthStore((s) => s.token);
  const authUser = useAuthStore((s) => s.user);
  const [form] = Form.useForm();

  const { data, isLoading, error, isError } = useQuery({
    queryKey: ["profile-me"],
    queryFn: fetchMyProfile,
    retry: false,
  });

  useEffect(() => {
    if (!data) return;
    form.setFieldsValue({
      display_name: data.display_name || data.nickname || "",
      steam_id: data.steam_id || "",
    });
  }, [data, form]);

  const save = useMutation({
    mutationFn: async (values: { display_name?: string; steam_id?: string }) =>
      updateMyProfile({
        display_name: values.display_name?.trim() || undefined,
        steam_id: values.steam_id?.trim() || null,
      }),
    onSuccess: (profile) => {
      message.success("个人设置已保存");
      queryClient.invalidateQueries({ queryKey: ["profile-me"] });
      // 同步顶栏显示名
      if (token && authUser) {
        setAuth(token, {
          ...authUser,
          display_name: profile.display_name || authUser.display_name,
        });
      }
    },
    onError: () => message.error("保存失败"),
  });

  const errMsg =
    isError && error && typeof error === "object" && "response" in error
      ? String(
          (error as { response?: { data?: { detail?: string } } }).response?.data
            ?.detail || "加载失败",
        )
      : null;

  return (
    <div>
      <PageHeader title="个人设置" subtitle="修改用户名与 Steam 绑定" />

      {errMsg ? (
        <Alert type="warning" showIcon message={errMsg} style={{ marginBottom: 16 }} />
      ) : null}

      {data ? (
        <Card loading={isLoading} style={{ marginBottom: 24 }}>
          <Space align="start" size={16}>
            <Avatar size={64} src={data.avatar_url || undefined}>
              {(data.display_name || data.nickname || "?")[0]}
            </Avatar>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="邮箱">
                {data.email || "-"}
              </Descriptions.Item>
            </Descriptions>
          </Space>
        </Card>
      ) : null}

      <Card title="资料与绑定" loading={isLoading && !errMsg}>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 480 }}
          onFinish={(v) => save.mutate(v)}
          disabled={!!errMsg}
        >
          <Form.Item
            name="display_name"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { max: 64, message: "最多 64 个字符" },
            ]}
            extra="展示用名称，登录仍使用邮箱"
          >
            <Input placeholder="怎么称呼你" />
          </Form.Item>
          <Form.Item
            name="steam_id"
            label="Steam ID"
            extra="64 位 SteamID（如 7656119…），资料需对好友/公开可见才能监控正在游玩"
          >
            <Input placeholder="可选" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={save.isPending}>
            保存
          </Button>
        </Form>
      </Card>
    </div>
  );
}
