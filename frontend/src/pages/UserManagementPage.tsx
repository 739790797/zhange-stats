import { QqOutlined } from "@ant-design/icons";
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
  message,
} from "antd";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createUser,
  deleteUser,
  fetchIntegrationsSettings,
  fetchUsers,
  updateUser,
} from "@/api/client";
import type { UserBrief } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { PlatformIcon } from "@/components/PlatformIcon";
import { apiError } from "@/lib/apiError";
import { isAdminUser } from "@/lib/isAdminUser";
import type { PlatformIconName } from "@/lib/platformIcons";
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
    | "mihoyo_bound"
    | "qq_bound"
  >;
  label: string;
  icon: PlatformIconName | "qq";
};

const BIND_ICON_SIZE = 14;

const BASE_PLATFORMS: BindPlatform[] = [
  { key: "steam_bound", label: "Steam", icon: "steam" },
  { key: "skland_bound", label: "森空岛", icon: "skland" },
  { key: "taygedo_bound", label: "塔吉多", icon: "taygedo" },
  { key: "exilium_bound", label: "追放", icon: "exilium" },
  { key: "kujiequ_bound", label: "库街区", icon: "kujiequ" },
  { key: "mihoyo_bound", label: "米游社", icon: "mihoyo" },
];

function BindPlatformMark({ icon }: { icon: PlatformIconName | "qq" }) {
  if (icon === "qq") {
    return (
      <span
        className="anticon"
        role="img"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: BIND_ICON_SIZE,
          height: BIND_ICON_SIZE,
          fontSize: BIND_ICON_SIZE,
          verticalAlign: "-0.125em",
          flexShrink: 0,
          color: "#12b7f5",
        }}
      >
        <QqOutlined />
      </span>
    );
  }
  return <PlatformIcon name={icon} size={BIND_ICON_SIZE} />;
}

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
          <Tag key={p.key} color={bound ? "success" : undefined} title={p.label}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <BindPlatformMark icon={p.icon} />
              {bound ? "已绑" : "未绑"}
            </span>
          </Tag>
        );
      })}
    </Space>
  );
}

export default function UserManagementPage() {
  const navigate = useNavigate();
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
      list.push({ key: "qq_bound", label: "QQ", icon: "qq" });
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
    onError: (e: unknown) => message.error(apiError(e, "添加失败")),
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
    onError: (e: unknown) => message.error(apiError(e, "保存失败")),
  });

  const removeUser = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      message.success("用户已删除");
      invalidate();
    },
    onError: (e: unknown) => message.error(apiError(e, "删除失败")),
  });

  const openEdit = (row: UserBrief) => {
    setEditing(row);
    editForm.setFieldsValue({
      email: row.email || "",
      display_name: row.display_name || "",
      password: "",
      role: isAdminUser(row) ? "admin" : "user",
    });
  };

  return (
    <div>
      <PageHeader
        title="用户管理"
        subtitle="添加、编辑用户并设置角色。绑定由用户在个人中心自行完成；口令策略与管理员安全状态见「安全设置」。"
        extra={
          <Button type="primary" onClick={() => setCreateOpen(true)}>
            添加用户
          </Button>
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
            width: 200,
            render: (_, row) => {
              const isSelf = row.id === currentUser?.id;
              const isAdmin = isAdminUser(row);
              return (
                <Space>
                  <Button type="link" onClick={() => openEdit(row)}>
                    编辑
                  </Button>
                  {row.member_id != null ? (
                    <Button
                      type="link"
                      onClick={() => navigate(`/members/${row.member_id}/profile`)}
                    >
                      资料
                    </Button>
                  ) : null}
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
