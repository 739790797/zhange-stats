import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Transfer,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  deleteArticle,
  fetchAdminArticles,
  fetchArticleAuthors,
  putArticleAuthors,
  type ArticleListItem,
} from "@/api/articlesApi";
import { fetchUsers } from "@/api/usersApi";
import { PageHeader } from "@/components/PageHeader";
import { TavernCategoryPanel } from "@/components/articles/TavernCategoryPanel";
import { apiError } from "@/lib/apiError";
import {
  articleStatusColor,
  articleStatusLabel,
} from "@/lib/articleStatus";
import { tavernArticlePath, tavernEditPath } from "@/lib/tavernNav";
import { formatBeijing } from "@/lib/time";

export default function TavernAdminPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<string | undefined>();
  const listQuery = useQuery({
    queryKey: ["articles-admin", status],
    queryFn: () =>
      fetchAdminArticles({
        page: 1,
        page_size: 50,
        status,
      }),
  });
  const delMut = useMutation({
    mutationFn: deleteArticle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles-admin"] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      message.success("已删除");
    },
    onError: (e) => message.error(apiError(e, "删除失败")),
  });

  const columns: ColumnsType<ArticleListItem> = [
    { title: "标题", dataIndex: "title", ellipsis: true },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={articleStatusColor(value)}>{articleStatusLabel(value)}</Tag>
      ),
    },
    {
      title: "作者",
      width: 120,
      render: (_, row) => row.author.display_name,
    },
    {
      title: "更新",
      width: 160,
      render: (_, row) =>
        formatBeijing(row.updated_at || row.created_at, "YYYY-MM-DD HH:mm"),
    },
    {
      title: "操作",
      width: 220,
      render: (_, row) => (
        <Space>
          <Button type="link" size="small" onClick={() => navigate(tavernEditPath(row.id))}>
            {row.status === "deleted" ? "版本" : "编辑"}
          </Button>
          {row.status === "published" ? (
            <Link to={tavernArticlePath(row.slug)}>
              <Button type="link" size="small">
                查看
              </Button>
            </Link>
          ) : null}
          {row.status !== "deleted" ? (
            <Popconfirm title="删除这篇文章？" onConfirm={() => delMut.mutate(row.id)}>
              <Button type="link" size="small" danger>
                删除
              </Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="酒馆管理"
        subtitle="分类、作者名单，以及全部文章（含已删除）。"
      />
      <Tabs
        items={[
          {
            key: "articles",
            label: "全部文章",
            children: (
              <>
                <Select
                  allowClear
                  placeholder="全部状态"
                  style={{ width: 160, marginBottom: 16 }}
                  value={status}
                  onChange={(value) => setStatus(value)}
                  options={[
                    { value: "draft", label: "草稿" },
                    { value: "published", label: "已发布" },
                    { value: "deleted", label: "已删除" },
                  ]}
                />
                <Table
                  rowKey="id"
                  loading={listQuery.isLoading}
                  columns={columns}
                  dataSource={listQuery.data?.items || []}
                  pagination={false}
                />
              </>
            ),
          },
          {
            key: "categories",
            label: "分类",
            children: <TavernCategoryPanel />,
          },
          {
            key: "authors",
            label: "作者",
            children: <AuthorPicker />,
          },
        ]}
      />
    </div>
  );
}

function AuthorPicker() {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });
  const authorsQuery = useQuery({
    queryKey: ["article-authors"],
    queryFn: fetchArticleAuthors,
  });
  const [targetKeys, setTargetKeys] = useState<string[]>([]);

  useEffect(() => {
    if (!authorsQuery.data) return;
    setTargetKeys(
      authorsQuery.data
        .map((row) => row.user_id)
        .filter((id): id is number => id != null)
        .map(String),
    );
  }, [authorsQuery.data]);

  const dataSource = useMemo(
    () =>
      (usersQuery.data || []).map((user) => ({
        key: String(user.id),
        title: user.display_name,
        description: user.email || user.username,
      })),
    [usersQuery.data],
  );

  const saveMut = useMutation({
    mutationFn: () =>
      putArticleAuthors({ user_ids: targetKeys.map((key) => Number(key)) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["article-authors"] });
      queryClient.invalidateQueries({ queryKey: ["article-capabilities"] });
      message.success("已保存作者名单");
    },
    onError: (e) => message.error(apiError(e, "保存失败")),
  });

  return (
    <div>
      <Transfer
        dataSource={dataSource}
        titles={["本站用户", "酒馆作者"]}
        targetKeys={targetKeys}
        onChange={(next) => setTargetKeys(next.map(String))}
        render={(item) => item.title}
        showSearch
        filterOption={(input, item) =>
          `${item.title} ${item.description || ""}`
            .toLowerCase()
            .includes(input.toLowerCase())
        }
        listStyle={{ width: 280, height: 420 }}
      />
      <Button
        type="primary"
        style={{ marginTop: 16 }}
        loading={saveMut.isPending}
        onClick={() => saveMut.mutate()}
      >
        保存作者
      </Button>
    </div>
  );
}
