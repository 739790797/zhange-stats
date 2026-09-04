import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovSiteSearch } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { transparentThumbUrl } from "@/lib/tarkovItemImages";
import {
  TARKOV_HOME_ITEM_GROUPS,
  TARKOV_HOME_PATH,
  TARKOV_HOME_TRADERS,
  TARKOV_MAPS,
  buildHomeSearchIndex,
  buildSiteSearchSections,
  traderPortraitUrl,
  type TarkovMapCard,
  type TarkovSiteSearchRow,
} from "@/lib/tarkovHomeNav";
import {
  LEGAL_PRIVACY_PATH,
  LEGAL_TERMS_PATH,
  TARKOV_PUBLIC_DISCLAIMER,
} from "@/lib/legalDocs";
import { IcpBeianLink } from "@/components/IcpBeianLink";
import { TarkovHomeToolRail } from "@/components/guides/tarkov/TarkovHomeToolRail";
import {
  TarkovRaidPrepEntryModal,
  type RaidPrepEntryStep,
} from "@/components/guides/tarkov/TarkovRaidPrepEntryModal";
import { TarkovGoonSightingHint } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import { sameGoonMap } from "@/lib/tarkovGoonTracker";
import { useTarkovGoonTracker } from "@/lib/useTarkovGoonTracker";
import { useAuthStore } from "@/stores/authStore";
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

function HomeTile({
  href,
  icon,
  label,
  soon,
  goon,
  extra,
}: {
  href: string;
  icon: string;
  label: string;
  soon?: boolean;
  goon?: boolean;
  extra?: ReactNode;
}) {
  const className = `${styles.mapCard} ${soon ? styles.mapSoon : ""} ${
    goon ? styles.mapGoon : ""
  }`.trim();
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
      <span className={styles.mapText}>
        <span className={styles.mapName}>{label}</span>
        {extra}
      </span>
    </>
  );

  if (soon) {
    return (
      <span
        className={className}
        aria-disabled="true"
        aria-label={`${label}，即将推出`}
        title="即将推出"
      >
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
  const soon = item.status === "soon" || Boolean(item.comingSoon);
  const { status } = useTarkovGoonTracker();
  const goon = !soon && sameGoonMap(item.id, status?.map_slug);
  return (
    <HomeTile
      href={item.href}
      icon={item.icon}
      label={item.label}
      soon={soon}
      goon={goon}
      extra={
        soon ? undefined : (
          <TarkovGoonSightingHint mapId={item.id} variant="tile" />
        )
      }
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
  const navigate = useNavigate();
  const gameMode = useTarkovGameMode();
  const loggedIn = Boolean(useAuthStore((s) => s.token));
  const [searchParams, setSearchParams] = useSearchParams();
  const [entryOpen, setEntryOpen] = useState(false);
  const [entryStep, setEntryStep] = useState<RaidPrepEntryStep>("create");
  const committed = (searchParams.get("q") || "").trim();
  const [draft, setDraft] = useState(committed);
  const index = useMemo(() => buildHomeSearchIndex(), []);
  const searching = committed.length > 0;
  const searchQuery = useQuery({
    queryKey: ["guides-tarkov-search", gameMode, committed],
    queryFn: () => fetchTarkovSiteSearch(committed),
    enabled: searching,
    staleTime: 60_000,
    retry: 1,
  });
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

  const openEntry = (step: RaidPrepEntryStep) => {
    if (!loggedIn) {
      navigate("/login", {
        state: { from: { pathname: TARKOV_HOME_PATH } },
      });
      return;
    }
    setEntryStep(step);
    setEntryOpen(true);
  };

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
                <SectionHead title="联机大厅" en="Lobby" />
                <div className={styles.raidActions}>
                  <button
                    type="button"
                    className={styles.raidAction}
                    onClick={() => openEntry("create")}
                  >
                    <span className={styles.raidActionTitle}>创建房间</span>
                  </button>
                  <button
                    type="button"
                    className={styles.raidAction}
                    onClick={() => openEntry("join")}
                  >
                    <span className={styles.raidActionTitle}>加入房间</span>
                  </button>
                </div>
              </section>

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
                    </Link>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
        <TarkovHomeToolRail />
      </div>

      <TarkovRaidPrepEntryModal
        open={entryOpen}
        step={entryStep}
        onClose={() => setEntryOpen(false)}
      />

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <p className={styles.footerDisclaimer}>{TARKOV_PUBLIC_DISCLAIMER}</p>
          <div className={styles.footerRow}>
            <span>非官方第三方 · 数据来源 tarkov.dev</span>
            <div className={styles.footerLinks}>
              <IcpBeianLink />
              <Link to={LEGAL_TERMS_PATH}>服务条款</Link>
              <Link to={LEGAL_PRIVACY_PATH}>隐私说明</Link>
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
        </div>
      </footer>
    </>
  );
}
