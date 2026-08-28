import { tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { colorForUserId } from "@/lib/tarkovRaidPrep";

export { tarkovRaidRoomHref, colorForUserId };

export const RAID_ROOM_SLOT_IDS = ["1", "2", "3", "4", "5"] as const;

export function parseRaidRoomPublicId(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const fromPath = text.match(/raid-prep\/rooms\/([a-zA-Z0-9]+)/i);
  const candidate = (fromPath?.[1] || text).trim();
  if (/^[1-5]$/.test(candidate)) return candidate;
  return "";
}

/** WS 断线后指数退避，上限 30 秒。 */
export function raidRoomWsRetryDelayMs(attempt: number): number {
  const n = Number.isFinite(attempt) ? Math.max(0, Math.trunc(attempt)) : 0;
  return Math.min(30_000, 1000 * 2 ** n);
}

export const RAID_ROOM_OTHER_FLOOR_OPACITY = 0.28;

export type RaidRoomClaimLike = {
  task_id: string;
  user_id: number;
  display_name: string;
};

export type RaidRoomKeyBringLike = {
  item_id: string;
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
  points?: number[][] | null;
  author_user_id: number;
  author_display_name?: string;
};

export type TarkovMapDrawMode = "pan" | "pen" | "erase";

export type StrokePoint = {
  x: number;
  z: number;
};

export type RaidRoomDraftStroke = {
  userId?: number;
  floor: string;
  points: StrokePoint[];
  color: string;
};

export const STROKE_MAX_POINTS = 160;
export const STROKE_MIN_DIST = 1.6;

export type RaidRoomMemberLike = {
  user_id: number;
  display_name: string;
  is_host?: boolean;
  in_room?: boolean;
  online?: boolean;
};

export type RaidRoomOccupantLike = {
  user_id: number;
  display_name: string;
  is_host?: boolean;
  online?: boolean;
};

export type RaidRoomSnapshotLike = {
  public_id: string;
  title?: string;
  map_slug: string;
  host_user_id?: number | null;
  host_display_name: string;
  can_edit?: boolean;
  is_host?: boolean;
  is_member?: boolean;
  occupants?: RaidRoomOccupantLike[];
  members?: RaidRoomMemberLike[];
  claims?: RaidRoomClaimLike[];
  key_brings?: RaidRoomKeyBringLike[];
  marks?: RaidRoomMarkLike[];
};

export function withRaidRoomViewerFlags<T extends RaidRoomSnapshotLike>(
  room: T,
  userId: number | null | undefined,
): T & { is_host: boolean; is_member: boolean; can_edit: boolean } {
  const seated = (room.occupants || []).some((row) => row.user_id === userId)
    || (room.members || []).some(
      (row) => row.user_id === userId && row.in_room !== false,
    );
  const is_host = userId != null && room.host_user_id === userId;
  return {
    ...room,
    is_host,
    is_member: seated,
    can_edit: seated && Boolean((room.map_slug || "").trim()),
  };
}

export type RaidRoomClaimGroup = {
  taskId: string;
  userIds: number[];
  names: string[];
};

export type RaidRoomKeyBringGroup = {
  itemId: string;
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

export type RaidLobbyRoomLike = {
  is_member?: boolean;
  host_user_id?: number | null;
  member_count?: number | null;
  max_members?: number | null;
};

/** 大厅条目：自己所在 / 自己主持 / 尚未加入（含已满，供列表灰显）。 */
export function partitionRaidLobbyRooms<T extends RaidLobbyRoomLike>(
  items: T[],
  userId?: number | null,
): { mine: T[]; hosted: T[]; joinable: T[] } {
  const mine: T[] = [];
  const hosted: T[] = [];
  const joinable: T[] = [];
  for (const room of items) {
    if (room.is_member) mine.push(room);
    else joinable.push(room);
    if (userId != null && room.host_user_id === userId) hosted.push(room);
  }
  return { mine, hosted, joinable };
}

export function raidRoomIsFull(room: RaidLobbyRoomLike): boolean {
  const max = Number(room.max_members) || 0;
  const count = Number(room.member_count) || 0;
  return max > 0 && count >= max;
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

export function groupKeyBringsByItem(
  brings: readonly RaidRoomKeyBringLike[] | null | undefined,
): RaidRoomKeyBringGroup[] {
  const order: string[] = [];
  const groups = new Map<string, RaidRoomKeyBringGroup>();
  for (const row of brings || []) {
    const itemId = String(row.item_id || "").trim();
    if (!itemId) continue;
    let group = groups.get(itemId);
    if (!group) {
      group = { itemId, userIds: [], names: [] };
      groups.set(itemId, group);
      order.push(itemId);
    }
    if (!group.userIds.includes(row.user_id)) {
      group.userIds.push(row.user_id);
      group.names.push((row.display_name || "").trim() || `用户${row.user_id}`);
    }
  }
  return order.map((id) => groups.get(id)!);
}

export function userBroughtKey(
  brings: readonly RaidRoomKeyBringLike[] | null | undefined,
  itemId: string,
  userId: number | null | undefined,
): boolean {
  if (userId == null) return false;
  const id = String(itemId || "").trim();
  if (!id) return false;
  return (brings || []).some(
    (row) => row.user_id === userId && String(row.item_id || "").trim() === id,
  );
}

export function formatKeyBringHint(
  names: readonly string[],
  options?: { canToggle?: boolean },
): string {
  const canToggle = options?.canToggle !== false;
  if (!names.length) {
    return canToggle ? "点击声明我带了这把钥匙" : "还没人声明带这把钥匙";
  }
  const who =
    names.length === 1
      ? `${names[0]}带了这把钥匙`
      : `${names.join("、")}带了这把钥匙`;
  return `${who}。`;
}

export function claimedTaskIds(
  claims: RaidRoomClaimLike[] | null | undefined,
): string[] {
  return groupClaimsByTask(claims).map((row) => row.taskId);
}

/** 当前用户自己勾选的任务，不含队友勾选。 */
export function claimTaskIdsForUser(
  claims: RaidRoomClaimLike[] | null | undefined,
  userId: number | null | undefined,
): string[] {
  if (userId == null) return [];
  const out: string[] = [];
  const seen = new Set<string>();
  for (const claim of claims || []) {
    if (claim.user_id !== userId) continue;
    const taskId = String(claim.task_id || "").trim();
    if (!taskId || seen.has(taskId)) continue;
    seen.add(taskId);
    out.push(taskId);
  }
  return out;
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
  userId?: number | null,
): (T & { is_host: boolean; is_member: boolean; can_edit: boolean }) | null {
  const online = event.online_user_ids;
  const withPresence = (room: T) => {
    if (!online) return withRaidRoomViewerFlags(room, userId);
    const ids = new Set(online);
    return withRaidRoomViewerFlags(
      {
        ...room,
        occupants: (room.occupants || []).map((row) => ({
          ...row,
          online: ids.has(row.user_id),
        })),
        members: (room.members || []).map((row) => ({
          ...row,
          online: ids.has(row.user_id),
        })),
      },
      userId,
    );
  };
  if (event.snapshot) return withPresence(event.snapshot);
  if (event.event === "presence" && current) return withPresence(current);
  return current ? withRaidRoomViewerFlags(current, userId) : null;
}

export function roundStrokeCoord(value: number): number {
  return Math.round(value * 100) / 100;
}

export function parseStrokePoints(raw: unknown): StrokePoint[] {
  if (!Array.isArray(raw)) return [];
  const points: StrokePoint[] = [];
  for (const item of raw) {
    if (Array.isArray(item) && item.length >= 2) {
      const x = Number(item[0]);
      const z = Number(item[1]);
      if (Number.isFinite(x) && Number.isFinite(z)) points.push({ x, z });
      continue;
    }
    if (item && typeof item === "object") {
      const rec = item as { x?: unknown; z?: unknown };
      const x = Number(rec.x);
      const z = Number(rec.z);
      if (Number.isFinite(x) && Number.isFinite(z)) points.push({ x, z });
    }
  }
  return points;
}

export function simplifyStroke(
  points: StrokePoint[],
  minDist = STROKE_MIN_DIST,
  maxPoints = STROKE_MAX_POINTS,
): StrokePoint[] {
  if (!points.length) return [];
  const sampled: StrokePoint[] = [
    { x: roundStrokeCoord(points[0].x), z: roundStrokeCoord(points[0].z) },
  ];
  for (let i = 1; i < points.length; i += 1) {
    const cur = points[i];
    const isLast = i === points.length - 1;
    const prev = sampled[sampled.length - 1];
    if (!isLast && Math.hypot(cur.x - prev.x, cur.z - prev.z) < minDist) continue;
    sampled.push({ x: roundStrokeCoord(cur.x), z: roundStrokeCoord(cur.z) });
  }
  if (sampled.length <= maxPoints) return sampled;
  const out: StrokePoint[] = [];
  const step = (sampled.length - 1) / (maxPoints - 1);
  for (let i = 0; i < maxPoints; i += 1) {
    const idx = i === maxPoints - 1 ? sampled.length - 1 : Math.round(i * step);
    out.push(sampled[idx]);
  }
  return out;
}

export function markStrokePoints(mark: RaidRoomMarkLike): StrokePoint[] {
  if (mark.kind === "stroke") {
    const parsed = parseStrokePoints(mark.points);
    if (parsed.length) return parsed;
  }
  if (
    (mark.kind === "line" || mark.kind === "stroke") &&
    mark.x2 != null &&
    mark.z2 != null
  ) {
    return [
      { x: mark.x, z: mark.z },
      { x: mark.x2, z: mark.z2 },
    ];
  }
  return [{ x: mark.x, z: mark.z }];
}

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

export function isMapDrawTool(mode: TarkovMapDrawMode): boolean {
  return mode === "pen" || mode === "erase";
}

export function strokeFingerprint(mark: RaidRoomMarkLike): string {
  const pts = markStrokePoints(mark);
  if (!pts.length) return `${mark.kind}:${mark.floor || ""}:${mark.x}:${mark.z}`;
  const body = pts
    .map((point) => `${roundStrokeCoord(point.x)},${roundStrokeCoord(point.z)}`)
    .join(";");
  return `${mark.kind}:${mark.floor || ""}:${body}`;
}

export function mergeBoardMarks(
  boardMarks: RaidRoomMarkLike[],
  optimistic: RaidRoomMarkLike[],
): RaidRoomMarkLike[] {
  if (!optimistic.length) return boardMarks;
  const keys = new Set(boardMarks.map(strokeFingerprint));
  const extras = optimistic.filter((row) => !keys.has(strokeFingerprint(row)));
  return extras.length ? [...boardMarks, ...extras] : boardMarks;
}
