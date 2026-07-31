import { ReloadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Empty,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import dayjs from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import { Link } from "react-router-dom";
import { fetchSteamFriends } from "@/api/client";
import type { SteamFriendItem } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";

dayjs.extend(utc);
dayjs.extend(timezone);

function statusTag(status: string) {
  if (status === "playing") return <Tag color="green">游戏中</Tag>;
  if (status === "online") return <Tag color="blue">在线</Tag>;
  return <Tag>离线</Tag>;
}

function formatSyncTime(iso: string | null | undefined) {
  if (!iso) return null;
  return dayjs.utc(iso).tz("Asia/Shanghai").format("YYYY-MM-DD HH:mm:ss");
}

export default function FriendsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error, isError } = useQuery({
    queryKey: ["steam-friends"],
    queryFn: () => fetchSteamFriends(false),
  });

  const refresh = useMutation({
    mutationFn: () => fetchSteamFriends(true),
    onSuccess: (res) => {
      queryClient.setQueryData(["steam-friends"], res);
      if (res.sync_ok) {
        message.success(
          res.synced ? "好友列表已刷新" : "已是最新，无需重复同步",
        );
      } else {
        message.warning(res.hint || "同步未完成");
      }
    },
    onError: (e: unknown) => {
      const detail =
        e &&
        typeof e === "object" &&
        "response" in e &&
        (e as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      message.error(String(detail || "刷新失败"));
    },
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
        title="好友"
        subtitle={
          formatSyncTime(data?.friends_synced_at)
            ? `上次同步 ${formatSyncTime(data?.friends_synced_at)}`
            : undefined
        }
        extra={
          <Button
            icon={<ReloadOutlined />}
            loading={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            刷新
          </Button>
        }
      />

      {errMsg ? (
        <Alert type="error" showIcon message={errMsg} style={{ marginBottom: 16 }} />
      ) : null}

      {data?.hint ? (
        <Alert
          type={
            data.friends_list_public === false || !data.steam_bound
              ? "warning"
              : "info"
          }
          showIcon
          message={data.hint}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Table<SteamFriendItem>
        rowKey="steam_id"
        loading={isLoading || refresh.isPending}
        dataSource={data?.friends ?? []}
        locale={{
          emptyText: (
            <Empty
              description={
                data?.steam_bound
                  ? "暂无好友，或好友列表未公开"
                  : "绑定 Steam 后可查看好友"
              }
            />
          ),
        }}
        pagination={{ pageSize: 50, showSizeChanger: true }}
        columns={[
          {
            title: "好友",
            key: "friend",
            render: (_, row) => (
              <Space>
                <Avatar src={row.avatar_url || undefined}>
                  {(row.persona_name || "?")[0]}
                </Avatar>
                <div>
                  {row.member_id ? (
                    <Link to={`/members/${row.member_id}`}>{row.persona_name}</Link>
                  ) : (
                    <Typography.Text>{row.persona_name}</Typography.Text>
                  )}
                  {row.is_registered ? (
                    <div>
                      <Tag color="gold" style={{ marginTop: 2 }}>
                        站内用户
                      </Tag>
                    </div>
                  ) : null}
                </div>
              </Space>
            ),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (status: string) => statusTag(status),
          },
          {
            title: "正在玩",
            dataIndex: "game_name",
            render: (name: string | null) => name || "—",
          },
          {
            title: "成为好友",
            dataIndex: "friend_since",
            width: 140,
            render: (ts: number | null) =>
              ts ? dayjs.unix(ts).format("YYYY-MM-DD") : "—",
          },
        ]}
      />
    </div>
  );
}
