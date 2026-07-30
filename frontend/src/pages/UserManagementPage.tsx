import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Popconfirm, Space, Table, Tag, message } from "antd";
import { Link } from "react-router-dom";
import { fetchUsers, updateUserRole, deleteUser } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { useAuthStore } from "@/stores/authStore";

export default function UserManagementPage() {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  const changeRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: "user" | "admin" }) =>
      updateUserRole(id, role),
    onSuccess: () => {
      message.success("角色已更新");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => message.error("更新角色失败"),
  });

  const removeUser = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      message.success("用户已删除");
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["members"] });
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

  return (
    <div>
      <PageHeader title="用户管理" subtitle="查看用户并配置角色" />
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
              return (
                <Space>
                  {row.member_id ? (
                    <Link to={`/members/${row.member_id}/profile`}>详情</Link>
                  ) : (
                    <Button type="link" disabled>
                      详情
                    </Button>
                  )}
                  {row.role === "admin" ? (
                    <Popconfirm
                      title="取消管理员权限？"
                      disabled={isSelf}
                      onConfirm={() =>
                        changeRole.mutate({ id: row.id, role: "user" })
                      }
                    >
                      <Button type="link" disabled={isSelf}>
                        设为普通用户
                      </Button>
                    </Popconfirm>
                  ) : (
                    <Popconfirm
                      title="提升为管理员？"
                      onConfirm={() =>
                        changeRole.mutate({ id: row.id, role: "admin" })
                      }
                    >
                      <Button type="link">设为管理员</Button>
                    </Popconfirm>
                  )}
                    <Popconfirm
                    title="确认删除该用户？"
                    description="将同步删除对应成员及其游玩记录"
                    disabled={isSelf}
                    onConfirm={() => removeUser.mutate(row.id)}
                  >
                    <Button type="link" danger disabled={isSelf}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              );
            },
          },
        ]}
      />
    </div>
  );
}
