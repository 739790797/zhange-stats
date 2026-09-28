import type { ReactNode } from "react";
import { logMapLabel } from "@/lib/tarkovGameLogs";
import { colorForUserId } from "@/lib/tarkovRaidPrep";
import {
  formatRaidRoomMemberActivity,
  formatRaidRoomOnlineLabel,
  raidRoomMemberActivity,
  type RaidRoomViewMapLike,
} from "@/lib/tarkovRaidRooms";
import styles from "./TarkovRaidRoomChannelRoster.module.css";

export type ChannelRosterMember = {
  user_id: number;
  display_name: string;
  is_host?: boolean;
  online?: boolean;
  clients?: readonly string[] | null;
};

type Phase = {
  kind?: string | null;
};

type Props = {
  title?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  corner?: ReactNode;
  members: readonly ChannelRosterMember[];
  viewMaps?: readonly RaidRoomViewMapLike[];
  phaseByUser?: ReadonlyMap<number, Phase>;
};

export function TarkovRaidRoomChannelRoster({
  title,
  meta,
  actions,
  corner,
  members,
  viewMaps,
  phaseByUser,
}: Props) {
  if (!members.length && !title && !actions && !corner) return null;
  const mapByUser = new Map(
    (viewMaps || []).map((row) => [row.user_id, (row.map_slug || "").trim()]),
  );
  return (
    <section className={styles.roster} aria-label="房间信息">
      {title || meta || corner ? (
        <div className={styles.head}>
          <div className={styles.headText}>
            {title ? <h2 className={styles.title}>{title}</h2> : null}
            {meta ? <div className={styles.meta}>{meta}</div> : null}
          </div>
          {corner ? <div className={styles.corner}>{corner}</div> : null}
        </div>
      ) : null}
      {actions ? <div className={styles.actions}>{actions}</div> : null}
      {members.length ? (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">成员</th>
              <th scope="col">地图</th>
              <th scope="col">状态</th>
            </tr>
          </thead>
          <tbody>
            {members.map((row) => {
              const phase = phaseByUser?.get(row.user_id);
              const status = raidRoomMemberActivity({
                online: row.online,
                kind: phase?.kind,
              });
              const memberMapId = mapByUser.get(row.user_id) || "";
              const memberMapLabel = memberMapId ? logMapLabel(memberMapId) : "";
              return (
                <tr key={row.user_id} data-status={status}>
                  <td>
                    <span className={styles.name}>
                      <span
                        className={styles.dot}
                        style={{ background: colorForUserId(row.user_id) }}
                      />
                      {row.is_host ? "⭐" : ""}
                      {row.display_name}
                      <span className={styles.presence}>
                        {formatRaidRoomOnlineLabel(row.online, row.clients)}
                      </span>
                    </span>
                  </td>
                  <td>{memberMapLabel || "—"}</td>
                  <td>{formatRaidRoomMemberActivity(status)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
