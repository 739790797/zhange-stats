import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovBosses } from "@/api/guidesApi";
import {
  groupBossCatalogTree,
  TARKOV_BOSS_HUB_SECTION_LABELS,
} from "@/lib/tarkovBossKinds";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import {
  TARKOV_HOME_PATH,
  TARKOV_TOP_NAV,
  isTarkovTopNavActive,
  tarkovBossHref,
  tarkovPageTitle,
  type TarkovNavStatus,
} from "@/lib/tarkovHomeNav";
import { TarkovThemed } from "@/components/guides/tarkov/TarkovThemed";
import { TarkovMeHeaderLink } from "@/components/guides/tarkov/TarkovMeHeaderLink";
import { TarkovRaidRoomHeaderLink } from "@/components/guides/tarkov/TarkovRaidRoomHeaderLink";
import {
  TarkovLiveWatchProvider,
  useTarkovLiveWatch,
} from "@/lib/tarkovLiveWatchContext";
import { TarkovGoonTrackerProvider } from "@/lib/tarkovGoonTrackerLive";
import {
  formatLiveWatchLogLine,
  formatLiveWatchShotLine,
} from "@/lib/tarkovLiveWatch";
import {
  TARKOV_GAME_MODES,
  useTarkovGameMode,
  useTarkovGameModeControls,
} from "@/lib/tarkovGameMode";
import styles from "./TarkovGuideShell.module.css";
import "./tarkovFonts.css";

export function TarkovSoonMark({ status }: { status: TarkovNavStatus }) {
  if (status === "ready") return null;
  return <span className={styles.soonMark}>即将推出</span>;
}

/** 逃离塔科夫游戏标识：六边形徽标 + ESCAPE FROM TARKOV 字标。 */
function TarkovGameLogo() {
  return (
    <span className={styles.gameLogo} aria-hidden>
      <svg
        className={styles.gameHex}
        viewBox="0 0 36 36"
        width="32"
        height="32"
      >
        <polygon
          points="18,2 32.5,10.25 32.5,25.75 18,34 3.5,25.75 3.5,10.25"
          fill="#1a1b14"
          stroke="#c8932a"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <polygon
          points="18,7.2 27.4,12.6 27.4,23.4 18,28.8 8.6,23.4 8.6,12.6"
          fill="none"
          stroke="#c8932a"
          strokeWidth="0.7"
          opacity="0.45"
        />
        <path
          d="M18 11.2 L24.2 21.8 H11.8 Z"
          fill="none"
          stroke="#c8932a"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path
          d="M18 15.4 L21.6 21.8 H14.4 Z"
          fill="#c8932a"
        />
      </svg>
      <svg
        className={styles.gameWordmark}
        viewBox="0 0 132 32"
        width="132"
        height="32"
      >
        <text
          x="0"
          y="9"
          fill="#c8932a"
          fontFamily="Rajdhani, 'Arial Narrow', sans-serif"
          fontWeight="600"
          fontSize="7.5"
          letterSpacing="3.6"
        >
          ESCAPE FROM
        </text>
        <text
          x="0"
          y="28"
          fill="#e8e3cf"
          fontFamily="Rajdhani, 'Arial Narrow', sans-serif"
          fontWeight="700"
          fontSize="16.5"
          letterSpacing="3.2"
        >
          TARKOV
        </text>
      </svg>
    </span>
  );
}

function NavCaret() {
  return (
    <svg
      className={styles.caret}
      width="8"
      height="5"
      viewBox="0 0 8 5"
      fill="none"
      aria-hidden
    >
      <path
        d="M1 1L4 4L7 1"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TarkovLiveWatchStatus() {
  const live = useTarkovLiveWatch();
  if (!live.visible) return null;
  const needResume = live.shotPerm === "prompt" || live.logPerm === "prompt";
  const body = (
    <>
      <span>{formatLiveWatchShotLine(live.lastShotAt)}</span>
      <span>{formatLiveWatchLogLine(live.lastLogAt)}</span>
    </>
  );
  if (needResume) {
    return (
      <button
        type="button"
        className={`${styles.pollClock} ${styles.pollClockBtn}`}
        title="继续读取已绑定的截图和日志目录"
        onClick={() => void live.resume()}
      >
        {body}
      </button>
    );
  }
  return (
    <div className={styles.pollClock} aria-live="polite">
      {body}
    </div>
  );
}

function TarkovGameModeSwitch() {
  const { mode, setMode } = useTarkovGameModeControls();
  return (
    <div className={styles.modeSwitch} role="group" aria-label="游戏模式">
      {TARKOV_GAME_MODES.map((item) => (
        <button
          key={item}
          type="button"
          className={`${styles.modeBtn} ${mode === item ? styles.modeBtnActive : ""}`}
          aria-pressed={mode === item}
          title={item === "pve" ? "合作模式（PVE）" : "在线对战（PVP）"}
          onClick={() => setMode(item)}
        >
          {item.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

type Props = {
  children: ReactNode;
};

/** 攻略暗色全幅外壳 + 顶栏，首页与弹药/枪械等内页共用。 */
export function TarkovGuideShell({ children }: Props) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const qParam = (searchParams.get("q") || "").trim();
  const [draft, setDraft] = useState(
    pathname === TARKOV_HOME_PATH || pathname === `${TARKOV_HOME_PATH}/`
      ? qParam
      : "",
  );
  const searchRef = useRef<HTMLInputElement>(null);
  const gameMode = useTarkovGameMode();
  useTarkovDocumentTitle(tarkovPageTitle(pathname));
  useEffect(() => {
    if (pathname === TARKOV_HOME_PATH || pathname === `${TARKOV_HOME_PATH}/`) {
      setDraft(qParam);
    }
  }, [pathname, qParam]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        target?.isContentEditable
      ) {
        return;
      }
      event.preventDefault();
      if (pathname.includes("raid-prep")) {
        const dock = document.getElementById("raid-prep-search");
        if (dock) {
          dock.focus();
          return;
        }
      }
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pathname]);
  const bossesQuery = useQuery({
    queryKey: ["guides-tarkov-bosses", gameMode],
    queryFn: fetchTarkovBosses,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const navItems = useMemo(() => {
    const bosses = bossesQuery.data?.items;
    if (!bosses?.length) return TARKOV_TOP_NAV;
    const grouped = groupBossCatalogTree(bosses);
    return TARKOV_TOP_NAV.map((item) => {
      if (item.id !== "bosses") return item;
      const sections: Array<{
        id: "boss" | "other";
        rows: typeof grouped.bosses;
      }> = [
        { id: "boss", rows: grouped.bosses },
        { id: "other", rows: grouped.others },
      ];
      return {
        ...item,
        groups: sections.flatMap((section) => {
          if (!section.rows.length) return [];
          return [
            {
              id: section.id,
              label: TARKOV_BOSS_HUB_SECTION_LABELS[section.id],
              items: section.rows.map((boss) => ({
                id: boss.id || boss.slug,
                label: boss.name,
                href: tarkovBossHref(boss.slug),
                status: "ready" as const,
              })),
            },
          ];
        }),
      };
    });
  }, [bossesQuery.data]);

  return (
    <TarkovThemed>
    <TarkovLiveWatchProvider>
    <TarkovGoonTrackerProvider>
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.topbarInner}>
          <div className={styles.topLeft}>
            <Link
              to={TARKOV_HOME_PATH}
              className={styles.brand}
              aria-label="逃离塔科夫"
            >
              <TarkovGameLogo />
            </Link>
            <TarkovRaidRoomHeaderLink />
            <TarkovLiveWatchStatus />
          </div>
          <nav className={styles.nav} aria-label="攻略栏目">
            {navItems.map((item) => {
              const extraHrefs = (item.groups ?? []).flatMap((g) =>
                g.items.map((link) => link.href),
              );
              const active = isTarkovTopNavActive(
                item.href,
                pathname,
                extraHrefs,
              );
              const bossMenu = item.id === "bosses";
              return (
                <div key={item.id} className={styles.navItem}>
                  <Link
                    to={item.href}
                    className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`}
                    aria-current={active ? "page" : undefined}
                    aria-haspopup={item.groups ? "menu" : undefined}
                  >
                    {item.label}
                    {item.groups ? <NavCaret /> : null}
                  </Link>
                  {item.groups ? (
                    <div className={styles.dropdown} role="menu">
                      {item.groups.map((group) => (
                        <div
                          key={group.id}
                          className={`${styles.dropCol} ${
                            bossMenu && group.id === "boss"
                              ? styles.dropColBosses
                              : ""
                          }`}
                        >
                          <p className={styles.dropHead}>{group.label}</p>
                          {group.items.map((link) =>
                            link.status === "soon" ? (
                              <span
                                key={link.id}
                                className={`${styles.dropLink} ${styles.dropLinkSoon}`}
                                aria-disabled="true"
                              >
                                {link.label}
                                <TarkovSoonMark status={link.status} />
                              </span>
                            ) : (
                              <Link
                                key={link.id}
                                to={link.href}
                                className={styles.dropLink}
                                role="menuitem"
                              >
                                {link.label}
                              </Link>
                            ),
                          )}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </nav>
          <div className={styles.topRight}>
            <TarkovGameModeSwitch />
            <form
              className={styles.topSearch}
              onSubmit={(event) => {
                event.preventDefault();
                const next = draft.trim();
                navigate(
                  next
                    ? `${TARKOV_HOME_PATH}?q=${encodeURIComponent(next)}`
                    : TARKOV_HOME_PATH,
                );
              }}
            >
              <input
                ref={searchRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="搜索…"
                aria-label="全站搜索攻略"
                autoComplete="off"
                enterKeyHint="search"
              />
              <kbd className={styles.topKbd}>/</kbd>
            </form>
            <div className={styles.tracker}>
              <TarkovMeHeaderLink />
            </div>
          </div>
        </div>
      </header>
      <div className={styles.body}>{children}</div>
    </div>
    </TarkovGoonTrackerProvider>
    </TarkovLiveWatchProvider>
    </TarkovThemed>
  );
}
