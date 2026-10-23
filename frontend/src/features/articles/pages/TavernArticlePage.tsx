import { useQuery } from "@tanstack/react-query";
import { Button, Spin, Tag } from "antd";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { fetchArticle, fetchArticleCapabilities } from "@/features/articles/api/articlesApi";
import { ArticleBody } from "@/features/articles/components/ArticleBody";
import { ArticleComments } from "@/features/articles/components/ArticleComments";
import { FeatureUnavailableResult } from "@/shared/ui/FeatureUnavailableResult";
import "@/features/articles/components/articleRichtext.css";
import styles from "@/features/articles/components/TavernReading.module.css";
import { apiError, isApiForbidden } from "@/shared/api/apiError";
import { articleCategoryChipColor } from "@/features/articles/model/articleCategory";
import {
  TAVERN_ADMIN_PATH,  TAVERN_PATH,
  TAVERN_WRITE_PATH,
  tavernEditPath,
} from "@/features/articles/model/tavernNav";
import { formatBeijing } from "@/shared/lib/time";
import { useDocumentTitle } from "@/shared/hooks/documentTitle";
import { useAuthStore } from "@/features/auth/model/authStore";

export default function TavernArticlePage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const token = Boolean(useAuthStore((s) => s.user));
  const user = useAuthStore((s) => s.user);
  const reserved =
    slug === "admin" || slug === "manage" || slug === "write" || slug === "new";
  const query = useQuery({
    queryKey: ["article", slug],
    queryFn: () => fetchArticle(slug),
    enabled: Boolean(slug) && !reserved,
  });
  const capQuery = useQuery({
    queryKey: ["article-capabilities"],
    queryFn: fetchArticleCapabilities,
    enabled: Boolean(token) && !reserved,
  });
  useDocumentTitle(query.data?.title || "战鸽酒馆");

  if (slug === "admin" || slug === "manage") {
    return <Navigate to={TAVERN_ADMIN_PATH} replace />;
  }
  if (slug === "write" || slug === "new") {
    return <Navigate to={TAVERN_WRITE_PATH} replace />;
  }

  if (isApiForbidden(query.error)) {
    return <FeatureUnavailableResult featureName="战鸽酒馆" />;
  }
  if (query.isLoading) {
    return (
      <div className={styles.loading}>
        <Spin />
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <p className={styles.empty}>
        {apiError(query.error, "文章不存在或无法加载")}
      </p>
    );
  }

  const article = query.data;
  const canEdit =
    Boolean(capQuery.data?.can_admin) ||
    (Boolean(capQuery.data?.can_write) &&
      article.author.user_id != null &&
      article.author.user_id === user?.id);

  return (
    <article className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.col}>
          <div className={styles.heroNav}>
            <Link className={styles.back} to={TAVERN_PATH}>
              战鸽酒馆
            </Link>
            {canEdit ? (
              <Button
                size="small"
                onClick={() => navigate(tavernEditPath(article.id))}
              >
                编辑
              </Button>
            ) : null}
          </div>
          <h1 className={styles.articleTitle}>{article.title}</h1>
          <p className={styles.articleMeta}>
            {article.author.display_name}
            {article.published_at
              ? ` · ${formatBeijing(article.published_at, "YYYY年M月D日")}`
              : ""}
          </p>
          {(article.categories || []).length || (article.tags || []).length ? (
            <div className={styles.tags}>
              {(article.categories || []).map((cat) => (
                <Link
                  key={cat.id}
                  to={`${TAVERN_PATH}?category=${encodeURIComponent(cat.slug)}`}
                >
                  <Tag color={articleCategoryChipColor(cat)}>{cat.name}</Tag>
                </Link>
              ))}
              {(article.tags || []).map((tag) => (
                <span key={tag.id}>{tag.name}</span>
              ))}
            </div>
          ) : null}
        </div>
      </header>
      <div className={styles.paper}>
        {article.cover_url ? (
          <img className={styles.cover} src={article.cover_url} alt="" />
        ) : null}
        <ArticleBody body={article.body} format={article.body_format} />
        <div className={styles.comments}>
          <ArticleComments slug={article.slug} />
        </div>
      </div>
    </article>
  );
}
