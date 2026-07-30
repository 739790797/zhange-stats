import { useQuery } from "@tanstack/react-query";
import { Alert, Avatar, Card, Descriptions, Space, Typography } from "antd";
import dayjs from "dayjs";
import { Link, useParams } from "react-router-dom";
import { fetchMemberProfile } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

export default function MemberProfilePage() {
  const { id } = useParams();
  const memberId = Number(id);

  const { data, isLoading, error, isError } = useQuery({
    queryKey: ["member-profile", memberId],
    queryFn: () => fetchMemberProfile(memberId),
    enabled: Number.isFinite(memberId),
    retry: false,
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
      <PageHeader
        title="个人设置详情"
        subtitle="只读查看该成员的平台绑定信息"
        extra={<Link to="/settings/users">返回用户管理</Link>}
      />

      {errMsg ? <Alert type="error" showIcon message={errMsg} /> : null}

      <Card loading={isLoading} style={{ marginBottom: 16 }}>
        {data ? (
          <Space align="start" size={16}>
            <Avatar size={64} src={data.avatar_url || undefined}>
              {data.nickname[0]}
            </Avatar>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="成员昵称">{data.nickname}</Descriptions.Item>
              <Descriptions.Item label="邮箱">
                {data.email || "未关联"}
              </Descriptions.Item>
              <Descriptions.Item label="加入时间">
                {dayjs(data.joined_at).format("YYYY-MM-DD HH:mm")}
              </Descriptions.Item>
            </Descriptions>
          </Space>
        ) : null}
      </Card>

      <Card title="Steam 绑定" loading={isLoading}>
        {data ? (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Steam ID">
              {data.steam_id || (
                <Typography.Text type="secondary">未绑定</Typography.Text>
              )}
            </Descriptions.Item>
          </Descriptions>
        ) : null}
      </Card>
    </div>
  );
}
