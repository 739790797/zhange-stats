import { Modal } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Dayjs } from "dayjs";
import { apiError } from "@/shared/api/apiError";
import type { TarkovLogSessionStub } from "@/features/guides/tarkov/model/tarkovGameLogs";
import { useTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import { TARKOV_MAPS } from "@/features/guides/tarkov/model/tarkovHomeNav";
import {
  accountArchiveFromFloor,
  launchCountByDay,
  logSyncCalendarLaunches,
  raidArchiveAllowed,
  raidArchiveFrom,
  type LogSyncCalendarLaunch,
  type LogSyncCalendarRaid,
} from "@/features/guides/tarkov/model/tarkovLogSyncCalendar";
import { defaultLogSyncRange } from "@/features/guides/tarkov/model/tarkovLogSyncRange";
import type { TarkovLogSyncRange } from "@/features/guides/tarkov/model/tarkovLogSyncRange";
import { useTarkovLogSync } from "@/features/guides/tarkov/hooks/useTarkovLiveWatch";
import { compareBeijingClock, formatBeijing, nowBeijing, parseBeijing } from "@/shared/lib/time";
import styles from "./TarkovLogSyncRangeModal.module.css";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

function clockOnly(at: string | undefined): string {
  const text = (at || "").trim();
  if (!text) return "";
  const formatted = formatBeijing(text, "HH:mm:ss");
  return formatted === "—" ? "" : formatted;
}

function raidTimeSpan(start?: string, end?: string): string {
  const opened = clockOnly(start);
  const closed = clockOnly(end);
  if (opened && closed) return `${opened} ~ ${closed}`;
  return opened || closed || "—";
}

function raidMapIcon(raid: { mapId?: string; mapLabel: string }): string {
  const id = raid.mapId === "night-factory" ? "factory" : raid.mapId || "";
  const byId = id ? TARKOV_MAPS.find((row) => row.id === id) : undefined;
  if (byId?.icon) return byId.icon;
  return TARKOV_MAPS.find((row) => row.label === raid.mapLabel)?.icon || "";
}

function RaidMapName({ raid }: { raid: { mapId?: string; mapLabel: string } }) {
  const icon = raidMapIcon(raid);
  return (
    <span className={styles.mapCell}>
      {icon ? (
        <svg className={styles.mapIcon} viewBox="0 0 24 24" width="18" height="18" aria-hidden>
          <path d={icon} fill="currentColor" />
        </svg>
      ) : null}
      <span>{raid.mapLabel}</span>
    </span>
  );
}

type Props = {
  open: boolean;
  sessions: readonly TarkovLogSessionStub[];
  onCancel: () => void;
  onConfirm: (range: TarkovLogSyncRange) => void;
};

type ArchivePick = {
  key: string;
  at: string;
  /** 被归档那一局的开始时间，用来藏起更早的按钮。 */
  raidAt: string;
  /** 这一局所在的日历日。 */
  day: string;
  approximate: boolean;
  profileId: string;
  sessionMode: string;
  version: string;
  label: string;
};

function monthCells(month: Dayjs): Array<Dayjs | null> {
  const start = month.startOf("month");
  const lead = (start.day() + 6) % 7;
  const cells: Array<Dayjs | null> = [];
  for (let i = 0; i < lead; i += 1) cells.push(null);
  const days = start.daysInMonth();
  for (let day = 1; day <= days; day += 1) cells.push(start.date(day));
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export function TarkovLogSyncRangeModal({
  open,
  sessions,
  onCancel,
  onConfirm,
}: Props) {
  const gameMode = useTarkovGameMode();
  const logSync = useTarkovLogSync();
  const launches = useMemo(
    () => logSyncCalendarLaunches(sessions, gameMode),
    [gameMode, sessions],
  );
  const counts = useMemo(() => launchCountByDay(launches), [launches]);
  const [month, setMonth] = useState(() => nowBeijing().startOf("month"));
  const [selectedDay, setSelectedDay] = useState("");
  const [floorAt, setFloorAt] = useState("");
  const [archive, setArchive] = useState<ArchivePick | null>(null);
  const [archiveNote, setArchiveNote] = useState("");
  const [resolvedEnds, setResolvedEnds] = useState<Record<string, string>>({});
  const [resolvingKey, setResolvingKey] = useState("");
  const chooseSeq = useRef(0);
  const readQuestFloor = logSync.readQuestFloor;

  useEffect(() => {
    if (!open) return;
    const latest = launches[launches.length - 1]?.startedAt;
    const parsed = latest ? parseBeijing(latest) : nowBeijing();
    setMonth((parsed.isValid() ? parsed : nowBeijing()).startOf("month"));
    setSelectedDay("");
    setArchive(null);
    setArchiveNote("");
    setResolvedEnds({});
    setResolvingKey("");
    let cancelled = false;
    void readQuestFloor().then((at) => {
      if (!cancelled) setFloorAt(at || "");
    });
    return () => {
      cancelled = true;
    };
  }, [launches, open, readQuestFloor]);

  const cells = useMemo(() => monthCells(month), [month]);
  const dayLaunches = useMemo(
    () => launches.filter((row) => row.day === selectedDay),
    [launches, selectedDay],
  );
  const accountArchive = useMemo(
    () => accountArchiveFromFloor(launches, floorAt),
    [floorAt, launches],
  );
  const shownArchive = archive
    ? { day: archive.day, raidAt: archive.raidAt, raidKey: archive.key, draft: true }
    : accountArchive
      ? { ...accountArchive, draft: false }
      : null;

  function clearArchive() {
    setArchive(null);
    setArchiveNote("");
  }

  async function cancelShownArchive(persisted: boolean) {
    clearArchive();
    if (!persisted) return;
    try {
      await logSync.releaseQuestFloor();
      setFloorAt("");
    } catch (error) {
      setArchiveNote(apiError(error, "取消归档失败"));
    }
  }

  async function chooseRaid(launch: LogSyncCalendarLaunch, raid: LogSyncCalendarRaid) {
    const pickKey = `${launch.folder}|${raid.key}`;
    const seq = ++chooseSeq.current;
    let endedAt = resolvedEnds[pickKey] || raid.endedAt;
    if (!endedAt) {
      setResolvingKey(pickKey);
      try {
        endedAt = await logSync.resolveRaidEndedAt(launch.folder, raid);
      } finally {
        if (seq === chooseSeq.current) setResolvingKey("");
      }
      if (seq !== chooseSeq.current) return;
      if (endedAt) {
        setResolvedEnds((current) => ({ ...current, [pickKey]: endedAt }));
      }
    }
    if (seq !== chooseSeq.current) return;
    const floor = raidArchiveFrom({ ...raid, endedAt });
    if (!floor || !raidArchiveAllowed(floor.at, floorAt)) {
      setArchiveNote("这一局不晚于已记下的进度起点，不能再往前归档。");
      return;
    }
    const when = formatBeijing(raid.startedAt || launch.startedAt);
    setArchiveNote("");
    setArchive({
      key: pickKey,
      at: floor.at,
      raidAt: raid.startedAt || launch.startedAt,
      day: launch.day,
      approximate: floor.approximate,
      profileId: launch.profileId,
      sessionMode: launch.sessionMode,
      version: launch.version,
      label: `${raid.mapLabel} · ${when}`,
    });
  }

  return (
    <Modal
      title="同步日志"
      open={open}
      onCancel={onCancel}
      footer={
        <div className={styles.footer}>
          <button
            type="button"
            className={styles.ok}
            onClick={() =>
              onConfirm({
                ...defaultLogSyncRange(),
                restart: Boolean(archive),
                breakpoint: archive
                  ? {
                      at: archive.at,
                      profileId: archive.profileId,
                      sessionMode: archive.sessionMode,
                      version: archive.version,
                    }
                  : undefined,
              })
            }
          >
            开始同步
          </button>
        </div>
      }
      width={840}
      destroyOnClose
      classNames={{ body: styles.body }}
    >
      <div className={styles.calHead}>
        <button
          type="button"
          className={styles.nav}
          aria-label="上个月"
          onClick={() => setMonth((current) => current.subtract(1, "month"))}
        >
          ‹
        </button>
        <span className={styles.month}>{month.format("YYYY年M月")}</span>
        <button
          type="button"
          className={styles.nav}
          aria-label="下个月"
          onClick={() => setMonth((current) => current.add(1, "month"))}
        >
          ›
        </button>
      </div>
      <div className={styles.week} aria-hidden>
        {WEEKDAYS.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      <div className={styles.grid} role="grid" aria-label="启动日历">
        {cells.map((day, index) => {
          if (!day) return <span key={`empty-${index}`} className={styles.empty} />;
          const key = day.format("YYYY-MM-DD");
          const count = counts.get(key) || 0;
          const selected = key === selectedDay;
          const prestigeDay = shownArchive?.day === key;
          const archivedDay = Boolean(
            shownArchive && count > 0 && key < shownArchive.day,
          );
          const mark = prestigeDay ? "转生日" : archivedDay ? "已归档" : count ? `启动${count}次` : "";
          return (
            <button
              key={key}
              type="button"
              role="gridcell"
              className={`${styles.day}${count ? ` ${styles.dayOn}` : ""}${
                selected ? ` ${styles.daySelected}` : ""
              }${archivedDay ? ` ${styles.dayArchived}` : ""}`}
              disabled={!count}
              aria-selected={selected}
              aria-label={
                prestigeDay
                  ? `${key}，转生日`
                  : archivedDay
                    ? `${key}，已归档`
                    : count
                      ? `${key}，启动 ${count} 次`
                      : `${key}，没有启动`
              }
              onClick={() => setSelectedDay((current) => (current === key ? "" : key))}
            >
              <span className={styles.dayNum}>{day.date()}</span>
              {mark ? <span className={styles.dayCount}>{mark}</span> : null}
            </button>
          );
        })}
      </div>
      {!launches.length ? (
        <p className={styles.meta}>这些日志里还没有当前角色的启动记录。</p>
      ) : null}
      {selectedDay && dayLaunches.length ? (
        <div className={styles.detail}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>第几次启动</th>
                <th>地图</th>
                <th>时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {dayLaunches.map((launch) => {
                const rows = launch.raids.length ? launch.raids : [null];
                return rows.map((raid, raidIndex) => {
                  const pickKey = raid ? `${launch.folder}|${raid.key}` : "";
                  const endedAt = raid ? resolvedEnds[pickKey] || raid.endedAt : "";
                  const knownEnd = Boolean(endedAt);
                  const floor = raid && knownEnd ? raidArchiveFrom({ ...raid, endedAt }) : null;
                  const allowed = !knownEnd || (floor ? raidArchiveAllowed(floor.at, floorAt) : false);
                  const picked = Boolean(pickKey) && archive?.key === pickKey;
                  const raidAt = raid?.startedAt || launch.startedAt;
                  const beforeArchive = Boolean(
                    shownArchive &&
                      raid &&
                      pickKey !== shownArchive.raidKey &&
                      compareBeijingClock(raidAt, shownArchive.raidAt) < 0,
                  );
                  const alreadyOnAccount =
                    Boolean(pickKey) &&
                    !archive &&
                    accountArchive?.raidKey === pickKey;
                  return (
                    <tr key={raid ? pickKey : `${launch.folder}-empty`}>
                      {raidIndex === 0 ? (
                        <td rowSpan={rows.length}>第 {launch.index} 次启动</td>
                      ) : null}
                      <td>{raid ? <RaidMapName raid={raid} /> : "未进入战局"}</td>
                      <td>{raidTimeSpan(raid?.startedAt || launch.startedAt, endedAt)}</td>
                      <td>
                        {raid && !beforeArchive ? (
                          <button
                            type="button"
                            className={`${styles.archive}${
                              picked || alreadyOnAccount ? ` ${styles.archiveOn}` : ""
                            }`}
                            disabled={
                              (!picked && !alreadyOnAccount && !allowed) ||
                              resolvingKey === pickKey
                            }
                            title={
                              picked || alreadyOnAccount
                                ? "取消后，同步不再跳过该局及更早的日志"
                                : allowed
                                  ? "该局及之前的日志不参与同步"
                                  : "这次不晚于已记下的进度起点"
                            }
                            onClick={() => {
                              if (picked) {
                                clearArchive();
                                return;
                              }
                              if (alreadyOnAccount) {
                                void cancelShownArchive(true);
                                return;
                              }
                              void chooseRaid(launch, raid);
                            }}
                          >
                            {resolvingKey === pickKey
                              ? "正在读取…"
                              : picked || alreadyOnAccount
                                ? "取消归档"
                                : "转生归档"}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                });
              })}
            </tbody>
          </table>
          {archive ? (
            <p className={styles.meta}>
              转生归档：{archive.label}。
              {archive.approximate
                ? "这一局还没有结束时间，将从开局的下一秒起解析，局内任务可能仍会计入。"
                : "这一局以及更早的日志不写回。"}
            </p>
          ) : null}
          {archiveNote ? <p className={styles.meta}>{archiveNote}</p> : null}
        </div>
      ) : null}
    </Modal>
  );
}
