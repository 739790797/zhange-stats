import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageOutlined } from "@ant-design/icons";
import {
  Button,
  Input,
  Pagination,
  Popconfirm,
  Space,
  Spin,
  Tag,
  message,
} from "antd";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  deleteArticle,
  fetchArticleCategories,
  fetchArticleCapabilities,
  fetchArticles,
  fetchMineArticles,
} from "@/api/articlesApi";
import { FeatureUnavailablePage } from "@/components/FeatureUnavailablePage";
import { ArticleVersionsModal } from "@/components/articles/ArticleVersionsModal";
import styles from "@/components/articles/TavernHome.module.css";
import { apiError, isApiForbidden } from "@/lib/apiError";
import {
  articleCategoryChipColor,
  articleCategoryChipHex,
} from "@/lib/articleCategory";
import {
  articleStatusColor,
  articleStatusLabel,
} from "@/lib/articleStatus";
import {
  TAVERN_FEATURE_ID,
  TAVERN_WRITE_PATH,
  tavernArticlePath,
  tavernEditPath,
} from "@/lib/tavernNav";
import { formatBeijing } from "@/lib/time";
import { useDocumentTitle } from "@/lib/documentTitle";
import { useAuthStore } from "@/stores/authStore";

export default function TavernListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  useDocumentTitle("战鸽酒馆");
  const token = Boolean(useAuthStore((s) => s.user));
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") || "1") || 1;
  const category = params.get("category") || undefined;
  const qParam = (params.get("q") || "").trim();
  const mine = params.get("mine") === "1";
  const [qDraft, setQDraft] = useState(qParam);
  const [versionRow, setVersionRow] = useState<{
    id: number;
    title: string;
  } | null>(null);

  useEffect(() => {
    setQDraft(qParam);
  }, [qParam]);

  const capQuery = useQuery({
    queryKey: ["article-capabilities"],
    queryFn: fetchArticleCapabilities,
    enabled: Boolean(token),
  });
  const canWrite = Boolean(capQuery.data?.can_write);
  const mineView = Boolean(canWrite && mine);

  const catsQuery = useQuery({
    queryKey: ["article-categories"],
    queryFn: fetchArticleCategories,
  });
  const listQuery = useQuery({
    queryKey: ["articles", { page, category, q: qParam }],
    queryFn: () =>
      fetchArticles({
        page,
        page_size: 10,
        category,
        q: qParam || undefined,
      }),
    enabled: !mineView,
  });
  const mineQuery = useQuery({
    queryKey: ["articles-mine"],
    queryFn: () => fetchMineArticles({ page: 1, page_size: 50 }),
    enabled: canWrite && mine,
  });
  const delMut = useMutation({
    mutationFn: deleteArticle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles-mine"] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      message.success("已删除");
    },
    onError: (e) => message.error(apiError(e, "删除失败")),
  });

  if (isApiForbidden(listQuery.error) || isApiForbidden(catsQuery.error)) {
    return (
      <FeatureUnavailablePage
        featureId={TAVERN_FEATURE_ID}
        loadError={false}
      />
    );
  }

  const patchParams = (mutate: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(params);
    mutate(next);
    setParams(next);
  };

  const setCategory = (slug?: string) => {
    patchParams((next) => {
      next.delete("mine");
      next.delete("page");
      if (slug) next.set("category", slug);
      else next.delete("category");
    });
  };

  const setSearch = (value: string) => {
    const needle = value.trim();
    patchParams((next) => {
      next.delete("mine");
      next.delete("page");
      if (needle) next.set("q", needle);
      else next.delete("q");
    });
  };

  const showMine = (on: boolean) => {
    patchParams((next) => {
      next.delete("page");
      next.delete("category");
      next.delete("q");
      if (on) next.set("mine", "1");
      else next.delete("mine");
    });
  };

  const data = listQuery.data;
  const cats = catsQuery.data || [];
  const items = data?.items || [];

  return (
    <div className={styles.page}>
      {canWrite ? (
        <header className={styles.topbar}>
          <div className={styles.topbarActions}>
            <Button onClick={() => showMine(!mineView)}>我的文章</Button>
            <Button type="primary" onClick={() => navigate(TAVERN_WRITE_PATH)}>
              发布文章
            </Button>
          </div>
        </header>
      ) : null}

      {mineView ? (
        mineQuery.isLoading ? (
          <div className={`${styles.emptyCard} ${styles.mineList}`}>
            <div style={{ textAlign: "center", padding: 48 }}>
              <Spin />
            </div>
          </div>
        ) : (mineQuery.data?.items || []).length === 0 ? (
          <div className={`${styles.emptyCard} ${styles.mineList}`}>
            <p className={styles.empty}>还没有自己的稿。点右上角发布一篇即可。</p>
          </div>
        ) : (
          <div className={styles.mineList}>
            {(mineQuery.data?.items || []).map((row) => (
              <div key={row.id} className={styles.mineItem}>
                <div>
                  <h2 className={styles.mineTitle}>{row.title}</h2>
                  <div className={styles.mineMeta}>
                    <Tag color={articleStatusColor(row.status)}>
                      {articleStatusLabel(row.status)}
                    </Tag>
                    {formatBeijing(
                      row.updated_at || row.created_at,
                      "YYYY-MM-DD HH:mm",
                    )}
                  </div>
                </div>
                <Space>
                  <Button
                    type="link"
                    size="small"
                    onClick={() => navigate(tavernEditPath(row.id))}
                  >
                    编辑
                  </Button>
                  <Button
                    type="link"
                    size="small"
                    onClick={() =>
                      setVersionRow({ id: row.id, title: row.title })
                    }
                  >
                    版本
                  </Button>
                  {row.status === "published" ? (
                    <Link to={tavernArticlePath(row.slug)}>
                      <Button type="link" size="small">
                        阅读
                      </Button>
                    </Link>
                  ) : null}
                  <Popconfirm
                    title="删除这篇文章？删除后无法恢复。"
                    onConfirm={() => delMut.mutate(row.id)}
                  >
                    <Button type="link" size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              </div>
            ))}
          </div>
        )
      ) : (
        <>
          <section className={styles.hero} aria-label="战鸽酒馆">
            <h1 className={styles.heroTitle}>战鸽酒馆</h1>
            <Input.Search
              className={styles.heroSearch}
              size="large"
              placeholder="输入文章标题"
              allowClear
              enterButton="搜索"
              value={qDraft}
              onChange={(e) => setQDraft(e.target.value)}
              onSearch={(value) => setSearch(value)}
            />
          </section>

          <div className={styles.board}>
            <div className={styles.feed}>
              {listQuery.isLoading ? (
                <div className={styles.emptyCard}>
                  <div style={{ textAlign: "center", padding: 48 }}>
                    <Spin />
                  </div>
                </div>
              ) : listQuery.isError ? (
                <div className={styles.emptyCard}>
                  <p className={styles.empty}>
                    {apiError(listQuery.error, "无法加载文章")}
                  </p>
                </div>
              ) : !items.length ? (
                <div className={styles.emptyCard}>
                  <p className={styles.empty}>
                    {qParam || category
                      ? "没有符合筛选的文章。"
                      : "大厅里暂时还没有已发布的文章。"}
                  </p>
                </div>
              ) : (
                items.map((item) => {
                  const cat = (item.categories || [])[0];
                  return (
                    <article key={item.id} className={styles.card}>
                      <div className={styles.cardTitleRow}>
                        {cat ? (
                          <Tag
                            className={styles.cardCat}
                            color={articleCategoryChipColor(cat)}
                            onClick={() => setCategory(cat.slug)}
                          >
                            {cat.name}
                          </Tag>
                        ) : null}
                        <h2 className={styles.cardTitle}>
                          <Link
                            className={styles.cardLink}
                            to={tavernArticlePath(item.slug)}
                          >
                            {item.title}
                          </Link>
                        </h2>
                      </div>
                      {item.summary ? (
                        <p className={styles.excerpt}>{item.summary}</p>
                      ) : null}
                      <div className={styles.stats}>
                        <span className={styles.stat}>
                          <MessageOutlined />
                          {item.comment_count ?? 0}
                        </span>
                      </div>
                    </article>
                  );
                })
              )}
              {(data?.total || 0) > (data?.page_size || 10) ? (
                <div className={styles.pager}>
                  <Pagination
                    current={data?.page}
                    pageSize={data?.page_size}
                    total={data?.total}
                    onChange={(nextPage) => {
                      patchParams((next) => {
                        next.set("page", String(nextPage));
                      });
                    }}
                  />
                </div>
              ) : null}
            </div>

            <aside className={styles.aside}>
              <section className={styles.widget}>
                <div className={styles.widgetHead}>分类</div>
                <div className={styles.catList}>
                  <Button
                    type="text"
                    block
                    className={`${styles.catItem} ${!category ? styles.catItemActive : ""}`}
                    onClick={() => setCategory()}
                  >
                    全部
                  </Button>
                  {cats.map((cat) => {
                    const hex = articleCategoryChipHex(cat);
                    return (
                      <Button
                        key={cat.id}
                        type="text"
                        block
                        className={`${styles.catItem} ${category === cat.slug ? styles.catItemActive : ""}`}
                        onClick={() => setCategory(cat.slug)}
                      >
                        <span
                          className={styles.catDot}
                          style={hex ? { background: hex } : undefined}
                        />
                        {cat.name}
                      </Button>
                    );
                  })}
                </div>
              </section>
            </aside>
          </div>
        </>
      )}
      <ArticleVersionsModal
        articleId={versionRow?.id ?? null}
        title={versionRow?.title}
        open={versionRow != null}
        onClose={() => setVersionRow(null)}
      />
    </div>
  );
}
