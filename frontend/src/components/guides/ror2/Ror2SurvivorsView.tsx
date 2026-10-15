import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Ror2Survivor } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import {
  filterRor2Survivors,
  ror2SurvivorExpansionLabel,
  ror2SurvivorStatLine,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2ItemsView.module.css";
import theme from "./ror2Theme.module.css";

export function Ror2SurvivorsView() {
  const catalog = useRor2Catalog();
  const survivors = catalog.data?.survivors ?? [];
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const visible = useMemo(
    () => filterRor2Survivors(survivors, query, "all"),
    [survivors, query],
  );

  const setQuery = (next: string) => {
    const nextParams = new URLSearchParams(params);
    if (next) nextParams.set("q", next);
    else nextParams.delete("q");
    setParams(nextParams, { replace: true });
  };

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>幸存者</h1>
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
            <nav className={styles.sideNav} aria-label="幸存者分类">
              <div className={styles.catList}>
                <CatButton label="Characters" count={survivors.length} pressed onSelect={() => undefined} />
              </div>
            </nav>
          </aside>
          <div className={styles.main}>
            <div className={styles.toolbar}>
              <p className={styles.meta}>共 {visible.length} 位</p>
              <input
                className={styles.search}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索名称、描述"
                aria-label="搜索幸存者"
                autoComplete="off"
              />
            </div>
            {visible.length === 0 ? (
              <p className={styles.status}>没有匹配的幸存者</p>
            ) : (
              <div className={styles.groups}>
                <section>
                  <div className={styles.list}>
                    {visible.map((survivor, index) => (
                      <SurvivorCard key={`${index}-${survivor.name}`} survivor={survivor} />
                    ))}
                  </div>
                </section>
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

function SurvivorCard({ survivor }: { survivor: Ror2Survivor }) {
  const stats = ror2SurvivorStatLine(survivor);
  return (
    <article className={`${theme.frame} ${styles.card} ${styles.faceCard}`}>
      <SurvivorFace src={survivor.image_url} />
      <div>
        <div className={styles.nameRow}>
          <h3 className={styles.name}>{survivor.name}</h3>
          <span className={styles.expansion}>{ror2SurvivorExpansionLabel(survivor.expansion)}</span>
        </div>
        {survivor.umbra ? <p className={styles.quote}>{survivor.umbra}</p> : null}
        {survivor.description ? (
          <div className={styles.desc}>
            <Ror2RichText text={survivor.description} />
          </div>
        ) : null}
        {stats ? <p className={styles.desc}>{stats}</p> : null}
      </div>
    </article>
  );
}

function SurvivorFace({ src }: { src?: string | null }) {
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
