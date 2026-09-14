import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovProfile } from "@/api/guidesApi";
import { TarkovCollectionPanel } from "@/components/guides/tarkov/TarkovCollectionPanel";
import { TarkovGameLogsPanel } from "@/components/guides/tarkov/TarkovGameLogsPanel";
import { TarkovHideoutPanel } from "@/components/guides/tarkov/TarkovHideoutPanel";
import { TarkovKeyPacksPanel } from "@/components/guides/tarkov/TarkovKeyPacksPanel";
import { TarkovProfilePanel } from "@/components/guides/tarkov/TarkovProfilePanel";
import { TarkovTaskManagerPanel } from "@/components/guides/tarkov/TarkovTaskManagerPanel";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  resolveTarkovMeTab,
  type TarkovMeTabId,
} from "@/lib/tarkovHomeNav";
import { useAuthStore } from "@/stores/authStore";
import {
  parseTarkovPmcFaction,
  persistTarkovPmcFaction,
} from "@/lib/tarkovPmcFaction";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovMePanel.module.css";

const TABS: Array<{ id: TarkovMeTabId; label: string }> = [
  { id: "profile", label: "个人资料" },
  { id: "tasks", label: "任务管理" },
  { id: "keys", label: "钥匙管理" },
  { id: "collection", label: "3×4收集" },
  { id: "hideout", label: "藏身处" },
  { id: "logs", label: "日志路径" },
];

export function TarkovMePanel() {
  const gameMode = useTarkovGameMode();
  const loggedIn = Boolean(useAuthStore((s) => s.user));
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = resolveTarkovMeTab(searchParams.get("tab"));
  const profileQuery = useQuery({
    queryKey: ["guides-tarkov-profile", gameMode],
    queryFn: fetchTarkovProfile,
    staleTime: 30_000,
    retry: 1,
    enabled: loggedIn,
  });

  useEffect(() => {
    const faction = parseTarkovPmcFaction(profileQuery.data?.pmc_faction);
    if (faction) persistTarkovPmcFaction(gameMode, faction);
  }, [profileQuery.data, gameMode]);

  const setTab = (id: TarkovMeTabId) => {
    const params = new URLSearchParams(searchParams);
    params.set("tab", id);
    if (id !== "hideout") {
      params.delete("station");
      params.delete("level");
    }
    if (id !== "keys") {
      params.delete("map");
      params.delete("page");
      params.delete("pageSize");
      params.delete("have");
    }
    if (id !== "keys" && id !== "tasks" && id !== "collection") {
      params.delete("q");
    }
    params.delete("kappa");
    params.delete("view");
    if (id !== "tasks") {
      params.delete("trader");
      params.delete("ready");
    }
    setSearchParams(params, { replace: true });
  };

  return (
    <div
      className={`${styles.stack}${tab === "collection" ? ` ${styles.stackFill}` : ""}`}
    >
      <div
        className={`${trade.chipBar} ${styles.tabs}`}
        role="tablist"
        aria-label="个人中心栏目"
      >
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`${trade.chipBtn} ${trade.chipAll}${tab === item.id ? ` ${trade.chipOn}` : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === "profile" ? <TarkovProfilePanel /> : null}
      {tab === "tasks" ? <TarkovTaskManagerPanel /> : null}
      {tab === "keys" ? <TarkovKeyPacksPanel /> : null}
      {tab === "collection" ? <TarkovCollectionPanel /> : null}
      {tab === "hideout" ? <TarkovHideoutPanel /> : null}
      {tab === "logs" ? <TarkovGameLogsPanel /> : null}
    </div>
  );
}
