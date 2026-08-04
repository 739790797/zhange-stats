import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useMemo, useState } from "react";
import {
  createUser,
  deleteUser,
  fetchIntegrationsSettings,
  fetchUsers,
  updateUser,
} from "@/api/client";
import type { UserBrief } from "@/api/types";
import { useAuthStore } from "@/stores/authStore";

type UserFormValues = {
  email: string;
  display_name: string;
  password?: string;
  role?: "admin" | "user";
};

type BindPlatform = {
  key: keyof Pick<
    UserBrief,
    | "steam_bound"
    | "skland_bound"
    | "taygedo_bound"
    | "exilium_bound"
    | "kujiequ_bound"
    | "qq_bound"
  >;
  label: string;
};

const BASE_PLATFORMS: BindPlatform[] = [
  { key: "steam_bound", label: "Steam" },
  { key: "skland_bound", label: "森空岛" },
  { key: "taygedo_bound", label: "塔吉多" },
  { key: "exilium_bound", label: "追放" },
  { key: "kujiequ_bound", label: "库街区" },
];

function BindStatusTags({
  row,
  platforms,
}: {
  row: UserBrief;
  platforms: BindPlatform[];
}) {
  return (
    <Space size={[4, 4]} wrap>
      {platforms.map((p) => {
        const bound = Boolean(row[p.key]);
        return (
          <Tag key={p.key} color={bound ? "success" : undefined}>
            {p.label}
            {bound ? " · 已绑" : " · 未绑"}
          </Tag>
        );
      })}
    </Space>
  );
}

export default function UserManagementPage() {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<UserBrief | null>(null);
  const [createForm] = Form.useForm<UserFormValues>();
  const [editForm] = Form.useForm<UserFormValues>();

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  const { data: integrations } = useQuery({
    queryKey: ["integrations-settings"],
    queryFn: fetchIntegrationsSettings,
  });

  const platforms = useMemo(() => {
    const list = [...BASE_PLATFORMS];
    if (integrations?.qq_configured) {
      list.push({ key: "qq_bound", label: "QQ" });
    }
    return list;
  }, [integrations?.qq_configured]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["users"] });
    queryClient.invalidateQueries({ queryKey: ["members"] });
  };

  const addUser = useMutation({
    mutationFn: (values: UserFormValues) =>
      createUser({
        email: values.email.trim(),
        display_name: values.display_name.trim(),
        password: values.password || "",
      }),
    onSuccess: () => {
      message.success("用户已添加");
      setCreateOpen(false);
      createForm.resetFields();
      invalidate();
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "添加失败"));
    },
  });

  const saveUser = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: number;
      values: UserFormValues;
    }) => {
      const payload: {
        email?: string;
        display_name?: string;
        password?: string;
        role?: "admin" | "user";
      } = {
        email: values.email.trim(),
        display_name: values.display_name.trim(),
        role: values.role === "admin" ? "admin" : "user",
      };
      if (values.password?.trim()) {
        payload.password = values.password.trim();
      }
      return updateUser(id, payload);
    },
    onSuccess: () => {
      message.success("用户已更新");
      setEditing(null);
      editForm.resetFields();
      invalidate();
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

  const removeUser = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      message.success("用户已删除");
      invalidate();
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "删除失败"));
    },
  });

  const openEdit = (row: UserBrief) => {
    setEditing(row);
    editForm.setFieldsValue({
      email: row.email || "",
      display_name: row.display_name || "",
      password: "",
      role: row.role === "admin" || row.is_admin ? "admin" : "user",
    });
  };

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 16,
          gap: 16,
        }}
      >
        <Typography.Text type="secondary">
          管理员可添加、编辑用户并设置角色（普通用户 / 管理员，可多名）。绑定由用户在个人中心自行完成。
        </Typography.Text>
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          添加用户
        </Button>
      </div>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={users ?? []}
        columns={[
          { title: "用户名", dataIndex: "display_name" },
          {
            title: "邮箱",
            dataIndex: "email",
            render: (v: string | null | undefined) => v || "-",
          },
          {
            title: "平台绑定",
            key: "binds",
            render: (_, row) => (
              <BindStatusTags row={row} platforms={platforms} />
            ),
          },
          {
            title: "角色",
            dataIndex: "role",
            width: 100,
            render: (role: string) =>
              role === "admin" ? (
                <Tag color="gold">管理员</Tag>
              ) : (
                <Tag>普通用户</Tag>
              ),
          },
          {
            title: "操作",
            width: 140,
            render: (_, row) => {
              const isSelf = row.id === currentUser?.id;
              const isAdmin = row.role === "admin" || row.is_admin;
              return (
                <Space>
                  <Button type="link" onClick={() => openEdit(row)}>
                    编辑
                  </Button>
                  <Popconfirm
                    title="确认删除该用户？"
                    description="将同步删除对应成员及其游玩记录"
                    disabled={isSelf || isAdmin}
                    okText="确定"
                    cancelText="取消"
                    onConfirm={() => removeUser.mutate(row.id)}
                  >
                    <Button type="link" danger disabled={isSelf || isAdmin}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              );
            },
          },
        ]}
      />

      <Modal
        title="添加用户"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false);
          createForm.resetFields();
        }}
        onOk={() => createForm.submit()}
        okText="添加"
        cancelText="取消"
        confirmLoading={addUser.isPending}
        destroyOnClose
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={(values) => addUser.mutate(values)}
        >
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input placeholder="登录邮箱" autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="display_name"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input placeholder="展示名称" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 8, message: "密码至少 8 位" },
            ]}
          >
            <Input.Password placeholder="初始密码" autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑用户"
        open={!!editing}
        onCancel={() => {
          setEditing(null);
          editForm.resetFields();
        }}
        onOk={() => editForm.submit()}
        okText="保存"
        cancelText="取消"
        confirmLoading={saveUser.isPending}
        destroyOnClose
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={(values) => {
            if (!editing) return;
            saveUser.mutate({ id: editing.id, values });
          }}
        >
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="display_name"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            extra="留空则不修改密码"
            rules={[
              {
                validator: async (_, value) => {
                  if (!value || !String(value).trim()) return;
                  if (String(value).trim().length < 6) {
                    throw new Error("密码至少 8 位");
                  }
                },
              },
            ]}
          >
            <Input.Password
              placeholder="新密码（可选）"
              autoComplete="new-password"
            />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: "请选择角色" }]}
            extra={
              editing && currentUser?.id === editing.id
                ? "不能将自己的角色改为普通用户"
                : undefined
            }
          >
            <Select
              options={[
                { value: "user", label: "普通用户" },
                { value: "admin", label: "管理员" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
