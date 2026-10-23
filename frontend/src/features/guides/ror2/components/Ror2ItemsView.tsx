import { useMemo, useState, type ReactNode } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import type { Ror2Item } from "@/features/guides/ror2/api/ror2Api";
import { apiError } from "@/shared/api/apiError";
import {
  ror2ItemRarityText,
  ror2ItemTableStackTexts,
  ror2RarityAccent,
} from "@/features/guides/ror2/model/ror2Catalog";
import { ror2ItemExpansionZh } from "@/features/guides/ror2/model/ror2ItemZh";
import { ror2ExpansionWikiTitle } from "@/features/guides/ror2/model/ror2Expansion";
import {
  filterRor2Items,
  ror2ActiveRarity,
  ror2CatalogExpansionRows,
  ror2CatalogItems,
  ror2ExpansionOrder,
  ror2ItemSections,
  ror2ItemSource,
  ror2SurvivorPacks,
  sortRor2Items,
  type Ror2ItemSortKey,
} from "@/features/guides/ror2/model/ror2Home";
import { ror2ItemDetailHref } from "@/features/guides/ror2/model/ror2ItemDetail";
import { useRor2Catalog } from "@/features/guides/ror2/hooks/useRor2Catalog";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import { Ror2ItemIcon } from "./Ror2ItemIcon";
import { Ror2ListDlcMark, Ror2ListMedia } from "./Ror2ListMedia";
import { Ror2RichText } from "./Ror2RichText";
import { Ror2TextInfo, Ror2TokenText } from "./Ror2TokenText";
import { Ror2WikiStructure } from "./Ror2WikiStructure";
import styles from "./Ror2ItemsView.module.css";
import theme from "./ror2Theme.module.css";

const NAME_COLUMN = { key: "name", label: "物品" } as const;
const DESCRIPTION_COLUMN = { key: "description", label: "描述" } as const;
const STACK_COLUMN = { key: "stack", label: "堆叠方式" } as const;

export function Ror2ItemsView() {
  const catalog = useRor2Catalog();
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const [sortKey, setSortKey] = useState<Ror2ItemSortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const items = useMemo(
    () => (catalog.data ? ror2CatalogItems(catalog.data) : []),
    [catalog.data],
  );
  const scope = useMemo(
    () => (catalog.data ? ror2CatalogExpansionRows(catalog.data) : []),
    [catalog.data],
  );
  const expansionOrder = useMemo(() => ror2ExpansionOrder(scope), [scope]);
  const packs = useMemo(() => ror2SurvivorPacks(items, scope), [items, scope]);
  const sections = useMemo(() => ror2ItemSections(items), [items]);
  const source = ror2ItemSource(params.get("src"), items);
  const rarity = ror2ActiveRarity(params.get("cat"), items);
  const columns: { key: Ror2ItemSortKey; label: string }[] = [
    NAME_COLUMN,
    DESCRIPTION_COLUMN,
    STACK_COLUMN,
  ];
  const query = params.get("q") ?? "";
  const visible = useMemo(
    () =>
      sortRor2Items(
        filterRor2Items(items, query, rarity, source, true),
        sortKey,
        sortDir,
        expansionOrder,
      ),
    [items, query, rarity, source, sortKey, sortDir, expansionOrder],
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
      {catalog.data ? (
        <Ror2WikiStructure articles={catalog.data.wiki_articles ?? []} articleIds={["Items", "Equipment"]} />
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
        <div className={styles.main}>
          <div className={styles.filters}>
            <FilterRow label="来源">
              <Chip pressed={source === "all"} onSelect={() => setSource("all")}>
                全部
              </Chip>
              {packs.map((pack) => {
                const wikiTitle = ror2ExpansionWikiTitle(catalog.data?.wiki_articles, pack.id);
                const icon = pack.iconUrl ? (
                  <Ror2ExpansionIcon
                    src={pack.iconUrl}
                    label={ror2ItemExpansionZh(pack.id, pack.label)}
                  />
                ) : null;
                const label = wikiTitle?.token ? (
                  <Ror2TokenText value={wikiTitle} showInfo={false} />
                ) : (
                  ror2ItemExpansionZh(pack.id, pack.label)
                );
                const chip = (
                  <Chip
                    pressed={source === pack.id}
                    onSelect={() => setSource(pack.id)}
                    icon={icon}
                  >
                    {label}
                  </Chip>
                );
                return wikiTitle?.token ? (
                  <span key={pack.id} className={styles.tokenFilter}>
                    {chip}
                    <Ror2TextInfo value={wikiTitle} />
                  </span>
                ) : (
                  <span key={pack.id}>{chip}</span>
                );
              })}
            </FilterRow>
            {sections.map((section) => (
              <FilterRow key={section.id} label={section.label}>
                {section.rarities.map((chip) => {
                  const rarityText = ror2ItemRarityText(items, chip.id);
                  const button = (
                    <Chip
                      pressed={rarity === chip.id}
                      onSelect={() => setRarity(chip.id)}
                      icon={(
                        <span
                          className={styles.pip}
                          style={{ background: ror2RarityAccent(chip.id) }}
                        />
                      )}
                    >
                      <Ror2TokenText value={rarityText} showInfo={false} />
                    </Chip>
                  );
                  return rarityText.token ? (
                    <span key={chip.id} className={styles.tokenFilter}>
                      {button}
                      <Ror2TextInfo value={rarityText} />
                    </span>
                  ) : (
                    <span key={chip.id}>{button}</span>
                  );
                })}
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
                <colgroup>
                  <col className={styles.itemColumn} />
                  <col className={styles.descriptionColumn} />
                  <col className={styles.stackColumn} />
                </colgroup>
                <thead>
                  <tr>
                    {columns.map((column) => {
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
                  {visible.map((item, index) => (
                    <ItemRow key={`${index}-${item.code}-${item.name}`} item={item} search={location.search} />
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
    <div className={`${styles.filterRow} ${styles.filterGridRow}`}>
      <span className={styles.filterLabel}>{label}</span>
      <div className={styles.chips}>{children}</div>
    </div>
  );
}

function Chip({
  pressed,
  onSelect,
  icon,
  children,
}: {
  pressed: boolean;
  onSelect: () => void;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`${theme.wikiBtn} ${styles.chip}${pressed ? ` ${theme.wikiBtnOn}` : ""}`}
      aria-pressed={pressed}
      onClick={onSelect}
    >
      <span className={styles.chipIcon} aria-hidden="true">{icon}</span>
      <span className={styles.chipText}>{children}</span>
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

function ItemRow({ item, search }: { item: Ror2Item; search: string }) {
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  const imageAvailable = Boolean(item.image_url && item.image_url !== failedImageUrl);
  const stack = ror2ItemTableStackTexts(item.stats);
  const name = item.localizedText.name;
  const quote = item.localizedText.quote;
  const description = item.localizedText.description;
  return (
    <tr>
      <th scope="row" className={styles.itemCell} aria-label={name.text || name.original}>
        <div className={styles.itemIdentity}>
          <Ror2ListMedia expansion={item.expansion} imageAvailable={imageAvailable} className={styles.itemIconWrap}>
            <Ror2ItemIcon
              src={item.image_url}
              accent={ror2RarityAccent(item.rarity)}
              onImageError={() => setFailedImageUrl(item.image_url ?? null)}
            />
          </Ror2ListMedia>
          {!imageAvailable ? <Ror2ListDlcMark expansion={item.expansion} /> : null}
          <span className={styles.itemName}>
            <Ror2TokenText value={name}>
              <Link className={styles.itemNameLink} aria-label={name.text || name.original} to={ror2ItemDetailHref(item, search)}>
                {name.text}
              </Link>
            </Ror2TokenText>
          </span>
        </div>
      </th>
      <td className={styles.descriptionCell}>
        <div className={styles.descriptionPair}>
          <div className={styles.descriptionSimple} role="group" aria-label="简单描述">
            {quote.text.trim() ? <Ror2RichText text={quote} /> : "—"}
          </div>
          <div className={styles.descriptionDetailed} role="group" aria-label="详细描述">
            {description.text.trim() ? <Ror2RichText text={description} /> : "—"}
          </div>
        </div>
      </td>
      <td className={styles.stackCell}>
        {stack.length
          ? stack.map((value, index) => (
              <span key={`${value.original}-${index}`}>
                {index ? " / " : ""}
                <Ror2TokenText value={value} />
              </span>
            ))
          : "—"}
      </td>
    </tr>
  );
}
