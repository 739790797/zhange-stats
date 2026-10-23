import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Ror2Item } from "@/features/guides/ror2/api/ror2Api";
import { apiError } from "@/shared/api/apiError";
import { ror2RarityAccent } from "@/features/guides/ror2/model/ror2Catalog";
import {
  ROR2_HOME_TILES,
  ROR2_ITEMS_PATH,
  ROR2_SIDE_LINKS,
  ROR2_SURVIVORS_PATH,
  ROR2_UNRELEASED_GROUPS,
  ROR2_UNRELEASED_PATH,
  filterRor2Items,
  ror2CatalogItems,
  ror2DlcMark,
  ror2ItemsHref,
  ror2SectionHref,
} from "@/features/guides/ror2/model/ror2Home";
import { useRor2Catalog } from "@/features/guides/ror2/hooks/useRor2Catalog";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import { Ror2ItemIcon } from "./Ror2ItemIcon";
import { Ror2RichText } from "./Ror2RichText";
import { Ror2TextInfo, Ror2TokenText } from "./Ror2TokenText";
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
      <section className={styles.hero} aria-labelledby="ror2-home-title">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>
            <span className={styles.eyebrowDot} aria-hidden="true" />
            <span>FIELD ARCHIVE</span>
            <span className={styles.eyebrowDivider} aria-hidden="true">
              /
            </span>
            <span>ROR2</span>
          </p>
          <h1 id="ror2-home-title" className={styles.title}>
            雨中冒险<span className={styles.titleNumber}>2</span>
          </h1>
          <p className={styles.subtitle}>
            RISK OF RAIN 2
            <span className={styles.subtitleDivider} aria-hidden="true" />
            SURVIVOR FIELD GUIDE
          </p>
          <p className={styles.description}>
            幸存者、物品、怪物与环境档案——在下一次跃迁前，先备好你的情报。
          </p>
        </div>

        <div className={styles.heroVisual} aria-hidden="true">
          <span className={styles.visualOrbit} />
          <span className={styles.visualOrbitTilt} />
          <span className={styles.visualPlanet} />
          <span className={styles.visualIndex}>02</span>
          <span className={styles.visualCaption}>
            FIELD
            <br />
            ARCHIVE
          </span>
        </div>

        <form
          className={styles.search}
          role="search"
          onSubmit={(event) => {
            event.preventDefault();
            commitSearch(draft);
          }}
        >
          <span className={styles.searchIcon} aria-hidden="true">
            <SearchIcon />
          </span>
          <span className={styles.searchLabel} aria-hidden="true">
            ITEM INDEX
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
          <button type="submit" className={styles.searchSubmit} aria-label="搜索物品">
            ↵
          </button>
        </form>

        <nav className={styles.heroLinks} aria-label="快速入口">
          <Link to={ROR2_SURVIVORS_PATH} className={styles.heroLink}>
            <span className={styles.heroLinkIndex} aria-hidden="true">
              01
            </span>
            <span>幸存者档案</span>
            <span className={styles.heroLinkArrow} aria-hidden="true">
              ↗
            </span>
          </Link>
          <Link to={ROR2_ITEMS_PATH} className={styles.heroLink}>
            <span className={styles.heroLinkIndex} aria-hidden="true">
              02
            </span>
            <span>物品图鉴</span>
            <span className={styles.heroLinkArrow} aria-hidden="true">
              ↗
            </span>
          </Link>
        </nav>
      </section>

      <div className={styles.columns}>
        <div className={styles.stack}>
          <section className={`${theme.frame} ${styles.panel} ${styles.indexPanel}`}>
            <div className={styles.panelHeader}>
              <div>
                <p className={styles.sectionCode}>
                  {searching ? "SEARCH TERMINAL / LIVE QUERY" : "FIELD ARCHIVE / DIRECTORY"}
                </p>
                <h2 className={styles.heading}>{searching ? "搜索结果" : "档案索引"}</h2>
              </div>
              <span className={styles.panelMeta}>
                {searching
                  ? catalog.isPending
                    ? "正在读取"
                    : catalog.isError
                      ? "暂不可用"
                      : `${hits.length} 条记录`
                  : `${String(ROR2_HOME_TILES.length).padStart(2, "0")} 个分类`}
              </span>
            </div>
            {searching ? (
              <SearchResults
                pending={catalog.isPending}
                error={catalog.isError ? apiError(catalog.error, "图鉴暂时拉不下来，请稍后再试") : ""}
                onRetry={() => void catalog.refetch()}
                hits={hits}
              />
            ) : (
              <TileGrid items={ROR2_HOME_TILES} draft={draft} />
            )}
          </section>
          <Ror2MiscPanel />
        </div>
        <UnreleasedRail />
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
      {hits.map((item) => {
        const dlc = ror2DlcMark(item.expansion);
        const name = item.localizedText.name;
        const quote = item.localizedText.quote;
        const description = item.localizedText.description;
        const rarity = item.localizedText.rarity;
        return (
          <div key={`${item.rarity}-${item.name}`} className={styles.resultRow}>
            <Link
              to={ror2ItemsHref(item.rarity, item.name)}
              className={`${theme.frame} ${styles.result}`}
            >
              <Ror2ItemIcon src={item.image_url} accent={ror2RarityAccent(item.rarity)} />
              <span className={styles.resultBody}>
                <span className={styles.resultName}>
                  {dlc ? <Ror2ExpansionIcon src={dlc.iconUrl} label={dlc.label} /> : null}
                  <Ror2TokenText value={name} showInfo={false} />
                </span>
                {item.rarity ? (
                  <span className={styles.resultMeta}>
                    <Ror2TokenText value={rarity} showInfo={false} />
                  </span>
                ) : null}
                {quote.text.trim() ? (
                  <Ror2RichText className={styles.excerpt} text={quote} showInfo={false} />
                ) : null}
                {description.text ? (
                  <Ror2RichText className={styles.excerpt} text={description} showInfo={false} />
                ) : null}
              </span>
            </Link>
            <span className={styles.resultTokenInfo}>
              <Ror2TextInfo value={name} />
              <Ror2TextInfo value={rarity} />
              <Ror2TextInfo value={quote} />
              <Ror2TextInfo value={description} />
            </span>
          </div>
        );
      })}
    </div>
  );
}

function TileGrid({
  items,
  draft,
}: {
  items: Array<{ id: string; label: string; href?: string }>;
  draft: string;
}) {
  return (
    <div className={styles.grid}>
      {items.map((tile, index) => {
        const tileClass = `${theme.wikiBtn} ${styles.tile}${tile.href ? "" : ` ${theme.wikiBtnQuiet} ${styles.tileDisabled}`}`;
        const contents = (
          <>
            <span className={styles.tileTop}>
              <span className={styles.tileIndex} aria-hidden="true">
                ARCHIVE / {String(index + 1).padStart(2, "0")}
              </span>
              <span className={styles.tileArrow} aria-hidden="true">
                ↗
              </span>
            </span>
            <span className={styles.tileLabel}>{tile.label}</span>
          </>
        );

        return tile.href ? (
          <Link
            key={tile.id}
            to={tile.id === "items" ? ror2ItemsHref("", draft) : tile.href}
            className={tileClass}
          >
            {contents}
          </Link>
        ) : (
          <span key={tile.id} className={tileClass} aria-disabled="true" title="尚未开放">
            {contents}
          </span>
        );
      })}
    </div>
  );
}

function UnreleasedRail() {
  return (
    <aside className={`${theme.frame} ${styles.rail}`}>
      <h2 className={styles.railTitle}>
        <Link to={ROR2_UNRELEASED_PATH}>Unreleased Items</Link>
      </h2>
      <nav className={styles.railNav} aria-label="Unreleased Items">
        {ROR2_UNRELEASED_GROUPS.map((group) => (
          <Link key={group.id} to={ror2SectionHref(ROR2_UNRELEASED_PATH, group.id)} className={styles.railLink}>
            {group.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}

function Ror2MiscPanel() {
  return (
    <section className={`${theme.frame} ${styles.panel} ${styles.miscPanel}`}>
      <div className={styles.panelHeader}>
        <div>
          <p className={styles.sectionCode}>SUPPLEMENTAL RECORDS</p>
          <h2 className={styles.heading}>杂项</h2>
        </div>
        <span className={styles.panelMeta}>尚未开放</span>
      </div>
      <TileGrid items={ROR2_SIDE_LINKS} draft="" />
    </section>
  );
}
