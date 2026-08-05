import { ReloadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiError } from "@/lib/apiError";
import {
  fetchIntegrationsSettings,
  fetchNapCatGroupMembers,
  fetchNapCatGroups,
  type NapCatGroup,
  type NapCatGroupMember,
} from "@/api/client";


export default function QqGroupsPage() {
  const queryClient = useQueryClient();
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  const integrations = useQuery({
    queryKey: ["integrations-settings"],
    queryFn: fetchIntegrationsSettings,
  });

  const configured = Boolean(integrations.data?.napcat_configured);

  const groupsQuery = useQuery({
    queryKey: ["napcat-groups"],
    queryFn: () => fetchNapCatGroups(false),
    enabled: configured,
    retry: false,
  });

  const membersQuery = useQuery({
    queryKey: ["napcat-group-members", selectedGroupId],
    queryFn: () => fetchNapCatGroupMembers(selectedGroupId!, false),
    enabled: configured && Boolean(selectedGroupId),
    retry: false,
  });

  const groups = groupsQuery.data?.groups ?? [];

  useEffect(() => {
    if (!groups.length) {
      setSelectedGroupId(null);
      return;
    }
    if (
      !selectedGroupId ||
      !groups.some((g) => g.group_id === selectedGroupId)
    ) {
      setSelectedGroupId(groups[0].group_id);
    }
  }, [groups, selectedGroupId]);

  const selectedGroup = useMemo(
    () => groups.find((g) => g.group_id === selectedGroupId) || null,
    [groups, selectedGroupId],
  );

  const refresh = async () => {
    try {
      const integ = await integrations.refetch();
      if (!integ.data?.napcat_configured) {
        message.warning("请先在「集成密钥」配置 NapCat");
        return;
      }
      await queryClient.fetchQuery({
        queryKey: ["napcat-groups"],
        queryFn: () => fetchNapCatGroups(true),
      });
      if (selectedGroupId) {
        await queryClient.fetchQuery({
          queryKey: ["napcat-group-members", selectedGroupId],
          queryFn: () => fetchNapCatGroupMembers(selectedGroupId, true),
        });
      }
      message.success("已刷新");
    } catch (e: unknown) {
      message.error(apiError(e, "刷新失败"));
    }
  };

  const groupColumns: ColumnsType<NapCatGroup> = [
    {
      title: "群名",
      dataIndex: "group_name",
      ellipsis: true,
    },
    {
      title: "群号",
      dataIndex: "group_id",
      width: 140,
    },
    {
      title: "人数",
      key: "count",
      width: 90,
      render: (_, row) =>
        row.member_count != null
          ? row.max_member_count != null
            ? `${row.member_count}/${row.max_member_count}`
            : String(row.member_count)
          : "-",
    },
  ];

  const memberColumns: ColumnsType<NapCatGroupMember> = [
    {
      title: "QQ 号",
      dataIndex: "user_id",
      width: 130,
    },
    {
      title: "群名片 / 昵称",
      key: "name",
      ellipsis: true,
      render: (_, row) => row.card || row.nickname || "-",
    },
    {
      title: "角色",
      dataIndex: "role",
      width: 90,
    },
    {
      title: "站内用户",
      key: "site",
      width: 200,
      render: (_, row) => {
        if (!row.site_member) {
          return <Tag>未关联</Tag>;
        }
        return (
          <Space size={4}>
            <Tag color="success">站内</Tag>
            <Link to={`/members/${row.site_member.id}`}>
              {row.site_member.nickname}
            </Link>
          </Space>
        );
      },
    },
  ];

  if (integrations.isLoading) {
    return <Typography.Text type="secondary">加载配置中…</Typography.Text>;
  }

  if (!configured) {
    return (
      <Alert
        type="info"
        showIcon
        message="尚未配置 NapCat"
        description={
          <span>
            请先在 <Link to="/settings/integrations">集成密钥</Link>{" "}
            填写 NapCat Base URL 与 Token。
          </span>
        }
      />
    );
  }

  const groupsError =
    groupsQuery.isError && groupsQuery.error
      ? apiError(groupsQuery.error, "加载群列表失败")
      : null;
  const membersError =
    membersQuery.isError && membersQuery.error
      ? apiError(membersQuery.error, "加载群成员失败")
      : null;

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <Typography.Text type="secondary">
          数据来自 NapCat；站内匹配依据成员资料中的 QQ 号。
          {selectedGroup && membersQuery.data
            ? ` 当前群站内用户 ${membersQuery.data.site_bound_count}/${membersQuery.data.members.length}`
            : null}
        </Typography.Text>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => void refresh()}
          loading={groupsQuery.isFetching || membersQuery.isFetching}
        >
          刷新
        </Button>
      </div>

      {groupsError ? (
        <Alert
          type="error"
          showIcon
          message={groupsError}
          style={{ marginBottom: 12 }}
        />
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(240px, 340px) minmax(0, 1fr)",
          gap: 16,
          alignItems: "start",
        }}
      >
        <Table<NapCatGroup>
          size="small"
          rowKey="group_id"
          loading={groupsQuery.isLoading}
          columns={groupColumns}
          dataSource={groups}
          pagination={false}
          scroll={{ y: 520 }}
          onRow={(row) => ({
            onClick: () => setSelectedGroupId(row.group_id),
            style: {
              cursor: "pointer",
              background:
                row.group_id === selectedGroupId
                  ? "rgba(47, 111, 78, 0.08)"
                  : undefined,
            },
          })}
          locale={{ emptyText: "暂无群" }}
        />

        <div>
          {membersError ? (
            <Alert
              type="error"
              showIcon
              message={membersError}
              style={{ marginBottom: 12 }}
            />
          ) : null}
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            {selectedGroup
              ? `${selectedGroup.group_name}（${selectedGroup.group_id}）`
              : "群成员"}
          </Typography.Title>
          <Table<NapCatGroupMember>
            size="small"
            rowKey="user_id"
            loading={Boolean(selectedGroupId) && membersQuery.isLoading}
            columns={memberColumns}
            dataSource={membersQuery.data?.members ?? []}
            pagination={{ pageSize: 50, showSizeChanger: true }}
            scroll={{ y: 480 }}
            locale={{
              emptyText: selectedGroupId ? "暂无成员" : "请选择群",
            }}
          />
        </div>
      </div>
    </div>
  );
}
