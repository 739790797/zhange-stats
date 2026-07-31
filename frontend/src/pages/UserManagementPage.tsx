import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  message,
} from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { createUser, deleteUser, fetchUsers, updateUser } from "@/api/client";
import type { UserBrief } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { useAuthStore } from "@/stores/authStore";

type UserFormValues = {
  email: string;
  display_name: string;
  password?: string;
  steam_id?: string;
};

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
        steam_id: values.steam_id?.trim() || null,
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
        steam_id?: string | null;
      } = {
        email: values.email.trim(),
        display_name: values.display_name.trim(),
        steam_id: values.steam_id?.trim() || null,
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
      steam_id: row.steam_id || "",
    });
  };

  return (
    <div>
      <PageHeader
        title="用户管理"
        subtitle="管理员可添加、编辑普通用户；系统仅保留一名管理员"
        extra={
          <Space>
            <Link to="/settings/email">邮箱设置</Link>
            <Button type="primary" onClick={() => setCreateOpen(true)}>
              添加用户
            </Button>
          </Space>
        }
      />
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
            title: "Steam ID",
            dataIndex: "steam_id",
            render: (v: string | null | undefined) => v || "-",
          },
          {
            title: "角色",
            dataIndex: "role",
            render: (role: string) =>
              role === "admin" ? (
                <Tag color="gold">管理员</Tag>
              ) : (
                <Tag>普通用户</Tag>
              ),
          },
          {
            title: "操作",
            render: (_, row) => {
              const isSelf = row.id === currentUser?.id;
              const isAdmin = row.role === "admin" || row.is_admin;
              return (
                <Space>
                  {row.member_id ? (
                    <Link to={`/members/${row.member_id}/profile`}>个人中心</Link>
                  ) : (
                    <Button type="link" disabled>
                      个人中心
                    </Button>
                  )}
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
              { min: 6, message: "密码至少 6 位" },
            ]}
          >
            <Input.Password placeholder="初始密码" autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="steam_id" label="Steam ID">
            <Input placeholder="可选" />
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
                    throw new Error("密码至少 6 位");
                  }
                },
              },
            ]}
          >
            <Input.Password placeholder="新密码（可选）" autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="steam_id" label="Steam ID">
            <Input placeholder="可选，清空则解除绑定" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
