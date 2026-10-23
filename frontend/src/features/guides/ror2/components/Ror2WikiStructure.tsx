import type { Ror2WikiArticle } from "@/features/guides/ror2/api/ror2Api";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2WikiStructure.module.css";

type Props = {
  articles: Ror2WikiArticle[];
  articleIds: readonly string[];
};

export function Ror2WikiStructure({ articles, articleIds }: Props) {
  const byId = new Map(articles.map((article) => [article.id, article]));
  const selected = articleIds
    .map((id) => byId.get(id))
    .filter((article): article is Ror2WikiArticle => Boolean(article));

  if (selected.length === 0) return null;

  return (
    <details className={styles.structure}>
      <summary className={styles.summary}>Wiki 章节与表头</summary>
      <div className={styles.articles}>
        {selected.map((article) => (
          <article className={styles.article} key={article.id}>
            <h2 className={styles.articleTitle}>
              <Ror2RichText text={article.title} />
            </h2>
            {(article.sections ?? []).map((section) => (
              <section className={styles.section} data-level={section.level} key={section.id}>
                <h3 className={styles.sectionTitle}>
                  <Ror2RichText text={section.title} />
                </h3>
                {(section.tables ?? []).map((table) => (
                  <div className={styles.table} key={table.id}>
                    {table.caption ? (
                      <h4 className={styles.caption}>
                        <Ror2RichText text={table.caption} />
                      </h4>
                    ) : null}
                    {(table.columns ?? []).length > 0 ? (
                      <ul className={styles.columns}>
                        {(table.columns ?? []).map((column) => (
                          <li key={column.id}>
                            <Ror2RichText text={column.label} />
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </section>
            ))}
          </article>
        ))}
      </div>
    </details>
  );
}
