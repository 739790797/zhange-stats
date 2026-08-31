import { useSearchParams } from "react-router-dom";
import { TarkovGameLogsPanel } from "@/components/guides/tarkov/TarkovGameLogsPanel";
import { TarkovKeyPacksPanel } from "@/components/guides/tarkov/TarkovKeyPacksPanel";
import { TarkovTaskManagerPanel } from "@/components/guides/tarkov/TarkovTaskManagerPanel";
import {
  resolveTarkovMeTab,
  type TarkovMeTabId,
} from "@/lib/tarkovHomeNav";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovMePanel.module.css";

const TABS: Array<{ id: TarkovMeTabId; label: string }> = [
  { id: "tasks", label: "任务管理" },
  { id: "keys", label: "钥匙管理" },
  { id: "logs", label: "日志路径" },
];

export function TarkovMePanel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = resolveTarkovMeTab(searchParams.get("tab"));

  const setTab = (id: TarkovMeTabId) => {
    const params = new URLSearchParams(searchParams);
    params.set("tab", id);
    if (id !== "keys") {
      params.delete("map");
      params.delete("have");
      params.delete("page");
      params.delete("pageSize");
    }
    if (id !== "keys" && id !== "tasks") {
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
    <div className={styles.stack}>
      <div className={trade.chipBar} role="tablist" aria-label="个人中心栏目">
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
      {tab === "tasks" ? <TarkovTaskManagerPanel /> : null}
      {tab === "keys" ? <TarkovKeyPacksPanel /> : null}
      {tab === "logs" ? <TarkovGameLogsPanel /> : null}
    </div>
  );
}
