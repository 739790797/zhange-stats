import { tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { colorForUserId } from "@/lib/tarkovRaidPrep";

export { tarkovRaidRoomHref, colorForUserId };

export const RAID_ROOM_OTHER_FLOOR_OPACITY = 0.28;

export type RaidRoomClaimLike = {
  task_id: string;
  user_id: number;
  display_name: string;
};

export type RaidRoomMarkLike = {
  id: number;
  kind: string;
  floor?: string | null;
  x: number;
  z: number;
  x2?: number | null;
  z2?: number | null;
  author_user_id: number;
  author_display_name?: string;
};

export type RaidRoomMemberLike = {
  user_id: number;
  display_name: string;
  is_host?: boolean;
  in_room?: boolean;
  online?: boolean;
};

export type RaidRoomSnapshotLike = {
  public_id: string;
  title?: string;
  map_slug: string;
  status: string;
  host_user_id: number;
  host_display_name: string;
  expire_at?: string | null;
  can_edit?: boolean;
  members?: RaidRoomMemberLike[];
  claims?: RaidRoomClaimLike[];
  marks?: RaidRoomMarkLike[];
};

export type RaidRoomClaimGroup = {
  taskId: string;
  userIds: number[];
  names: string[];
};

export function roomDisplayTitle(
  room: { title?: string | null; host_display_name?: string | null },
  mapLabel: string,
): string {
  const title = (room.title || "").trim();
  if (title) return title;
  const host = (room.host_display_name || "").trim() || "房间";
  return `${host} 的 ${mapLabel}`;
}

export function remainMs(
  expireAt: string | null | undefined,
  nowMs: number,
): number {
  if (!expireAt) return 0;
  const stamp = Date.parse(String(expireAt).replace(" ", "T"));
  if (!Number.isFinite(stamp)) return 0;
  return Math.max(0, stamp - nowMs);
}

export function formatRoomRemain(ms: number): string {
  const sec = Math.floor(ms / 1000);
  if (sec <= 0) return "已到期";
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  if (hours >= 1) return `剩余 ${hours} 小时 ${minutes} 分`;
  if (minutes >= 1) return `剩余 ${minutes} 分钟`;
  return "剩余不到 1 分钟";
}

export function groupClaimsByTask(
  claims: RaidRoomClaimLike[] | null | undefined,
): RaidRoomClaimGroup[] {
  const order: string[] = [];
  const groups = new Map<string, RaidRoomClaimGroup>();
  for (const claim of claims || []) {
    const taskId = String(claim.task_id || "").trim();
    if (!taskId) continue;
    let group = groups.get(taskId);
    if (!group) {
      group = { taskId, userIds: [], names: [] };
      groups.set(taskId, group);
      order.push(taskId);
    }
    if (!group.userIds.includes(claim.user_id)) {
      group.userIds.push(claim.user_id);
      group.names.push((claim.display_name || "").trim() || `用户${claim.user_id}`);
    }
  }
  return order.map((id) => groups.get(id)!);
}

export function claimedTaskIds(
  claims: RaidRoomClaimLike[] | null | undefined,
): string[] {
  return groupClaimsByTask(claims).map((row) => row.taskId);
}

export function markMatchesFloor(
  mark: { floor?: string | null },
  floor: string,
): boolean {
  return (mark.floor || "") === (floor || "");
}

export function applyRoomWsEvent<T extends RaidRoomSnapshotLike>(
  current: T | null,
  event: {
    event?: string;
    snapshot?: T;
    online_user_ids?: number[];
  },
): T | null {
  const online = event.online_user_ids;
  const withPresence = (room: T): T => {
    if (!online) return room;
    const ids = new Set(online);
    return {
      ...room,
      members: (room.members || []).map((row) => ({
        ...row,
        online: ids.has(row.user_id),
      })),
    };
  };
  if (event.snapshot) return withPresence(event.snapshot);
  if (event.event === "presence" && current) return withPresence(current);
  return current;
}
