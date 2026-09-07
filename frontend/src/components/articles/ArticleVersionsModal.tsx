import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Modal, Popconfirm, Space, Spin, Table, message } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchArticleVersion,
  fetchArticleVersions,
  restoreArticleVersion,
  type ArticleVersionListItem,
} from "@/api/articlesApi";
import { ArticleBody } from "@/components/articles/ArticleBody";
import { apiError } from "@/lib/apiError";
import { tavernEditPath } from "@/lib/tavernNav";
import { formatBeijing } from "@/lib/time";
import styles from "./TavernHome.module.css";

export function ArticleVersionsModal({
  articleId,
  title,
  open,
  onClose,
}: {
  articleId: number | null;
  title?: string;
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [previewId, setPreviewId] = useState<number | null>(null);

  const versionsQuery = useQuery({
    queryKey: ["article-versions", articleId],
    queryFn: () => fetchArticleVersions(articleId as number),
    enabled: open && articleId != null,
  });
  const previewQuery = useQuery({
    queryKey: ["article-version", articleId, previewId],
    queryFn: () => fetchArticleVersion(articleId as number, previewId as number),
    enabled: open && articleId != null && previewId != null,
  });
  const restoreMut = useMutation({
    mutationFn: (versionId: number) =>
      restoreArticleVersion(articleId as number, versionId),
    onSuccess: (saved) => {
      message.success("已恢复该版本");
      queryClient.setQueryData(["article-editor", saved.id], saved);
      queryClient.invalidateQueries({ queryKey: ["article-versions", saved.id] });
      queryClient.invalidateQueries({ queryKey: ["articles-mine"] });
      queryClient.invalidateQueries({ queryKey: ["articles-admin"] });
      setPreviewId(null);
      onClose();
      navigate(tavernEditPath(saved.id));
    },
    onError: (e) => message.error(apiError(e, "恢复失败")),
  });

  const columns = [
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
    <>
      <Modal
        title={title ? `版本 · ${title}` : "版本"}
        open={open}
        onCancel={() => {
          setPreviewId(null);
          onClose();
        }}
        footer={null}
        destroyOnClose
        width="min(720px, calc(100vw - 24px))"
      >
        <p className={styles.versionsHint}>
          只保留发布时的版本，保存不会记一版。可以把正文恢复到某一发布版。
        </p>
        <Table
          rowKey="id"
          loading={versionsQuery.isLoading}
          columns={columns}
          dataSource={versionsQuery.data || []}
          pagination={false}
          size="small"
          locale={{ emptyText: "还没有发布版本" }}
        />
      </Modal>
      <Modal
        title={
          previewQuery.data
            ? `第 ${previewQuery.data.version_no} 版`
            : "版本预览"
        }
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
    </>
  );
}
