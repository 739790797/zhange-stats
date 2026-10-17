import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiError } from "@/lib/apiError";
import {
  ROR2_HOME_PATH,
  filterRor2Directory,
  ror2ActiveGroup,
  ror2DirectoryGroups,
  ror2SectionById,
  ror2SectionGroupOrder,
  ror2SectionRows,
  ror2UnreleasedRows,
  type Ror2DirectoryRow,
  type Ror2PageSectionId,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import { useRor2TermText } from "./Ror2TermScope";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2ItemsView.module.css";
import theme from "./ror2Theme.module.css";

export function Ror2DirectoryView({ section }: { section: Ror2PageSectionId }) {
  const spec = ror2SectionById(section);
  const catalog = useRor2Catalog();
  const [params, setParams] = useSearchParams();
  const rows = useMemo(() => {
    if (!catalog.data || !spec) return [];
    if (section === "unreleased") return ror2UnreleasedRows(catalog.data);
    return ror2SectionRows(section, catalog.data);
  }, [catalog.data, section, spec]);
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
                {groups.map((group) => (
                  <CatButton
                    key={group.id || "base"}
                    label={group.label}
                    count={group.rows.length}
                    pressed={cat === group.id}
                    onSelect={() => setCat(group.id)}
                  />
                ))}
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
                    {cat === "all" && groups.length > 1 ? <h2 className={styles.groupHead}>{group.label}</h2> : null}
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

function CatButton({
  label,
  count,
  pressed,
  onSelect,
}: {
  label: string;
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
  const termText = useRor2TermText();
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
                {row.dlcIconUrl ? <Ror2ExpansionIcon src={row.dlcIconUrl} label={row.dlcLabel} /> : null}
                {row.name_zh || termText(row.name)}
              </th>
              <td>{row.description ? <Ror2RichText text={row.description} /> : null}</td>
              <td>
                <div className={styles.unlocks}>
                  {(row.unlocks ?? []).map((unlock) => (
                    <span key={unlock.name} className={styles.unlock}>
                      <UnlockIcon src={unlock.imageUrl} />
                      <span>{unlock.name_zh || termText(unlock.name)}</span>
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
  const termText = useRor2TermText();
  return (
    <article className={`${theme.frame} ${styles.card} ${styles.faceCard}`}>
      <EntryFace src={row.imageUrl} />
      <div>
        <div className={styles.nameRow}>
          <h3 className={styles.name}>
            {row.dlcIconUrl ? <Ror2ExpansionIcon src={row.dlcIconUrl} label={row.dlcLabel} /> : null}
            {row.name_zh || termText(row.name)}
          </h3>
          {row.note ? <span className={styles.expansion}>{row.note}</span> : null}
        </div>
        {row.quote ? (
          <p className={styles.quote}>
            <Ror2RichText text={row.quote_zh || row.quote} />
          </p>
        ) : null}
        {row.description ? (
          <div className={styles.desc}>
            <Ror2RichText text={row.description_zh || row.description} />
          </div>
        ) : null}
      </div>
    </article>
  );
}

function EntryFace({ src }: { src?: string | null }) {
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
      onError={() => setHidden(true)}
    />
  );
}
