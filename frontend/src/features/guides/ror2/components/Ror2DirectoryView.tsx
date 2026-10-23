import { useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Ror2WikiArticle } from "@/features/guides/ror2/api/ror2Api";
import { apiError } from "@/shared/api/apiError";
import {
  ROR2_HOME_PATH,
  filterRor2Directory,
  ror2ActiveGroup,
  ror2CatalogExpansionRows,
  ror2DirectoryGroups,
  ror2DirectoryListRule,
  ror2ExpansionOrder,
  ror2SectionById,
  ror2SectionGroupOrder,
  sortRor2DirectoryRows,
  ror2SectionRows,
  ror2UnreleasedRows,
  type Ror2DirectoryRow,
  type Ror2PageSectionId,
} from "@/features/guides/ror2/model/ror2Home";
import { isRor2KnownExpansion, ror2ExpansionWikiTitle } from "@/features/guides/ror2/model/ror2Expansion";
import { useRor2Catalog } from "@/features/guides/ror2/hooks/useRor2Catalog";
import { Ror2ListDlcMark, Ror2ListMedia } from "./Ror2ListMedia";
import { Ror2ExpansionName } from "./Ror2ExpansionName";
import { Ror2RichText } from "./Ror2RichText";
import { Ror2TextInfo, Ror2TokenText } from "./Ror2TokenText";
import { Ror2WikiStructure } from "./Ror2WikiStructure";
import { ror2ResolvedText } from "@/features/guides/ror2/model/ror2Text";
import styles from "./Ror2ItemsView.module.css";
import theme from "./ror2Theme.module.css";

export function Ror2DirectoryView({ section }: { section: Ror2PageSectionId }) {
  const spec = ror2SectionById(section);
  const listRule = ror2DirectoryListRule(section);
  const catalog = useRor2Catalog();
  const [params, setParams] = useSearchParams();
  const expansionOrder = useMemo(
    () => (catalog.data ? ror2ExpansionOrder(ror2CatalogExpansionRows(catalog.data)) : []),
    [catalog.data],
  );
  const rows = useMemo(() => {
    if (!catalog.data || !spec) return [];
    const sourceRows = section === "unreleased" ? ror2UnreleasedRows(catalog.data) : ror2SectionRows(section, catalog.data);
    return sortRor2DirectoryRows(section, sourceRows, expansionOrder);
  }, [catalog.data, expansionOrder, section, spec]);
  const groups = useMemo(
    () => ror2DirectoryGroups(rows, spec ? ror2SectionGroupOrder(section) : []),
    [rows, section, spec],
  );
  const cat = ror2ActiveGroup(params.get("cat"), rows);
  const query = params.get("q") ?? "";
  const visible = useMemo(() => filterRor2Directory(rows, query, cat), [rows, query, cat]);
  const visibleGroups = useMemo(
    () => (cat === "all" ? ror2DirectoryGroups(visible, spec ? ror2SectionGroupOrder(section) : []) : [{ id: cat, label: "", rows: visible }]),
    [cat, section, spec, visible],
  );

  const setCat = (next: string) => {
    const nextParams = new URLSearchParams(params);
    if (!next || next === "all") nextParams.delete("cat");
    else nextParams.set("cat", next);
    setParams(nextParams, { replace: true });
  };

  const setQuery = (next: string) => {
    const nextParams = new URLSearchParams(params);
    if (next) nextParams.set("q", next);
    else nextParams.delete("q");
    setParams(nextParams, { replace: true });
  };

  if (!spec) return null;

  return (
    <div className={styles.page}>
      <p className={styles.crumb}>
        <Link to={ROR2_HOME_PATH}>雨中冒险2</Link>
        <span aria-hidden> / </span>
        {spec.label}
      </p>
      <h1 className={styles.title}>{spec.label}</h1>
      {catalog.data ? (
        <Ror2WikiStructure
          articles={catalog.data.wiki_articles ?? []}
          articleIds={listRule.wikiArticleIds ?? []}
        />
      ) : null}
      {catalog.isPending ? <p className={styles.status}>正在读取图鉴</p> : null}
      {catalog.isError ? (
        <div className={styles.status}>
          <p>{apiError(catalog.error, "图鉴暂时拉不下来，请稍后再试")}</p>
          <div className={styles.retry}>
            <button type="button" className={theme.wikiBtn} onClick={() => void catalog.refetch()}>
              重试
            </button>
          </div>
        </div>
      ) : null}
      {catalog.data ? (
        <div className={styles.layout}>
          <aside className={styles.sidebar}>
            <nav className={styles.sideNav} aria-label={spec.label}>
              <div className={styles.catList}>
                <CatButton label="全部" count={rows.length} pressed={cat === "all"} onSelect={() => setCat("all")} />
                {groups.map((group) => {
                  const expansionId = group.id || "base";
                  const isExpansion = expansionId === "base" || isRor2KnownExpansion(expansionId);
                  const wikiTitle = isExpansion
                    ? ror2ExpansionWikiTitle(catalog.data?.wiki_articles, expansionId)
                    : undefined;
                  const label = isExpansion ? (
                    <Ror2ExpansionName
                      id={expansionId}
                      fallback={group.label}
                      wikiArticles={catalog.data?.wiki_articles}
                      showInfo={false}
                    />
                  ) : (
                    group.label
                  );
                  const button = (
                    <CatButton
                      label={label}
                      count={group.rows.length}
                      pressed={cat === group.id}
                      onSelect={() => setCat(group.id)}
                    />
                  );
                  return wikiTitle?.token ? (
                    <span key={group.id || "base"} className={styles.tokenFilter}>
                      {button}
                      <Ror2TextInfo value={wikiTitle} />
                    </span>
                  ) : (
                    <span key={group.id || "base"}>{button}</span>
                  );
                })}
              </div>
            </nav>
          </aside>
          <div className={styles.main}>
            <div className={styles.toolbar}>
              <p className={styles.meta}>
                共 {visible.length} {spec.unit}
              </p>
              <input
                className={styles.search}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索名称、描述"
                aria-label={`搜索${spec.label}`}
                autoComplete="off"
              />
            </div>
            {visible.length === 0 ? (
              <p className={styles.status}>没有匹配的条目</p>
            ) : (
              <div className={styles.groups}>
                {visibleGroups.map((group) => (
                  <section key={group.id || "base"}>
                    {cat === "all" && groups.length > 1 ? (
                      <h2 className={styles.groupHead}>
                        {groupLabel(group.id, group.label, catalog.data?.wiki_articles)}
                      </h2>
                    ) : null}
                    {section === "challenges" ? (
                      <ChallengeTable rows={group.rows} />
                    ) : (
                      <div className={styles.list}>
                        {group.rows.map((row, index) => (
                          <DirectoryCard key={`${group.id}-${index}-${row.name}`} row={row} />
                        ))}
                      </div>
                    )}
                  </section>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function groupLabel(
  id: string,
  label: string,
  wikiArticles: readonly Ror2WikiArticle[] | undefined,
): ReactNode {
  const expansionId = id || "base";
  if (expansionId !== "base" && !isRor2KnownExpansion(expansionId)) return label;
  return (
    <Ror2ExpansionName
      id={expansionId}
      fallback={label}
      wikiArticles={wikiArticles}
    />
  );
}

function CatButton({
  label,
  count,
  pressed,
  onSelect,
}: {
  label: ReactNode;
  count: number;
  pressed: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`${theme.wikiBtn} ${styles.catBtn}${pressed ? ` ${theme.wikiBtnOn}` : ""}`}
      aria-pressed={pressed}
      onClick={onSelect}
    >
      <span className={styles.catLabel}>{label}</span>
      <span className={styles.catCount}>{count}</span>
    </button>
  );
}

const LUNAR_COIN = "https://riskofrain2.wiki.gg/images/LunarCoin.png";

function ChallengeTable({ rows }: { rows: Ror2DirectoryRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>成就</th>
            <th>描述</th>
            <th>解锁</th>
            <th>月币</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${index}-${row.name}`}>
              <th scope="row" className={styles.challenge}>
                <Ror2ListDlcMark expansion={row.expansion} />
                <Ror2TokenText value={row.localizedText?.name ?? ror2ResolvedText(row.name_zh, row.name)} />
              </th>
              <td>
                {row.localizedText?.description || row.description_zh || row.description ? (
                  <Ror2RichText
                    text={row.localizedText?.description ?? ror2ResolvedText(row.description_zh, row.description)}
                  />
                ) : null}
              </td>
              <td>
                <div className={styles.unlocks}>
                  {(row.unlocks ?? []).map((unlock) => (
                    <span key={unlock.name} className={styles.unlock}>
                      <UnlockIcon src={unlock.imageUrl} />
                      <Ror2TokenText
                        value={unlock.localizedText ?? ror2ResolvedText(unlock.name_zh, unlock.name)}
                      />
                    </span>
                  ))}
                </div>
              </td>
              <td>
                <span className={styles.coin}>
                  <UnlockIcon src={LUNAR_COIN} />
                  <span>{row.coins || ""}</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UnlockIcon({ src }: { src: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <img
      src={src}
      alt=""
      width={48}
      height={48}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}

function DirectoryCard({ row }: { row: Ror2DirectoryRow }) {
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  const imageAvailable = Boolean(row.imageUrl && row.imageUrl !== failedImageUrl);
  return (
    <article className={`${theme.frame} ${styles.card} ${styles.faceCard}`}>
      <Ror2ListMedia expansion={row.expansion} imageAvailable={imageAvailable}>
        <EntryFace src={row.imageUrl} onImageError={() => setFailedImageUrl(row.imageUrl ?? null)} />
      </Ror2ListMedia>
      <div>
        <div className={styles.nameRow}>
          <h3 className={styles.name}>
            {!imageAvailable ? <Ror2ListDlcMark expansion={row.expansion} /> : null}
            <Ror2TokenText value={row.localizedText?.name ?? ror2ResolvedText(row.name_zh, row.name)} />
          </h3>
          {row.note ? (
            <span className={styles.expansion}>
              <Ror2TokenText value={row.localizedText?.note ?? row.note} />
            </span>
          ) : null}
        </div>
        {row.quote ? (
          <p className={styles.quote}>
            <Ror2RichText text={row.localizedText?.quote ?? ror2ResolvedText(row.quote_zh, row.quote)} />
          </p>
        ) : null}
        {row.description ? (
          <div className={styles.desc}>
            <Ror2RichText text={row.localizedText?.description ?? ror2ResolvedText(row.description_zh, row.description)} />
          </div>
        ) : null}
      </div>
    </article>
  );
}

function EntryFace({ src, onImageError }: { src?: string | null; onImageError?: () => void }) {
  const [hidden, setHidden] = useState(false);
  if (!src || hidden) return <span className={styles.faceFallback} aria-hidden />;
  return (
    <img
      className={styles.face}
      src={src}
      alt=""
      width={72}
      height={72}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => {
        setHidden(true);
        onImageError?.();
      }}
    />
  );
}
