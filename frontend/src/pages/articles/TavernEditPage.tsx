import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Result,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Upload,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  createArticle,
  createArticleTag,
  fetchAdminArticle,
  fetchArticleCapabilities,
  fetchArticleCategories,
  fetchArticleTags,
  fetchArticleVersion,
  fetchArticleVersions,
  patchArticle,
  restoreArticleVersion,
  uploadArticleAsset,
  type ArticleVersionListItem,
} from "@/api/articlesApi";
import { ArticleBody } from "@/components/articles/ArticleBody";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import { formatBeijing } from "@/lib/time";
import { TAVERN_PATH, tavernEditPath } from "@/lib/tavernNav";

type FormValues = {
  title: string;
  slug?: string;
  summary?: string;
  body: string;
  body_format: "markdown" | "html";
  status: "draft" | "published";
  category_ids: number[];
  tag_ids: number[];
  cover_url?: string;
};

export default function TavernEditPage() {
  const { articleId } = useParams();
  const isNew = !articleId || articleId === "new";
  const id = isNew ? null : Number(articleId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<FormValues>();
  const body = Form.useWatch("body", form) || "";
  const bodyFormat = Form.useWatch("body_format", form) || "markdown";
  const [previewId, setPreviewId] = useState<number | null>(null);

  const capQuery = useQuery({
    queryKey: ["article-capabilities"],
    queryFn: fetchArticleCapabilities,
  });
  const detailQuery = useQuery({
    queryKey: ["article-editor", id],
    queryFn: () => fetchAdminArticle(id as number),
    enabled: id != null && !Number.isNaN(id),
  });
  const versionsQuery = useQuery({
    queryKey: ["article-versions", id],
    queryFn: () => fetchArticleVersions(id as number),
    enabled: id != null && !Number.isNaN(id),
  });
  const previewQuery = useQuery({
    queryKey: ["article-version", id, previewId],
    queryFn: () => fetchArticleVersion(id as number, previewId as number),
    enabled: id != null && previewId != null,
  });
  const catsQuery = useQuery({
    queryKey: ["article-categories"],
    queryFn: fetchArticleCategories,
  });
  const tagsQuery = useQuery({
    queryKey: ["article-tags"],
    queryFn: fetchArticleTags,
  });

  const saveMut = useMutation({
    mutationFn: async (values: FormValues) => {
      const payload = {
        title: values.title,
        slug: values.slug || null,
        summary: values.summary || "",
        body: values.body || "",
        body_format: values.body_format,
        status: values.status,
        category_ids: values.category_ids || [],
        tag_ids: values.tag_ids || [],
        cover_url: values.cover_url || null,
      };
      if (id == null) {
        return createArticle(payload);
      }
      return patchArticle(id, payload);
    },
    onSuccess: (saved) => {
      message.success("已保存");
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["articles-mine"] });
      queryClient.invalidateQueries({ queryKey: ["articles-admin"] });
      queryClient.invalidateQueries({ queryKey: ["article-versions", saved.id] });
      queryClient.invalidateQueries({ queryKey: ["article-editor", saved.id] });
      if (id == null) {
        navigate(tavernEditPath(saved.id), { replace: true });
      }
    },
    onError: (e) => message.error(apiError(e, "保存失败")),
  });

  const restoreMut = useMutation({
    mutationFn: (versionId: number) => restoreArticleVersion(id as number, versionId),
    onSuccess: () => {
      message.success("已恢复该版本");
      queryClient.invalidateQueries({ queryKey: ["article-editor", id] });
      queryClient.invalidateQueries({ queryKey: ["article-versions", id] });
      queryClient.invalidateQueries({ queryKey: ["articles-mine"] });
      queryClient.invalidateQueries({ queryKey: ["articles-admin"] });
    },
    onError: (e) => message.error(apiError(e, "恢复失败")),
  });

  const initial = detailQuery.data;
  const deleted = initial?.status === "deleted";
  const canAdmin = Boolean(capQuery.data?.can_admin);
  const canWrite = Boolean(capQuery.data?.can_write);

  useEffect(() => {
    if (!initial) return;
    form.setFieldsValue({
      title: initial.title,
      slug: initial.slug,
      summary: initial.summary || "",
      body: initial.body || "",
      body_format: (initial.body_format as FormValues["body_format"]) || "markdown",
      status:
        initial.status === "published"
          ? "published"
          : "draft",
      category_ids: (initial.categories || []).map((c) => c.id),
      tag_ids: (initial.tags || []).map((t) => t.id),
      cover_url: initial.cover_url || "",
    });
  }, [form, initial]);

  if (!isNew && detailQuery.isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin />
      </div>
    );
  }

  if (capQuery.isSuccess && !canWrite) {
    return (
      <Result
        status="403"
        title="没有发文权限"
        extra={
          <Button onClick={() => navigate(TAVERN_PATH)}>返回酒馆</Button>
        }
      />
    );
  }

  const versionColumns = [
    { title: "版本", dataIndex: "version_no", width: 80 },
    { title: "标题", dataIndex: "title", ellipsis: true },
    {
      title: "时间",
      width: 170,
      render: (_: unknown, row: ArticleVersionListItem) =>
        formatBeijing(row.created_at, "YYYY-MM-DD HH:mm"),
    },
    {
      title: "说明",
      dataIndex: "note",
      ellipsis: true,
    },
    {
      title: "操作",
      width: 160,
      render: (_: unknown, row: ArticleVersionListItem) => (
        <Space>
          <Button type="link" size="small" onClick={() => setPreviewId(row.id)}>
            预览
          </Button>
          <Popconfirm
            title="恢复到此版本？当前正文会被替换。"
            onConfirm={() => restoreMut.mutate(row.id)}
          >
            <Button type="link" size="small">
              恢复
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title={isNew ? "发布文章" : deleted ? "已删除的文章" : "编辑文章"} />
      {deleted ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="文章已删除，可从下面的版本恢复。恢复后会变成草稿。"
        />
      ) : (
        <Form<FormValues>
          form={form}
          layout="vertical"
          initialValues={{
            title: "",
            slug: "",
            summary: "",
            body: "",
            body_format: "markdown",
            status: "draft",
            category_ids: [],
            tag_ids: [],
            cover_url: "",
          }}
          onFinish={(values) => saveMut.mutate(values)}
        >
          <Form.Item name="title" label="标题" rules={[{ required: true, message: "请填写标题" }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="slug" label="短链">
            <Input placeholder="留空则按标题生成（仅英文数字）" maxLength={191} />
          </Form.Item>
          <Form.Item name="summary" label="摘要">
            <Input.TextArea rows={2} maxLength={512} />
          </Form.Item>
          <Form.Item name="cover_url" label="封面图 URL">
            <Input placeholder="/uploads/articles/..." />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select
              options={[
                { value: "draft", label: "草稿" },
                { value: "published", label: "发布" },
              ]}
            />
          </Form.Item>
          <Form.Item name="body_format" label="正文格式">
            <Select
              options={[
                { value: "markdown", label: "Markdown" },
                { value: "html", label: "HTML" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="category_ids"
            label="分类"
            extra="可多选。分类由管理员在酒馆管理里维护。"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择分类"
              options={(catsQuery.data || []).map((c) => ({
                value: c.id,
                label: c.name,
              }))}
            />
          </Form.Item>
          <Form.Item name="tag_ids" label="标签">
            <Select
              mode="multiple"
              options={(tagsQuery.data || []).map((t) => ({ value: t.id, label: t.name }))}
              dropdownRender={
                canAdmin
                  ? (menu) => (
                      <>
                        {menu}
                        <QuickAdd
                          placeholder="新标签名"
                          onAdd={async (name) => {
                            await createArticleTag({ name });
                            tagsQuery.refetch();
                          }}
                        />
                      </>
                    )
                  : undefined
              }
            />
          </Form.Item>
          <Form.Item label="插入图片">
            <Upload
              accept="image/*"
              showUploadList={false}
              customRequest={async ({ file, onSuccess, onError }) => {
                try {
                  const res = await uploadArticleAsset(file as File);
                  const cur = form.getFieldValue("body") || "";
                  form.setFieldValue("body", `${cur}\n\n![](${res.url})\n`);
                  onSuccess?.(res);
                  message.success("已插入图片");
                } catch (e) {
                  onError?.(e as Error);
                  message.error(apiError(e, "上传失败"));
                }
              }}
            >
              <Button size="small">上传并插入 Markdown</Button>
            </Upload>
          </Form.Item>
          <Form.Item name="body" label="正文">
            <Input.TextArea rows={16} />
          </Form.Item>
          <Tabs
            items={[
              {
                key: "preview",
                label: "预览",
                children: <ArticleBody body={body} format={bodyFormat} />,
              },
            ]}
          />
          <Space style={{ marginTop: 16 }}>
            <Button type="primary" htmlType="submit" loading={saveMut.isPending}>
              保存
            </Button>
            <Button onClick={() => navigate(TAVERN_PATH)}>取消</Button>
          </Space>
        </Form>
      )}
      {id != null ? (
        <div style={{ marginTop: 32 }}>
          <PageHeader title="版本" subtitle="可以把正文恢复到某一版；已删除的文章恢复后会变成草稿。" />
          <Table
            rowKey="id"
            loading={versionsQuery.isLoading}
            columns={versionColumns}
            dataSource={versionsQuery.data || []}
            pagination={false}
            size="small"
          />
        </div>
      ) : null}
      <Modal
        title={previewQuery.data ? `第 ${previewQuery.data.version_no} 版` : "版本预览"}
        open={previewId != null}
        onCancel={() => setPreviewId(null)}
        footer={null}
        width="min(840px, calc(100vw - 24px))"
      >
        {previewQuery.isLoading ? (
          <Spin />
        ) : previewQuery.data ? (
          <ArticleBody
            body={previewQuery.data.body}
            format={previewQuery.data.body_format}
          />
        ) : null}
      </Modal>
    </div>
  );
}

function QuickAdd({
  placeholder,
  onAdd,
}: {
  placeholder: string;
  onAdd: (name: string) => Promise<void>;
}) {
  return (
    <div style={{ padding: 8 }}>
      <Input.Search
        placeholder={placeholder}
        enterButton="添加"
        onSearch={async (name) => {
          const trimmed = name.trim();
          if (!trimmed) return;
          try {
            await onAdd(trimmed);
            message.success("已添加");
          } catch (e) {
            message.error(apiError(e, "添加失败"));
          }
        }}
      />
    </div>
  );
}
