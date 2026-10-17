import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Ror2Survivor } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import { ror2ItemExpansionZh } from "@/lib/ror2ItemZh";
import {
  filterRor2Survivors,
  ror2ActiveExpansion,
  ror2CatalogExpansionRows,
  ror2SurvivorExpansionId,
  ror2SurvivorHref,
  ror2SurvivorPacks,
  ror2SurvivorTableCells,
  sortRor2Survivors,
  type Ror2SurvivorSortKey,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import itemStyles from "./Ror2ItemsView.module.css";
import styles from "./Ror2SurvivorsView.module.css";
import theme from "./ror2Theme.module.css";

const COLUMNS: { key: Ror2SurvivorSortKey; label: string }[] = [
  { key: "image", label: "图像" },
  { key: "name", label: "名称" },
  { key: "health", label: "生命" },
  { key: "regen", label: "生命回复" },
  { key: "damage", label: "伤害" },
  { key: "speed", label: "移速" },
  { key: "acceleration", label: "加速度" },
  { key: "mass", label: "质量" },
  { key: "armor", label: "护甲" },
];

export function Ror2SurvivorsView() {
  const catalog = useRor2Catalog();
  const survivors = catalog.data?.survivors;
  const [params, setParams] = useSearchParams();
  const [sortKey, setSortKey] = useState<Ror2SurvivorSortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const query = params.get("q") ?? "";
  const rows = survivors ?? [];
  const scope = useMemo(
    () => (catalog.data ? ror2CatalogExpansionRows(catalog.data) : []),
    [catalog.data],
  );
  const cat = ror2ActiveExpansion(params.get("cat"), rows);
  const packs = useMemo(() => ror2SurvivorPacks(survivors ?? [], scope), [survivors, scope]);
  const visible = useMemo(
    () => sortRor2Survivors(filterRor2Survivors(survivors ?? [], query, cat, true), sortKey, sortDir),
    [survivors, query, cat, sortKey, sortDir],
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

  const onSort = (key: Ror2SurvivorSortKey) => {
    if (key === sortKey) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir("asc");
  };

  return (
    <div className={`${itemStyles.page} ${styles.wide}`}>
      <h1 className={itemStyles.title}>幸存者</h1>
      {catalog.isPending ? <p className={itemStyles.status}>正在读取图鉴</p> : null}
      {catalog.isError ? (
        <div className={itemStyles.status}>
          <p>{apiError(catalog.error, "图鉴暂时拉不下来，请稍后再试")}</p>
          <div className={itemStyles.retry}>
            <button type="button" className={theme.wikiBtn} onClick={() => void catalog.refetch()}>
              重试
            </button>
          </div>
        </div>
      ) : null}
      {catalog.data ? (
        <div className={itemStyles.layout}>
          <aside className={itemStyles.sidebar}>
            <nav className={itemStyles.sideNav} aria-label="幸存者筛选">
              <div className={itemStyles.catList}>
                <CatButton
                  label="全部"
                  count={rows.length}
                  pressed={cat === "all"}
                  onSelect={() => setCat("all")}
                />
                {packs.map((pack) => {
                  const label = ror2ItemExpansionZh(pack.id, pack.label);
                  return (
                    <CatButton
                      key={pack.id}
                      label={label}
                      title={label === pack.title ? undefined : pack.title}
                      count={pack.count}
                      iconUrl={pack.iconUrl}
                      pressed={cat === pack.id}
                      onSelect={() => setCat(pack.id)}
                    />
                  );
                })}
              </div>
            </nav>
          </aside>
          <div className={itemStyles.main}>
            <div className={itemStyles.toolbar}>
              <p className={itemStyles.meta}>共 {visible.length} 位</p>
              <input
                className={itemStyles.search}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索名称、描述"
                aria-label="搜索幸存者"
                autoComplete="off"
              />
            </div>
            {visible.length === 0 ? (
              <p className={itemStyles.status}>没有匹配的幸存者</p>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <caption className={styles.caption}>幸存者属性</caption>
                  <thead>
                    <tr>
                      {COLUMNS.map((column) => {
                        const active = sortKey === column.key;
                        const ariaSort = active ? (sortDir === "asc" ? "ascending" : "descending") : "none";
                        return (
                          <th key={column.key} scope="col" aria-sort={ariaSort}>
                            <button type="button" className={styles.thBtn} onClick={() => onSort(column.key)}>
                              {column.label}
                              <SortMark active={active} dir={sortDir} />
                            </button>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((survivor) => (
                      <SurvivorRow
                        key={survivor.name}
                        survivor={survivor}
                        pack={packs.find((item) => item.id === ror2SurvivorExpansionId(survivor.expansion))}
                      />
                    ))}
                  </tbody>
                </table>
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
  title,
  count,
  iconUrl,
  pressed,
  onSelect,
}: {
  label: string;
  title?: string;
  count: number;
  iconUrl?: string | null;
  pressed: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`${theme.wikiBtn} ${itemStyles.catBtn}${pressed ? ` ${theme.wikiBtnOn}` : ""}`}
      aria-pressed={pressed}
      title={title}
      onClick={onSelect}
    >
      {iconUrl ? <Ror2ExpansionIcon src={iconUrl} /> : null}
      <span className={itemStyles.catLabel}>{label}</span>
      <span className={itemStyles.catCount}>{count}</span>
    </button>
  );
}

function SortMark({ active, dir }: { active: boolean; dir: "asc" | "desc" }) {
  return (
    <span className={styles.sort} aria-hidden>
      <span className={active && dir === "asc" ? `${styles.up} ${styles.upOn}` : styles.up} />
      <span className={active && dir === "desc" ? `${styles.down} ${styles.downOn}` : styles.down} />
    </span>
  );
}

function SurvivorRow({
  survivor,
  pack,
}: {
  survivor: Ror2Survivor;
  pack?: { id: string; title: string; iconUrl: string | null };
}) {
  const cells = ror2SurvivorTableCells(survivor);
  return (
    <tr>
      <td>
        <SurvivorFace src={survivor.image_url} />
      </td>
      <td className={styles.nameCell}>
        <span className={styles.who}>
          {pack && pack.id !== "base" && pack.iconUrl ? (
            <Ror2ExpansionIcon src={pack.iconUrl} label={pack.title} />
          ) : null}
          <Link className={styles.name} to={ror2SurvivorHref(survivor.name)}>
            {survivor.name_zh || survivor.name}
          </Link>
        </span>
      </td>
      <td>
        <Stat base={cells.health} growth={cells.healthGrowth} />
      </td>
      <td>
        <Stat base={cells.regen} growth={cells.regenGrowth} />
      </td>
      <td>
        <Stat base={cells.damage} growth={cells.damageGrowth} />
      </td>
      <td>{cells.speed}</td>
      <td>{cells.acceleration}</td>
      <td>{cells.mass}</td>
      <td>{cells.armor}</td>
    </tr>
  );
}

function Stat({ base, growth }: { base: string; growth: string }) {
  if (!growth) return base;
  return (
    <>
      {base} <span className={styles.growth}>{growth}</span>
    </>
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
      width={48}
      height={48}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setHidden(true)}
    />
  );
}
