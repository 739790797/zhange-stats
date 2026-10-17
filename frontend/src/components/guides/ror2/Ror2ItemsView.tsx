import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import type { Ror2Item } from "@/api/ror2Api";
import { apiError } from "@/lib/apiError";
import { ror2ItemTableStack, ror2RarityAccent } from "@/lib/ror2Catalog";
import { ror2ItemExpansionZh, ror2ItemRarityZh, ror2ItemStackZh } from "@/lib/ror2ItemZh";
import {
  filterRor2Items,
  ror2ActiveRarity,
  ror2CatalogItems,
  ror2DlcMark,
  ror2ItemCooldownText,
  ror2ItemRarityIsActive,
  ror2ItemSections,
  ror2ItemSource,
  ror2SurvivorPacks,
  sortRor2Items,
  type Ror2ItemSortKey,
} from "@/lib/ror2Home";
import { useRor2Catalog } from "@/lib/useRor2Catalog";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import { Ror2ItemIcon } from "./Ror2ItemIcon";
import { Ror2RichText } from "./Ror2RichText";
import styles from "./Ror2ItemsView.module.css";
import theme from "./ror2Theme.module.css";

const NAME_COLUMN = { key: "name", label: "物品" } as const;
const DESCRIPTION_COLUMN = { key: "description", label: "描述" } as const;

export function Ror2ItemsView() {
  const catalog = useRor2Catalog();
  const [params, setParams] = useSearchParams();
  const [sortKey, setSortKey] = useState<Ror2ItemSortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const items = useMemo(
    () => (catalog.data ? ror2CatalogItems(catalog.data) : []),
    [catalog.data],
  );
  const packs = useMemo(() => ror2SurvivorPacks(items), [items]);
  const sections = useMemo(() => ror2ItemSections(items), [items]);
  const source = ror2ItemSource(params.get("src"), items);
  const rarity = ror2ActiveRarity(params.get("cat"), items);
  const showCooldown = ror2ItemRarityIsActive(rarity);
  const columns: { key: Ror2ItemSortKey; label: string }[] = [
    NAME_COLUMN,
    DESCRIPTION_COLUMN,
    showCooldown ? { key: "cooldown", label: "冷却" } : { key: "stack", label: "堆叠" },
  ];
  const query = params.get("q") ?? "";
  const metricSort: Ror2ItemSortKey =
    sortKey === "stack" || sortKey === "cooldown" ? (showCooldown ? "cooldown" : "stack") : sortKey;
  const visible = useMemo(
    () => sortRor2Items(filterRor2Items(items, query, rarity, source, true), metricSort, sortDir),
    [items, query, rarity, source, metricSort, sortDir],
  );

  const setSource = (next: string) => {
    if (next === source) return;
    const nextParams = new URLSearchParams(params);
    if (!next || next === "all") nextParams.delete("src");
    else nextParams.set("src", next);
    setParams(nextParams, { replace: true });
  };

  const setRarity = (next: string) => {
    const nextParams = new URLSearchParams(params);
    if (rarity === next) nextParams.delete("cat");
    else nextParams.set("cat", next);
    setParams(nextParams, { replace: true });
  };

  const setQuery = (next: string) => {
    const nextParams = new URLSearchParams(params);
    if (next) nextParams.set("q", next);
    else nextParams.delete("q");
    setParams(nextParams, { replace: true });
  };

  const onSort = (key: Ror2ItemSortKey) => {
    if (key === sortKey) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir("asc");
  };

  return (
    <div className={styles.page}>
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
        <div className={styles.main}>
          <div className={styles.filters}>
            <FilterRow label="来源">
              <Chip pressed={source === "all"} onSelect={() => setSource("all")}>
                全部
              </Chip>
              {packs.map((pack) => (
                <Chip key={pack.id} pressed={source === pack.id} onSelect={() => setSource(pack.id)}>
                  {pack.iconUrl ? <Ror2ExpansionIcon src={pack.iconUrl} /> : null}
                  {ror2ItemExpansionZh(pack.id, pack.label)}
                </Chip>
              ))}
            </FilterRow>
            {sections.map((section) => (
              <FilterRow key={section.id} label={section.label}>
                {section.rarities.map((chip) => (
                  <Chip
                    key={chip.id}
                    pressed={rarity === chip.id}
                    onSelect={() => setRarity(chip.id)}
                  >
                    <span className={styles.pip} style={{ background: ror2RarityAccent(chip.id) }} aria-hidden />
                    {ror2ItemRarityZh(chip.id)}
                  </Chip>
                ))}
              </FilterRow>
            ))}
            <div className={styles.filterRow}>
              <span className={styles.filterLabel}>名称</span>
              <input
                className={styles.search}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索名称、描述"
                aria-label="搜索物品"
                autoComplete="off"
              />
              <p className={styles.meta}>共 {visible.length} 件</p>
            </div>
          </div>
          {visible.length === 0 ? (
            <p className={styles.status}>没有匹配的物品</p>
          ) : (
            <div className={styles.sheetWrap}>
              <table className={styles.sheet}>
                <caption className={styles.caption}>物品</caption>
                <thead>
                  <tr>
                    {columns.map((column) => {
                      const active = metricSort === column.key;
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
                  {visible.map((item, index) => (
                    <ItemRow key={`${index}-${item.code}-${item.name}`} item={item} showCooldown={showCooldown} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function FilterRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>{label}</span>
      <div className={styles.chips}>{children}</div>
    </div>
  );
}

function Chip({
  pressed,
  onSelect,
  children,
}: {
  pressed: boolean;
  onSelect: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`${theme.wikiBtn} ${styles.chip}${pressed ? ` ${theme.wikiBtnOn}` : ""}`}
      aria-pressed={pressed}
      onClick={onSelect}
    >
      {children}
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

function ItemRow({ item, showCooldown }: { item: Ror2Item; showCooldown: boolean }) {
  const dlc = ror2DlcMark(item.expansion);
  const metric = showCooldown
    ? ror2ItemCooldownText(item.cooldown)
    : ror2ItemStackZh(ror2ItemTableStack(item.stats));
  const name = item.name_zh || item.name;
  const description = item.description_zh || item.description;
  return (
    <tr>
      <td className={styles.itemCell}>
        <Ror2ItemIcon src={item.image_url} accent={ror2RarityAccent(item.rarity)} />
        <span className={styles.itemName}>
          {dlc ? <Ror2ExpansionIcon src={dlc.iconUrl} label={ror2ItemExpansionZh(dlc.id, dlc.label)} /> : null}
          {name}
        </span>
      </td>
      <td className={styles.descCell}>
        {description ? <Ror2RichText text={description} /> : null}
      </td>
      <td className={styles.stackCell}>{metric}</td>
    </tr>
  );
}
