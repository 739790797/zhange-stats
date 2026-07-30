import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tabs,
  message,
} from "antd";
import dayjs from "dayjs";
import { useState } from "react";
import {
  createGame,
  createMember,
  deleteGame,
  deleteMember,
  fetchGames,
  fetchMembers,
  updateGame,
  updateMember,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [memberOpen, setMemberOpen] = useState(false);
  const [gameOpen, setGameOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<number | null>(null);
  const [editingGame, setEditingGame] = useState<number | null>(null);
  const [memberForm] = Form.useForm();
  const [gameForm] = Form.useForm();

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ["members"],
    queryFn: fetchMembers,
  });
  const { data: games, isLoading: gamesLoading } = useQuery({
    queryKey: ["games"],
    queryFn: fetchGames,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["members"] });
    queryClient.invalidateQueries({ queryKey: ["games"] });
  };

  const saveMember = useMutation({
    mutationFn: async (values: { nickname: string; avatar_url?: string }) => {
      if (editingMember) {
        return updateMember(editingMember, values);
      }
      return createMember(values);
    },
    onSuccess: () => {
      message.success("成员已保存");
      setMemberOpen(false);
      setEditingMember(null);
      memberForm.resetFields();
      invalidate();
    },
    onError: () => message.error("保存失败"),
  });

  const saveGame = useMutation({
    mutationFn: async (values: {
      name: string;
      platform?: string;
      icon_url?: string;
    }) => {
      if (editingGame) {
        return updateGame(editingGame, values);
      }
      return createGame(values);
    },
    onSuccess: () => {
      message.success("游戏已保存");
      setGameOpen(false);
      setEditingGame(null);
      gameForm.resetFields();
      invalidate();
    },
    onError: () => message.error("保存失败"),
  });

  return (
    <div>
      <PageHeader title="系统设置" subtitle="成员管理与游戏字典（管理员）" />
      <Tabs
        items={[
          {
            key: "members",
            label: "成员管理",
            children: (
              <>
                <Button
                  type="primary"
                  style={{ marginBottom: 16 }}
                  onClick={() => {
                    setEditingMember(null);
                    memberForm.resetFields();
                    setMemberOpen(true);
                  }}
                >
                  新增成员
                </Button>
                <Table
                  rowKey="id"
                  loading={membersLoading}
                  dataSource={members ?? []}
                  columns={[
                    { title: "昵称", dataIndex: "nickname" },
                    {
                      title: "头像 URL",
                      dataIndex: "avatar_url",
                      ellipsis: true,
                      render: (v) => v || "-",
                    },
                    {
                      title: "加入时间",
                      dataIndex: "joined_at",
                      render: (v: string) =>
                        dayjs(v).format("YYYY-MM-DD HH:mm"),
                    },
                    {
                      title: "操作",
                      render: (_, row) => (
                        <Space>
                          <Button
                            type="link"
                            onClick={() => {
                              setEditingMember(row.id);
                              memberForm.setFieldsValue({
                                nickname: row.nickname,
                                avatar_url: row.avatar_url,
                              });
                              setMemberOpen(true);
                            }}
                          >
                            编辑
                          </Button>
                          <Popconfirm
                            title="确认删除该成员？"
                            onConfirm={async () => {
                              try {
                                await deleteMember(row.id);
                                message.success("已删除");
                                invalidate();
                              } catch {
                                message.error("删除失败（可能仍有关联战绩）");
                              }
                            }}
                          >
                            <Button type="link" danger>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: "games",
            label: "游戏字典",
            children: (
              <>
                <Button
                  type="primary"
                  style={{ marginBottom: 16 }}
                  onClick={() => {
                    setEditingGame(null);
                    gameForm.resetFields();
                    setGameOpen(true);
                  }}
                >
                  新增游戏
                </Button>
                <Table
                  rowKey="id"
                  loading={gamesLoading}
                  dataSource={games ?? []}
                  columns={[
                    { title: "名称", dataIndex: "name" },
                    { title: "平台", dataIndex: "platform" },
                    {
                      title: "图标 URL",
                      dataIndex: "icon_url",
                      ellipsis: true,
                      render: (v) => v || "-",
                    },
                    {
                      title: "操作",
                      render: (_, row) => (
                        <Space>
                          <Button
                            type="link"
                            onClick={() => {
                              setEditingGame(row.id);
                              gameForm.setFieldsValue({
                                name: row.name,
                                platform: row.platform,
                                icon_url: row.icon_url,
                              });
                              setGameOpen(true);
                            }}
                          >
                            编辑
                          </Button>
                          <Popconfirm
                            title="确认删除该游戏？"
                            onConfirm={async () => {
                              try {
                                await deleteGame(row.id);
                                message.success("已删除");
                                invalidate();
                              } catch {
                                message.error("删除失败（可能仍有关联战绩）");
                              }
                            }}
                          >
                            <Button type="link" danger>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
        ]}
      />

      <Modal
        title={editingMember ? "编辑成员" : "新增成员"}
        open={memberOpen}
        onCancel={() => setMemberOpen(false)}
        onOk={() => memberForm.submit()}
        confirmLoading={saveMember.isPending}
        destroyOnClose
      >
        <Form
          form={memberForm}
          layout="vertical"
          onFinish={(v) => saveMember.mutate(v)}
        >
          <Form.Item
            name="nickname"
            label="昵称"
            rules={[{ required: true, message: "请输入昵称" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="avatar_url" label="头像 URL">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingGame ? "编辑游戏" : "新增游戏"}
        open={gameOpen}
        onCancel={() => setGameOpen(false)}
        onOk={() => gameForm.submit()}
        confirmLoading={saveGame.isPending}
        destroyOnClose
      >
        <Form
          form={gameForm}
          layout="vertical"
          onFinish={(v) => saveGame.mutate(v)}
        >
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="platform" label="平台">
            <Input placeholder="如 Steam / 手游" />
          </Form.Item>
          <Form.Item name="icon_url" label="图标 URL">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
