import { tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { colorForUserId } from "@/lib/tarkovRaidPrep";

export { tarkovRaidRoomHref, colorForUserId };

export function parseRaidRoomPublicId(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const fromPath = text.match(/raid-prep\/rooms\/([a-zA-Z0-9]+)/i);
  if (fromPath?.[1] && /^[a-f0-9]{12}$/i.test(fromPath[1])) {
    return fromPath[1].toLowerCase();
  }
  if (/^[a-f0-9]{12}$/i.test(text)) return text.toLowerCase();
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
