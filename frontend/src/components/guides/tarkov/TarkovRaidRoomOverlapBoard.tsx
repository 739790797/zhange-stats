import { Tooltip } from "antd";
import { useMemo, useState, type ReactNode } from "react";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { colorForUserId, type RaidPrepMapOption } from "@/lib/tarkovRaidPrep";
import {
  formatRaidRoomOverlapCell,
  raidRoomOverlapPeopleLabel,
  raidRoomOverlapTasksForUser,
  sortRaidRoomMapOverlap,
  type RaidRoomMapOverlapLike,
  type RaidRoomMemberProgressLike,
} from "@/lib/tarkovRaidRooms";
import styles from "./TarkovRaidRoomOverlapBoard.module.css";

type MemberLike = {
  user_id: number;
  display_name: string;
};

type Props = {
  rows: readonly RaidRoomMapOverlapLike[];
  members: readonly MemberLike[];
  progress?: readonly RaidRoomMemberProgressLike[];
  mapOptions: readonly RaidPrepMapOption[];
  isHost: boolean;
  picking?: boolean;
  currentMapSlug?: string;
  onPickMap?: (mapSlug: string) => void;
};

function OverlapThumb({ slug }: { slug: string }) {
  const [broken, setBroken] = useState(false);
  const src = tarkovMapThumbUrl(slug);
  if (!src || broken) {
    return <span className={styles.thumb} aria-hidden />;
  }
  return (
    <img
      className={styles.thumb}
      src={src}
      alt=""
      width={36}
      height={24}
      onError={() => setBroken(true)}
    />
  );
}

function cellFor(row: RaidRoomMapOverlapLike, userId: number) {
  return (row.cells || []).find((cell) => cell.user_id === userId);
}

function shortName(name: string): string {
  const text = (name || "").trim() || "成员";
  return text.length > 4 ? `${text.slice(0, 4)}…` : text;
}

function CountTip({
  tasks,
  uploaded,
  children,
}: {
  tasks: { id: string; name: string }[];
  uploaded: boolean;
  children: ReactNode;
}) {
  const title = !uploaded
    ? "未同步"
    : tasks.length
      ? (
          <ul className={styles.tipList}>
            {tasks.map((task) => (
              <li key={task.id}>{task.name || task.id}</li>
            ))}
          </ul>
        )
      : "没有进行中的本图任务";
  return (
    <Tooltip
      title={title}
      mouseEnterDelay={0.08}
      mouseLeaveDelay={0.08}
      placement="top"
      zIndex={1200}
      overlayClassName={styles.tip}
      getPopupContainer={() => document.body}
    >
      {children}
    </Tooltip>
  );
}

export function TarkovRaidRoomOverlapBoard({
  rows,
  members,
  progress = [],
  mapOptions,
  isHost,
  picking = false,
  currentMapSlug = "",
  onPickMap,
}: Props) {
  const labelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const option of mapOptions) map.set(option.id, option.label);
    return map;
  }, [mapOptions]);
  const ranked = useMemo(() => {
    const source =
      rows.length > 0
        ? rows
        : mapOptions.map((option) => ({
            map_slug: option.id,
            with_tasks_count: 0,
            synced_count: 0,
            occupant_count: members.length,
            cells: members.map((member) => ({
              user_id: member.user_id,
              count: 0,
              uploaded: false,
            })),
          }));
    return sortRaidRoomMapOverlap(
      source,
      mapOptions.map((item) => item.id),
    );
  }, [mapOptions, members, rows]);
  const unsynced = useMemo(
    () =>
      members.filter((row) => {
        const hit = progress.find((item) => item.user_id === row.user_id);
        return !hit?.uploaded;
      }),
    [members, progress],
  );

  return (
    <div className={styles.board}>
      {!rows.length ? (
        <p className={styles.syncNote}>任务目录尚未同步，数字暂不可用。</p>
      ) : null}
      {unsynced.length ? (
        <p className={styles.syncNote}>
          未同步：{unsynced.map((row) => row.display_name || "成员").join("、")}
        </p>
      ) : null}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">地图</th>
              {members.map((row) => (
                <th
                  key={row.user_id}
                  className={styles.userCol}
                  title={row.display_name}
                >
                  <span
                    className={styles.dot}
                    style={{ background: colorForUserId(row.user_id) }}
                    aria-hidden
                  />
                  {shortName(row.display_name)}
                </th>
              ))}
              <th scope="col" className={styles.peopleHead}>
                有任务人数
              </th>
              {isHost && onPickMap ? <th scope="col" /> : null}
            </tr>
          </thead>
          <tbody>
            {ranked.map((row) => {
              const label = labelById.get(row.map_slug) || row.map_slug;
              return (
                <tr
                  key={row.map_slug}
                  className={`${styles.row}${
                    currentMapSlug && row.map_slug === currentMapSlug
                      ? ` ${styles.rowCurrent}`
                      : ""
                  }`}
                >
                  <th scope="row">
                    <div className={styles.mapCell}>
                      <OverlapThumb slug={row.map_slug} />
                      <span className={styles.mapName}>{label}</span>
                    </div>
                  </th>
                  {members.map((member) => {
                    const cell = cellFor(row, member.user_id);
                    const text = formatRaidRoomOverlapCell(cell);
                    const hit = Boolean(cell?.uploaded && cell.count > 0);
                    const tasks = raidRoomOverlapTasksForUser(
                      row,
                      member.user_id,
                    ).map((task) => ({
                      id: task.id,
                      name: task.name || task.id,
                    }));
                    return (
                      <td key={member.user_id} className={styles.userCol}>
                        <CountTip
                          tasks={tasks}
                          uploaded={Boolean(cell?.uploaded)}
                        >
                          <span
                            className={`${styles.countWrap} ${styles.count} ${
                              hit ? styles.countHit : styles.countMuted
                            }`}
                          >
                            {text}
                          </span>
                        </CountTip>
                      </td>
                    );
                  })}
                  <td className={styles.peopleCell}>
                    {raidRoomOverlapPeopleLabel(row.with_tasks_count)}
                  </td>
                  {isHost && onPickMap ? (
                    <td>
                      <button
                        type="button"
                        className={styles.pickBtn}
                        disabled={picking}
                        onClick={() => onPickMap(row.map_slug)}
                      >
                        {currentMapSlug && row.map_slug === currentMapSlug
                          ? "继续这张图"
                          : "选这张图"}
                      </button>
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
