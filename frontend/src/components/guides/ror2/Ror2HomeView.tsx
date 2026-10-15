import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Ror2Item } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import { ror2RarityAccent } from "@/lib/ror2Catalog";
import {
  ROR2_HOME_TILES,
  ROR2_SIDE_LINKS,
  filterRor2Items,
  ror2CatalogItems,
  ror2ItemsHref,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2ItemIcon } from "./Ror2ItemIcon";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2HomeView.module.css";
import theme from "./ror2Theme.module.css";

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 14 14" fill="none" aria-hidden>
      <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.4" />
      <line x1="9.5" y1="9.5" x2="13" y2="13" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

export function Ror2HomeView() {
  const catalog = useRor2Catalog();
  const [searchParams, setSearchParams] = useSearchParams();
  const committed = searchParams.get("q") ?? "";
  const [draft, setDraft] = useState(committed);
  const items = useMemo(
    () => (catalog.data ? ror2CatalogItems(catalog.data) : []),
    [catalog.data],
  );
  const hits = useMemo(
    () => filterRor2Items(items, draft, "all"),
    [items, draft],
  );
  const searching = draft.trim().length > 0;

  useEffect(() => {
    setDraft(committed);
  }, [committed]);

  const commitSearch = (value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value.trim()) params.set("q", value);
    else params.delete("q");
    setSearchParams(params, { replace: true });
  };

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <h1 className={styles.title}>雨中冒险2</h1>
        <p className={styles.subtitle}>RISK OF RAIN 2</p>
        <form
          className={styles.search}
          role="search"
          onSubmit={(event) => {
            event.preventDefault();
            commitSearch(draft);
          }}
        >
          <span aria-hidden>
            <SearchIcon />
          </span>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="搜索物品"
            aria-label="搜索物品"
            autoComplete="off"
            enterKeyHint="search"
          />
          {draft ? (
            <button
              type="button"
              className={styles.clear}
              aria-label="清空搜索"
              onClick={() => {
                setDraft("");
                commitSearch("");
              }}
            >
              ×
            </button>
          ) : null}
        </form>
      </section>

      <div className={styles.layout}>
        <div className={styles.main}>
          <section className={`${theme.frame} ${styles.panel}`}>
            <h2 className={styles.heading}>{searching ? "搜索结果" : "内容"}</h2>
            {searching ? (
              <SearchResults
                pending={catalog.isPending}
                error={catalog.isError ? apiError(catalog.error, "图鉴暂时拉不下来，请稍后再试") : ""}
                onRetry={() => void catalog.refetch()}
                hits={hits}
              />
            ) : (
              <div className={styles.grid}>
                {ROR2_HOME_TILES.map((tile) =>
                  tile.href ? (
                    <Link
                      key={tile.id}
                      to={ror2ItemsHref("", draft)}
                      className={`${theme.wikiBtn} ${styles.tile}`}
                    >
                      {tile.label}
                    </Link>
                  ) : (
                    <span
                      key={tile.id}
                      className={`${theme.wikiBtn} ${theme.wikiBtnQuiet} ${styles.tile}`}
                      aria-disabled="true"
                      title="尚未开放"
                    >
                      {tile.label}
                    </span>
                  ),
                )}
              </div>
            )}
          </section>
        </div>
        <Ror2SideRail />
      </div>
    </div>
  );
}

function SearchResults({
  pending,
  error,
  onRetry,
  hits,
}: {
  pending: boolean;
  error: string;
  onRetry: () => void;
  hits: Ror2Item[];
}) {
  if (pending) return <p className={styles.note}>正在读取图鉴</p>;
  if (error) {
    return (
      <>
        <p className={styles.empty}>{error}</p>
        <div className={styles.retry}>
          <button type="button" className={theme.wikiBtn} onClick={onRetry}>
            重试
          </button>
        </div>
      </>
    );
  }
  if (!hits.length) return <p className={styles.empty}>没有匹配的物品</p>;
  return (
    <div className={styles.results}>
      {hits.map((item) => (
        <Link
          key={`${item.rarity}-${item.name}`}
          to={ror2ItemsHref(item.rarity, item.name)}
          className={`${theme.frame} ${styles.result}`}
        >
          <Ror2ItemIcon src={item.image_url} accent={ror2RarityAccent(item.rarity)} />
          <span className={styles.resultBody}>
            <span className={styles.resultName}>{item.name}</span>
            {item.rarity ? <span className={styles.resultMeta}>{item.rarity}</span> : null}
            {item.description ? (
              <Ror2RichText className={styles.excerpt} text={item.description} />
            ) : null}
          </span>
        </Link>
      ))}
    </div>
  );
}

function Ror2SideRail() {
  return (
    <aside className={`${theme.frame} ${styles.panel} ${styles.rail}`} aria-label="杂项">
      <h2 className={styles.heading}>杂项</h2>
      <nav className={styles.railList}>
        {ROR2_SIDE_LINKS.map((item) => (
          <span
            key={item.id}
            className={`${theme.wikiBtn} ${theme.wikiBtnQuiet} ${styles.railBtn}`}
            aria-disabled="true"
            title="尚未开放"
          >
            {item.label}
          </span>
        ))}
      </nav>
    </aside>
  );
}
