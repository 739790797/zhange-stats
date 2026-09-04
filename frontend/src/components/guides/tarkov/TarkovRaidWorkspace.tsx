import type { ReactNode } from "react";
import { TarkovGoonRoomNotice } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props = {
  dockOpen: boolean;
  onToggleDock?: () => void;
  picking?: boolean;
  showDock?: boolean;
  alerts?: ReactNode;
  belowBar?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  members?: ReactNode;
  topActions?: ReactNode;
  goonMapId?: string;
  mapToolbar?: ReactNode;
  map: ReactNode;
  dock?: ReactNode;
  children?: ReactNode;
};

export function TarkovRaidWorkspace({
  dockOpen,
  onToggleDock,
  picking = false,
  showDock = true,
  alerts,
  belowBar,
  title,
  meta,
  members,
  topActions,
  goonMapId,
  mapToolbar,
  map,
  dock,
  children,
}: Props) {
  return (
    <div
      className={styles.stage}
      data-dock={dockOpen ? "open" : "closed"}
      data-pick={picking ? "true" : undefined}
    >
      {alerts}
      <div className={styles.topBar}>
        <div className={styles.roomId}>
          <h1 className={styles.roomTitle}>{title}</h1>
          {meta ? <div className={styles.roomMeta}>{meta}</div> : null}
        </div>
        {members}
        {topActions ? (
          <div className={styles.topActions}>{topActions}</div>
        ) : null}
      </div>
      {belowBar}
      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          {goonMapId ? <TarkovGoonRoomNotice mapId={goonMapId} /> : null}
          {showDock && onToggleDock ? (
            <button
              type="button"
              className={styles.dockEdge}
              aria-expanded={dockOpen}
              aria-controls="tarkov-raid-dock"
              onClick={onToggleDock}
            >
              <span className={styles.srOnly}>
                {dockOpen ? "收起任务栏" : "展开任务栏"}
              </span>
              <span aria-hidden>{dockOpen ? "›" : "‹"}</span>
            </button>
          ) : null}
          {mapToolbar}
          <div className={styles.mapFill}>{map}</div>
        </div>
        {showDock && dock ? (
          <aside
            id="tarkov-raid-dock"
            className={styles.dock}
            aria-label="任务列表"
          >
            {dock}
          </aside>
        ) : null}
      </div>
      {children}
    </div>
  );
}
