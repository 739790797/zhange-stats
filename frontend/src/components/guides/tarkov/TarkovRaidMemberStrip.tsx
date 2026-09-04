import {
  formatRaidRoomMemberChipLine,
  raidRoomMemberRegionLabel,
} from "@/lib/tarkovRaidRooms";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidMemberChip = {
  user_id: number;
  display_name: string;
  is_host?: boolean;
  online?: boolean;
};

export type RaidMemberPhase = {
  kind?: string | null;
  mapLabel?: string | null;
  mapId?: string | null;
};

type Props = {
  members: readonly RaidMemberChip[];
  phaseByUser?: ReadonlyMap<number, RaidMemberPhase>;
};

export function TarkovRaidMemberStrip({ members, phaseByUser }: Props) {
  if (!members.length) return null;
  return (
    <div className={styles.members} aria-label="房间成员">
      {members.map((row) => {
        const phase = phaseByUser?.get(row.user_id);
        const region = raidRoomMemberRegionLabel({
          kind: phase?.kind,
          mapLabel: phase?.mapLabel,
          mapId: phase?.mapId,
        });
        const chipLine = formatRaidRoomMemberChipLine({
          name: row.display_name,
          isHost: row.is_host,
          online: row.online,
          kind: phase?.kind,
          mapLabel: phase?.mapLabel,
          mapId: phase?.mapId,
        });
        return (
          <span
            key={row.user_id}
            className={styles.memberChip}
            data-online={row.online ? "true" : "false"}
            data-phase={phase?.kind || ""}
            title={chipLine}
          >
            <span className={styles.memberName}>
              {row.is_host ? "⭐" : ""}
              {row.display_name}
            </span>
            <span
              className={styles.memberOnline}
              data-on={row.online ? "true" : "false"}
            >
              {row.online ? "在线" : "离线"}
            </span>
            {region ? (
              <span className={styles.memberRegion}>{region}</span>
            ) : null}
          </span>
        );
      })}
    </div>
  );
}
