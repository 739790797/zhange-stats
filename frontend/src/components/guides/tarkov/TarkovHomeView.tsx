import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovBosses,
  fetchTarkovSiteSearch,
  type TarkovBossListItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { transparentThumbUrl } from "@/lib/tarkovItemImages";
import {
  TARKOV_HOME_BOSSES,
  TARKOV_HOME_ITEM_GROUPS,
  TARKOV_HOME_TRADERS,
  TARKOV_MAPS,
  bossPortraitUrl,
  buildHomeSearchIndex,
  buildSiteSearchSections,
  tarkovBossHref,
  traderPortraitUrl,
  type TarkovMapCard,
  type TarkovSiteSearchRow,
} from "@/lib/tarkovHomeNav";
import { TarkovHomeToolRail } from "@/components/guides/tarkov/TarkovHomeToolRail";
import styles from "./TarkovHomeView.module.css";

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.4" />
      <line
        x1="9.5"
        y1="9.5"
        x2="13"
        y2="13"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="square"
      />
    </svg>
  );
}

function SectionHead({
  title,
  en,
  extra,
}: {
  title: string;
  en?: string;
  extra?: ReactNode;
}) {
  return (
    <div className={styles.sectionHead}>
      <span className={styles.sectionBar} aria-hidden />
      <span className={styles.sectionTitle}>{title}</span>
      {en ? <span className={styles.sectionEn}>{en}</span> : null}
      {extra ? <span className={styles.sectionExtra}>{extra}</span> : null}
    </div>
  );
}

function spawnAccent(label: string): string {
  const nums = [...label.matchAll(/(\d+)/g)].map((m) => Number(m[1]));
  const n = nums.length ? Math.max(...nums) : 0;
  if (n >= 40) return "#c8932a";
  if (n >= 15) return "#7ab648";
  return "#d44a4a";
}

type HomeBossRow = {
  id: string;
  href: string;
  name: string;
  nickname?: string;
  map: string;
  spawn: string;
  guards: string;
  accent: string;
  portrait: string;
};

function homeBossesFromApi(items: TarkovBossListItem[]): HomeBossRow[] {
  return items.map((item) => ({
    id: item.id || item.slug,
    href: tarkovBossHref(item.slug),
    name: item.name,
    nickname: item.nickname || "",
    map: item.maps_label || "—",
    spawn: item.spawn_short || item.spawn_label || "—",
    guards: item.escorts_label || "—",
    accent: spawnAccent(item.spawn_short || item.spawn_label || ""),
    portrait: item.portrait_link || "",
  }));
}

function homeBossesFallback(): HomeBossRow[] {
  return TARKOV_HOME_BOSSES.map((row) => ({
    id: row.id,
    href: row.href,
    name: row.label,
    nickname: row.nickname,
    map: row.map,
    spawn: row.spawn,
    guards: row.guards,
    accent: row.accent,
    portrait: bossPortraitUrl(row.id),
  }));
}

function BossName({ row }: { row: HomeBossRow }) {
  const [broken, setBroken] = useState(false);
  const src = row.portrait;
  return (
    <span className={styles.bossName}>
      {src && !broken ? (
        <img
          className={styles.bossAvatar}
          src={src}
          alt=""
          width={56}
          height={56}
          loading="lazy"
          decoding="async"
          onError={() => setBroken(true)}
        />
      ) : (
        <span
          className={styles.bossTick}
          style={{ background: row.accent }}
          aria-hidden
        />
      )}
      {row.name}
    </span>
  );
}

function HomeTile({
  href,
  icon,
  label,
  soon,
}: {
  href: string;
  icon: string;
  label: string;
  soon?: boolean;
}) {
  const className = `${styles.mapCard} ${soon ? styles.mapSoon : ""}`;
  const body = (
    <>
      <svg
        className={styles.mapIcon}
        viewBox="0 0 24 24"
        width="18"
        height="18"
        aria-hidden
      >
        <path d={icon} fill="currentColor" />
      </svg>
      <span className={styles.mapName}>{label}</span>
    </>
  );

  if (soon) {
    return (
      <span className={className} aria-disabled="true">
        {body}
      </span>
    );
  }

  return (
    <Link to={href} className={className}>
      {body}
    </Link>
  );
}

function MapCard({ item }: { item: TarkovMapCard }) {
  return (
    <HomeTile
      href={item.href}
      icon={item.icon}
      label={item.label}
      soon={item.status === "soon" || Boolean(item.comingSoon)}
    />
  );
}

function ResultThumb({ src }: { src?: string }) {
  const [broken, setBroken] = useState(false);
  const thumb = transparentThumbUrl(src) || src || "";
  if (!thumb || broken) return null;
  return (
    <img
      className={styles.resultThumb}
      src={thumb}
      alt=""
      width={36}
      height={36}
      onError={() => setBroken(true)}
    />
  );
}

function SearchResultRow({ hit }: { hit: TarkovSiteSearchRow }) {
  const className = `${styles.result} ${hit.soon ? styles.resultSoon : ""}`;
  const body = (
    <>
      <ResultThumb src={hit.icon} />
      <span className={styles.resultBody}>
        <span className={styles.resultLabel}>{hit.label}</span>
        {hit.extra ? (
          <span className={styles.resultExtra}>{hit.extra}</span>
        ) : null}
      </span>
    </>
  );
  if (hit.soon) {
    return (
      <span className={className} aria-disabled="true">
        {body}
      </span>
    );
  }
  return (
    <Link to={hit.href} className={className}>
      {body}
    </Link>
  );
}

export function TarkovHomeView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const committed = (searchParams.get("q") || "").trim();
  const [draft, setDraft] = useState(committed);
  const index = useMemo(() => buildHomeSearchIndex(), []);
  const searching = committed.length > 0;
  const bossesQuery = useQuery({
    queryKey: ["guides-tarkov-bosses"],
    queryFn: fetchTarkovBosses,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const searchQuery = useQuery({
    queryKey: ["guides-tarkov-search", committed],
    queryFn: () => fetchTarkovSiteSearch(committed),
    enabled: searching,
    staleTime: 60_000,
    retry: 1,
  });
  const bossRows = useMemo(() => {
    const items = bossesQuery.data?.items;
    if (items?.length) return homeBossesFromApi(items);
    return homeBossesFallback();
  }, [bossesQuery.data]);
  const sections = useMemo(
    () => buildSiteSearchSections(committed, searchQuery.data, index),
    [committed, searchQuery.data, index],
  );

  useEffect(() => {
    setDraft(committed);
  }, [committed]);

  const commitSearch = (value: string) => {
    const next = value.trim();
    const params = new URLSearchParams(searchParams);
    if (next) params.set("q", next);
    else params.delete("q");
    setSearchParams(params, { replace: true });
  };

  const waiting = searching && searchQuery.isLoading && !searchQuery.data;

  return (
    <>
      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <h1 className={styles.title}>逃离塔科夫</h1>
          <p className={styles.subtitle}>ESCAPE FROM TARKOV · 中文攻略站</p>
          <form
            className={styles.search}
            onSubmit={(e) => {
              e.preventDefault();
              commitSearch(draft);
            }}
          >
            <span className={styles.searchIcon}>
              <SearchIcon />
            </span>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="搜物品、任务、地图、商人、BOSS…"
              aria-label="全站搜索攻略"
              autoComplete="off"
              enterKeyHint="search"
            />
            <kbd className={styles.kbd}>Enter</kbd>
          </form>
        </div>
      </section>

      <div className={styles.layout}>
        <div className={styles.main}>
          {searching ? (
            <>
              {searchQuery.isError ? (
                <div className={styles.empty}>
                  {apiError(searchQuery.error, "搜索失败")}
                </div>
              ) : null}
              {waiting ? (
                <div className={styles.empty}>搜索中…</div>
              ) : sections.length ? (
                sections.map((section) => (
                  <section key={section.id}>
                    <SectionHead title={section.label} extra={section.extra} />
                    <div className={styles.resultList}>
                      {section.hits.map((hit) => (
                        <SearchResultRow key={hit.key} hit={hit} />
                      ))}
                    </div>
                  </section>
                ))
              ) : searchQuery.isError ? null : (
                <div className={styles.empty}>无匹配结果</div>
              )}
            </>
          ) : (
            <>
              <section>
                <SectionHead title="地图" en="Maps" />
                <div className={styles.mapGrid}>
                  {TARKOV_MAPS.map((item) => (
                    <MapCard key={item.id} item={item} />
                  ))}
                </div>
              </section>

              <section>
                <SectionHead title="物品" en="Items" />
                <div className={styles.itemGroups}>
                  {TARKOV_HOME_ITEM_GROUPS.map((group) => (
                    <div key={group.id} className={styles.itemGroup}>
                      <div className={styles.itemGroupHead}>
                        <span className={styles.itemGroupTitle}>
                          {group.label}
                        </span>
                        {group.en ? (
                          <span className={styles.itemGroupEn}>{group.en}</span>
                        ) : null}
                      </div>
                      <div className={styles.mapGrid}>
                        {group.items.map((item) => (
                          <HomeTile
                            key={item.id}
                            href={item.href}
                            icon={item.icon}
                            label={item.label}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section>
                <SectionHead title="商人" en="Traders" />
                <div className={styles.traderGrid}>
                  {TARKOV_HOME_TRADERS.map((item) => (
                    <Link
                      key={item.id}
                      to={item.href}
                      className={styles.traderCard}
                    >
                      <img
                        className={styles.traderAvatar}
                        src={traderPortraitUrl(item.id)}
                        alt=""
                        width={72}
                        height={72}
                        loading="lazy"
                        decoding="async"
                      />
                      <div className={styles.traderEnglish}>{item.english}</div>
                      <div className={styles.traderChinese}>{item.chinese}</div>
                    </Link>
                  ))}
                </div>
              </section>

              <section>
                <SectionHead title="BOSS" extra="出生率 / 保镖数" />
                <div className={styles.bossTable}>
                  <div className={styles.bossHead}>
                    <span>名称</span>
                    <span>昵称</span>
                    <span>地图</span>
                    <span>出生率</span>
                    <span>保镖</span>
                  </div>
                  {bossRows.map((row) => (
                    <Link
                      key={row.id}
                      to={row.href}
                      className={styles.bossRow}
                    >
                      <BossName row={row} />
                      <span className={styles.bossNick}>{row.nickname || ""}</span>
                      <span className={styles.bossMap}>{row.map}</span>
                      <span
                        className={styles.bossSpawn}
                        style={{ color: row.accent }}
                      >
                        {row.spawn}
                      </span>
                      <span className={styles.bossGuards}>{row.guards}</span>
                    </Link>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
        <TarkovHomeToolRail />
      </div>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <span>非官方第三方 · 数据来源 tarkov.dev</span>
          <div className={styles.footerLinks}>
            <a
              href="https://github.com/739790797/zhange-stats"
              target="_blank"
              rel="noreferrer"
            >
              GitHub
            </a>
            <a href="https://tarkov.dev" target="_blank" rel="noreferrer">
              API
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}
