import { useQuery } from "@tanstack/react-query";
import { Avatar, Empty, Table } from "antd";
import dayjs from "dayjs";
import { Link } from "react-router-dom";
import { fetchMembers } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

export default function MembersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["members"],
    queryFn: fetchMembers,
  });

  return (
    <div>
      <PageHeader title="成员" subtitle="与注册用户一一对应" />
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data ?? []}
        locale={{ emptyText: <Empty description="暂无成员" /> }}
        columns={[
          {
            title: "头像",
            dataIndex: "avatar_url",
            width: 80,
            render: (url: string | null, row) => (
              <Avatar src={url || undefined}>{row.nickname[0]}</Avatar>
            ),
          },
          {
            title: "昵称",
            dataIndex: "nickname",
            render: (name: string, row) => (
              <Link to={`/members/${row.id}`}>{name}</Link>
            ),
          },
          {
            title: "加入时间",
            dataIndex: "joined_at",
            render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
          },
        ]}
      />
    </div>
  );
}
