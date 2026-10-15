import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Ror2Item } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import { ror2ItemStackLabel, ror2RarityAccent } from "@/lib/ror2Catalog";
import {
  ROR2_HOME_PATH,
  filterRor2Items,
  groupRor2ItemsByRarity,
  ror2ActiveRarity,
  ror2CatalogItems,
  ror2ItemSections,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2ItemIcon } from "./Ror2ItemIcon";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2ItemsView.module.css";
import theme from "./ror2Theme.module.css";

export function Ror2ItemsView() {
  const catalog = useRor2Catalog();
  const [params, setParams] = useSearchParams();
  const items = useMemo(
    () => (catalog.data ? ror2CatalogItems(catalog.data) : []),
    [catalog.data],
  );
  const sections = useMemo(() => ror2ItemSections(items), [items]);
  const cat = ror2ActiveRarity(params.get("cat"), items);
  const query = params.get("q") ?? "";
  const visible = useMemo(
    () => filterRor2Items(items, query, cat),
    [items, query, cat],
  );
  const groups = useMemo(
    () => (cat === "all" ? groupRor2ItemsByRarity(visible) : [{ rarity: cat, items: visible }]),
    [cat, visible],
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

  return (
    <div className={styles.page}>
      <p className={styles.crumb}>
        <Link to={ROR2_HOME_PATH}>雨中冒险2</Link>
        <span aria-hidden> / </span>
        物品
      </p>
      <h1 className={styles.title}>物品</h1>
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
            <nav className={styles.sideNav} aria-label="物品稀有度">
              <div className={styles.catList}>
                <CatButton
                  label="全部"
                  count={items.length}
                  pressed={cat === "all"}
                  onSelect={() => setCat("all")}
                />
              </div>
              {sections.map((section) => (
                <section key={section.id}>
                  <h2 className={styles.groupLabel}>{section.label}</h2>
                  <div className={styles.catList}>
                    {section.rarities.map((chip) => (
                      <CatButton
                        key={chip.id}
                        label={chip.label}
                        count={chip.count}
                        pressed={cat === chip.id}
                        onSelect={() => setCat(chip.id)}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </nav>
          </aside>
          <div className={styles.main}>
            <div className={styles.toolbar}>
              <p className={styles.meta}>共 {visible.length} 件</p>
              <input
                className={styles.search}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索名称、描述"
                aria-label="搜索物品"
                autoComplete="off"
              />
            </div>
            {visible.length === 0 ? (
              <p className={styles.status}>没有匹配的物品</p>
            ) : (
              <div className={styles.groups}>
                {groups.map((group) => (
                  <section key={group.rarity}>
                    {cat === "all" ? <h2 className={styles.groupHead}>{group.rarity}</h2> : null}
                    <div className={styles.list}>
                      {group.items.map((item) => (
                        <ItemCard key={`${item.rarity}-${item.code}-${item.name}`} item={item} />
                      ))}
                    </div>
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
      {label === "全部" ? null : (
        <span className={styles.pip} style={{ background: ror2RarityAccent(label) }} aria-hidden />
      )}
      <span className={styles.catLabel}>{label}</span>
      <span className={styles.catCount}>{count}</span>
    </button>
  );
}

function ItemCard({ item }: { item: Ror2Item }) {
  const stack = ror2ItemStackLabel(item.stats);
  return (
    <article className={`${theme.frame} ${styles.card}`}>
      <Ror2ItemIcon src={item.image_url} accent={ror2RarityAccent(item.rarity)} />
      <div>
        <div className={styles.nameRow}>
          <h3 className={styles.name}>{item.name}</h3>
          {stack ? <span className={styles.stack}>{stack}</span> : null}
        </div>
        {item.expansion ? <p className={styles.expansion}>{item.expansion}</p> : null}
        {item.quote ? (
          <p className={styles.quote}>
            <Ror2RichText text={item.quote} />
          </p>
        ) : null}
        {item.description ? (
          <div className={styles.desc}>
            <Ror2RichText text={item.description} />
          </div>
        ) : (
          <StatFallback item={item} />
        )}
      </div>
    </article>
  );
}

function StatFallback({ item }: { item: Ror2Item }) {
  const stats = item.stats ?? [];
  if (!stats.length) return null;
  return (
    <div className={styles.desc}>
      {stats.map((stat) => (
        <p key={`${stat.label}-${stat.value}`} className={styles.statLine}>
          {stat.label} <Ror2RichText text={stat.value} />
        </p>
      ))}
    </div>
  );
}
