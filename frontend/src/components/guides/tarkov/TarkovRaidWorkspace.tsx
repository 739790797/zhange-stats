import { useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { TarkovGoonRoomNotice } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import {
  isTarkovRaidDockDesktop,
  TARKOV_RAID_DOCK_DESKTOP_MQ,
} from "@/lib/tarkovRaidDockPrefs";
import styles from "./TarkovRaidPrepPanel.module.css";

const SIDE_WIDTH_KEY = "zhange.tarkov.raidSideWidths";
const SIDE_WIDTH_DEFAULT = 20;
const SIDE_WIDTH_LEGACY_DEFAULT = 15;
const SIDE_WIDTH_MIN = 10;
const SIDE_WIDTH_MAX = 42;

function clampSideWidth(value: number): number {
  if (!Number.isFinite(value)) return SIDE_WIDTH_DEFAULT;
  return Math.min(SIDE_WIDTH_MAX, Math.max(SIDE_WIDTH_MIN, value));
}

function readSideWidths(): { left: number; right: number } {
  if (typeof localStorage === "undefined") {
    return { left: SIDE_WIDTH_DEFAULT, right: SIDE_WIDTH_DEFAULT };
  }
  try {
    const raw = JSON.parse(localStorage.getItem(SIDE_WIDTH_KEY) || "") as {
      left?: number;
      right?: number;
    };
    const left = Number(raw.left);
    const right = Number(raw.right);
    return {
      left:
        left === SIDE_WIDTH_LEGACY_DEFAULT
          ? SIDE_WIDTH_DEFAULT
          : clampSideWidth(left),
      right:
        right === SIDE_WIDTH_LEGACY_DEFAULT
          ? SIDE_WIDTH_DEFAULT
          : clampSideWidth(right),
    };
  } catch {
    return { left: SIDE_WIDTH_DEFAULT, right: SIDE_WIDTH_DEFAULT };
  }
}

type Props = {
  dockOpen: boolean;
  onToggleDock?: () => void;
  picking?: boolean;
  showDock?: boolean;
  /** 一键收起时隐藏左右侧栏。 */
  sidebarsOpen?: boolean;
  alerts?: ReactNode;
  belowBar?: ReactNode;
  title?: ReactNode;
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
  sidebarsOpen = true,
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
  const stageRef = useRef<HTMLDivElement>(null);
  const [leftPct, setLeftPct] = useState(() => readSideWidths().left);
  const [rightPct, setRightPct] = useState(() => readSideWidths().right);
  const [dragging, setDragging] = useState<"left" | "right" | null>(null);
  const [desktopDock, setDesktopDock] = useState(isTarkovRaidDockDesktop);
  useEffect(() => {
    const media = window.matchMedia(TARKOV_RAID_DOCK_DESKTOP_MQ);
    const sync = () => setDesktopDock(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  const dockShown = showDock && sidebarsOpen && (desktopDock || dockOpen);
  useEffect(() => {
    try {
      localStorage.setItem(
        SIDE_WIDTH_KEY,
        JSON.stringify({ left: leftPct, right: rightPct }),
      );
    } catch {
      /* 隐私模式写不进 */
    }
  }, [leftPct, rightPct]);

  const startResize = (side: "left" | "right", event: ReactPointerEvent<HTMLButtonElement>) => {
    const stage = stageRef.current;
    if (!stage) return;
    event.preventDefault();
    const rect = stage.getBoundingClientRect();
    const pointerId = event.pointerId;
    event.currentTarget.setPointerCapture(pointerId);
    setDragging(side);
    const move = (ev: PointerEvent) => {
      if (rect.width <= 0) return;
      const x = ev.clientX - rect.left;
      const pct =
        side === "left" ? (x / rect.width) * 100 : ((rect.width - x) / rect.width) * 100;
      const next = clampSideWidth(pct);
      if (side === "left") setLeftPct(next);
      else setRightPct(next);
    };
    const stop = () => {
      setDragging(null);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  };

  const hasBar = Boolean(title || meta || members || topActions);
  const stageStyle = {
    "--raid-overlay-left": `${leftPct}%`,
    "--raid-overlay-dock": `${rightPct}%`,
    "--raid-overlay-right": dockShown ? `calc(${rightPct}% + 8px)` : "10px",
  } as CSSProperties;
  return (
    <div
      ref={stageRef}
      className={styles.stage}
      data-dock={dockShown ? "open" : "closed"}
      data-sidebars={sidebarsOpen ? "open" : "closed"}
      data-pick={picking ? "true" : undefined}
      data-resizing={dragging || undefined}
      style={stageStyle}
    >
      {alerts}
      {hasBar ? (
        <div className={styles.topBar}>
          <div className={styles.roomId}>
            {title ? <h1 className={styles.roomTitle}>{title}</h1> : null}
            {meta ? <div className={styles.roomMeta}>{meta}</div> : null}
          </div>
          {members}
          {topActions ? (
            <div className={styles.topActions}>{topActions}</div>
          ) : null}
        </div>
      ) : null}
      {belowBar}
      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          {goonMapId ? <TarkovGoonRoomNotice mapId={goonMapId} /> : null}
          {showDock && onToggleDock && !desktopDock ? (
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
        {!picking && sidebarsOpen ? (
          <button
            type="button"
            className={`${styles.resizeHandle} ${styles.resizeLeft}`}
            aria-label="调整左侧栏宽度"
            data-dragging={dragging === "left" ? "true" : undefined}
            onPointerDown={(event) => startResize("left", event)}
          />
        ) : null}
        {showDock && dock ? (
          <aside
            id="tarkov-raid-dock"
            className={styles.dock}
            aria-label="任务列表"
          >
            {dock}
          </aside>
        ) : null}
        {dockShown ? (
          <button
            type="button"
            className={`${styles.resizeHandle} ${styles.resizeRight}`}
            aria-label="调整右侧栏宽度"
            data-dragging={dragging === "right" ? "true" : undefined}
            onPointerDown={(event) => startResize("right", event)}
          />
        ) : null}
      </div>
      {children}
    </div>
  );
}
