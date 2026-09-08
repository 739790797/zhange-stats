import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  Input,
  List,
  Popconfirm,
  Space,
  Typography,
  message,
} from "antd";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  createArticleComment,
  deleteArticleComment,
  fetchArticleComments,
  type ArticleComment,
} from "@/api/articlesApi";
import { apiError } from "@/lib/apiError";
import { isAdminUser } from "@/lib/isAdminUser";
import { formatBeijing } from "@/lib/time";
import { useAuthStore } from "@/stores/authStore";

export function ArticleComments({ slug }: { slug: string }) {
  const token = Boolean(useAuthStore((s) => s.user));
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  const queryClient = useQueryClient();
  const admin = isAdminUser(user);
  const [draft, setDraft] = useState("");
  const [replyTo, setReplyTo] = useState<number | null>(null);

  const commentsQuery = useQuery({
    queryKey: ["article-comments", slug],
    queryFn: () => fetchArticleComments(slug),
  });

  const postMut = useMutation({
    mutationFn: () =>
      createArticleComment(slug, {
        body: draft,
        parent_id: replyTo,
      }),
    onSuccess: () => {
      setDraft("");
      setReplyTo(null);
      queryClient.invalidateQueries({ queryKey: ["article-comments", slug] });
      message.success("已发表");
    },
    onError: (e) => {
      message.error(apiError(e, "发表失败"));
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => deleteArticleComment(slug, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["article-comments", slug] });
      message.success("已删除");
    },
    onError: (e) => {
      message.error(apiError(e, "删除失败"));
    },
  });

  const comments = commentsQuery.data || [];
  const roots = comments.filter((c) => !c.parent_id);
  const repliesOf = (id: number) => comments.filter((c) => c.parent_id === id);

  const renderItem = (item: ArticleComment, nested = false) => (
    <List.Item
      key={item.id}
      style={nested ? { paddingLeft: 40 } : undefined}
      actions={
        token
          ? [
              <Button
                key="reply"
                type="link"
                size="small"
                onClick={() => setReplyTo(item.parent_id ?? item.id)}
              >
                回复
              </Button>,
              admin ? (
                <Popconfirm
                  key="del"
                  title="删除这条评论？"
                  onConfirm={() => delMut.mutate(item.id)}
                >
                  <Button type="link" size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              ) : null,
            ].filter(Boolean)
          : undefined
      }
    >
      <List.Item.Meta
        avatar={
          <Avatar src={item.author.avatar_url || undefined}>
            {item.author.display_name?.[0] || "?"}
          </Avatar>
        }
        title={
          <Space>
            <span>{item.author.display_name}</span>
            <Typography.Text type="secondary" style={{ fontWeight: 400, fontSize: 12 }}>
              {formatBeijing(item.created_at, "YYYY-MM-DD HH:mm")}
            </Typography.Text>
          </Space>
        }
        description={
          <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
            {item.body}
          </Typography.Paragraph>
        }
      />
    </List.Item>
  );

  return (
    <div>
      <Typography.Title level={4}>评论</Typography.Title>
      <List
        loading={commentsQuery.isLoading}
        locale={{ emptyText: "还没有评论" }}
        dataSource={roots.flatMap((root) => [root, ...repliesOf(root.id)])}
        renderItem={(item) => renderItem(item, Boolean(item.parent_id))}
      />
      {token ? (
        <div style={{ marginTop: 16 }}>
          {replyTo ? (
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
              回复评论 #{replyTo}{" "}
              <Button type="link" size="small" onClick={() => setReplyTo(null)}>
                取消
              </Button>
            </Typography.Text>
          ) : null}
          <Input.TextArea
            rows={4}
            maxLength={2000}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="写一条评论"
          />
          <Button
            type="primary"
            style={{ marginTop: 8 }}
            loading={postMut.isPending}
            onClick={() => postMut.mutate()}
            disabled={!draft.trim()}
          >
            发表
          </Button>
        </div>
      ) : (
        <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
          <Link to="/login" state={{ from: location }}>
            登录
          </Link>
          后可以评论
        </Typography.Paragraph>
      )}
    </div>
  );
}
