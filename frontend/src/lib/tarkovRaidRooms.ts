import { tarkovRaidRoomHref } from "@/lib/tarkovHomeNav";
import { colorForUserId, mapSlugKeys } from "@/lib/tarkovRaidPrep";
import { logEventLabel } from "@/lib/tarkovGameLogs";

export { tarkovRaidRoomHref, colorForUserId };

export const RAID_ROOM_SLOT_COUNT = 5;
export const RAID_ROOM_SLOT_IDS = ["1", "2", "3", "4", "5"] as const;

const RAID_ROOM_SLOT_ID_RE = /^(?:pve-)?[1-5]$/i;

export function raidRoomSlotPublicId(
  slot: number,
  gameMode: string = "pvp",
): string {
  const n = Math.trunc(slot);
  if (n < 1 || n > RAID_ROOM_SLOT_COUNT) return "";
  return String(gameMode || "").trim().toLowerCase() === "pve"
    ? `pve-${n}`
    : String(n);
}

export function raidRoomSlotIdsForMode(gameMode: string = "pvp"): string[] {
  return RAID_ROOM_SLOT_IDS.map((id) =>
    raidRoomSlotPublicId(Number(id), gameMode),
  );
}

/** 按当前模式 1～5 号对齐大厅条目；对不上的桌用占位，不因模式错位整表清空。 */
export function mergeRaidLobbySeats<T extends { public_id: string }>(
  items: readonly T[] | null | undefined,
  placeholders: readonly T[],
): T[] {
  const byId = new Map(
    (items || []).map((row) => [String(row.public_id).toLowerCase(), row]),
  );
  return placeholders.map(
    (seat) => byId.get(String(seat.public_id).toLowerCase()) ?? seat,
  );
}

export function parseRaidRoomPublicId(
  raw: string,
  gameMode?: string,
): string {
  const text = (raw || "").trim();
  if (!text) return "";
  const fromPath = text.match(/raid-prep\/rooms\/([a-zA-Z0-9-]+)/i);
  if (fromPath?.[1]) return normalizeRaidRoomPublicId(fromPath[1]);
  const candidate = text.toLowerCase();
  if (/^[1-5]$/.test(candidate)) {
    return raidRoomSlotPublicId(Number(candidate), gameMode || "pvp");
  }
  return normalizeRaidRoomPublicId(candidate);
}

export function normalizeRaidRoomPublicId(raw: string): string {
  const key = (raw || "").trim().toLowerCase();
  if (RAID_ROOM_SLOT_ID_RE.test(key)) return key;
  return "";
}

export function isRaidRoomSlotId(publicId: string): boolean {
  return RAID_ROOM_SLOT_ID_RE.test(publicId);
}

/** WS 断线后指数退避，上限 30 秒。 */
export function raidRoomWsRetryDelayMs(attempt: number): number {
  const n = Number.isFinite(attempt) ? Math.max(0, Math.trunc(attempt)) : 0;
  return Math.min(30_000, 1000 * 2 ** n);
}

/** 房间占用心跳：只要这条 WS 还在，服务端就不收座位。 */
export const RAID_ROOM_WS_PING_MS = 25_000;

export const RAID_ROOM_OTHER_FLOOR_OPACITY = 0.28;

/** 房间内截图定位：超过此时长没有新点就从地图上拿掉。 */
export const PLAYER_FIX_TTL_MS = 8 * 60_000;

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

export type TarkovMapDrawMode = "pan" | "pen" | "pin" | "line" | "erase";

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

export type RaidRoomLogPhase = {
  userId: number;
  kind: string;
  mapId: string;
  mapLabel: string;
  raidId: string;
  at: string;
};

export function parseRaidRoomLogPhases(raw: unknown): RaidRoomLogPhase[] {
  if (!Array.isArray(raw)) return [];
  const out: RaidRoomLogPhase[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const rec = row as Record<string, unknown>;
    const userId = Number(rec.user_id ?? rec.userId);
    const kind = String(rec.kind || "").trim();
    if (!Number.isFinite(userId) || userId <= 0 || !kind) continue;
    out.push({
      userId,
      kind,
      mapId: String(rec.map_id ?? rec.mapId ?? "").trim(),
      mapLabel: String(rec.map_label ?? rec.mapLabel ?? "").trim(),
      raidId: String(rec.raid_id ?? rec.raidId ?? "").trim(),
      at: String(rec.at || "").trim(),
    });
  }
  return out;
}

/** 在座任一人日志为开战且未结束 → 已在战局中；否则准备中。 */
export function raidRoomLiveStatus(
  occupantIds: readonly number[],
  phases: readonly RaidRoomLogPhase[],
): "preparing" | "in_raid" {
  const seated = new Set(occupantIds.filter((id) => Number.isFinite(id) && id > 0));
  if (!seated.size) return "preparing";
  for (const phase of phases) {
    if (seated.has(phase.userId) && phase.kind === "raid_started") return "in_raid";
  }
  return "preparing";
}

export function formatRaidRoomLiveStatus(status: "preparing" | "in_raid"): string {
  return status === "in_raid" ? "已在战局中" : "准备中";
}

export function formatRaidRoomMemberWsLine(opts: {
  online?: boolean;
  phaseKind?: string;
}): string {
  const ws = opts.online ? "WS在线" : "WS离线";
  const kind = (opts.phaseKind || "").trim();
  if (!kind) return `${ws} · 无日志`;
  return `${ws} · ${logEventLabel(kind)}`;
}

export type RaidRoomSnapshotLike = {
  public_id: string;
  title?: string;
  map_slug: string;
  game_mode?: string | null;
  listed?: boolean;
  has_password?: boolean;
  host_user_id?: number | null;
  host_display_name: string;
  member_count?: number;
  max_members?: number;
  can_edit?: boolean;
  is_host?: boolean;
  is_member?: boolean;
  occupants?: RaidRoomOccupantLike[];
  members?: RaidRoomMemberLike[];
  claims?: RaidRoomClaimLike[];
  key_brings?: RaidRoomKeyBringLike[];
  key_owns?: RaidRoomKeyBringLike[];
  objective_dones?: RaidRoomObjectiveDoneLike[];
  marks?: RaidRoomMarkLike[];
  task_progress?: RaidRoomMemberProgressLike[];
  map_overlap?: RaidRoomMapOverlapLike[];
};

export type RaidRoomMemberProgressLike = {
  user_id: number;
  uploaded: boolean;
  started_count: number;
  uploaded_at?: string | null;
};

export type RaidRoomOverlapCellLike = {
  user_id: number;
  count: number;
  uploaded: boolean;
};

export type RaidRoomOverlapTaskLike = {
  id: string;
  name?: string;
  user_ids?: number[];
};

export type RaidRoomMapOverlapLike = {
  map_slug: string;
  with_tasks_count: number;
  synced_count: number;
  occupant_count: number;
  cells?: RaidRoomOverlapCellLike[];
  tasks?: RaidRoomOverlapTaskLike[];
};

export type RaidRoomObjectiveDoneLike = {
  task_id: string;
  objective_id: string;
  user_id: number;
  display_name?: string | null;
  created_at?: string | null;
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

export function formatRaidRoomOverlapCell(
  cell: RaidRoomOverlapCellLike | undefined,
): string {
  if (!cell || !cell.uploaded) return "—";
  return String(cell.count);
}

export function raidRoomOverlapPeopleLabel(count: number): string {
  return `${count}人`;
}

export function raidRoomOverlapTasksForUser(
  row: RaidRoomMapOverlapLike,
  userId: number,
): RaidRoomOverlapTaskLike[] {
  return (row.tasks || []).filter((task) =>
    (task.user_ids || []).includes(userId),
  );
}

export function raidRoomMapTaskTotal(row: RaidRoomMapOverlapLike): number {
  return (row.cells || []).reduce(
    (sum, cell) => sum + (cell.uploaded ? cell.count : 0),
    0,
  );
}

export function sortRaidRoomMapOverlap(
  rows: readonly RaidRoomMapOverlapLike[],
  mapOrder: readonly string[],
): RaidRoomMapOverlapLike[] {
  const order = new Map(mapOrder.map((id, index) => [id, index]));
  return [...rows].sort((left, right) => {
    const withTasks = right.with_tasks_count - left.with_tasks_count;
    if (withTasks) return withTasks;
    const total = raidRoomMapTaskTotal(right) - raidRoomMapTaskTotal(left);
    if (total) return total;
    return (order.get(left.map_slug) ?? 99) - (order.get(right.map_slug) ?? 99);
  });
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

/** 当前入座的那一桌；未入座返回空。已在该房间页时也返回空（不必再「回去」）。 */
export function raidRoomReturnHref(
  items:
    | readonly { is_member?: boolean; public_id?: string | null }[]
    | null
    | undefined,
  pathname: string,
): string {
  const seated = (items || []).find((row) => row.is_member);
  const id = normalizeRaidRoomPublicId(seated?.public_id || "");
  if (!id) return "";
  if (parseRaidRoomPublicId(pathname) === id) return "";
  return tarkovRaidRoomHref(id);
}

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

export function userOwnsKey(
  owns: readonly RaidRoomKeyBringLike[] | null | undefined,
  itemId: string,
  userId: number | null | undefined,
): boolean {
  return userBroughtKey(owns, itemId, userId);
}

export function patchRaidRoomKeyOwns(
  owns: readonly RaidRoomKeyBringLike[] | null | undefined,
  itemId: string,
  user: { userId: number; name: string },
  nextHas: boolean,
): RaidRoomKeyBringLike[] {
  const id = String(itemId || "").trim();
  const rest = (owns || []).filter(
    (row) =>
      !(row.user_id === user.userId && String(row.item_id || "").trim() === id),
  );
  if (!nextHas || !id) return rest;
  return [
    ...rest,
    {
      item_id: id,
      user_id: user.userId,
      display_name: (user.name || "").trim() || `用户${user.userId}`,
    },
  ];
}

export function formatKeyOwnToggleLabel(ownedByMe: boolean): string {
  return ownedByMe ? "取消" : "我有";
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

export function formatKeyOwnHint(names: readonly string[]): string {
  if (!names.length) return "";
  if (names.length === 1) return `${names[0]}拥有这把钥匙。`;
  return `${names.join("、")}拥有这把钥匙。`;
}

export function keyOwnsForUser(
  itemIds: readonly string[] | null | undefined,
  user: { userId: number; name: string } | null | undefined,
): RaidRoomKeyBringLike[] {
  if (!user || !itemIds?.length) return [];
  const name = (user.name || "").trim() || `用户${user.userId}`;
  return itemIds.map((item_id) => ({
    item_id,
    user_id: user.userId,
    display_name: name,
  }));
}

export function formatKeyChipHint(
  ownNames: readonly string[],
  bringNames: readonly string[],
  options?: { canToggle?: boolean },
): string {
  const own = formatKeyOwnHint(ownNames);
  const bring = formatKeyBringHint(bringNames, options);
  return [own, bring].filter(Boolean).join("\n");
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

export function raidRoomLiveSig(
  room: RaidRoomSnapshotLike | null | undefined,
): string {
  if (!room) return "";
  const claims = (room.claims || [])
    .map((row) => `${row.user_id}:${row.task_id}`)
    .sort()
    .join(",");
  const marks = (room.marks || []).map((row) => row.id).join(",");
  const dones = (room.objective_dones || [])
    .map((row) => `${row.user_id}:${row.task_id}:${row.objective_id}`)
    .sort()
    .join(",");
  const keys = (room.key_brings || [])
    .map((row) => `${row.user_id}:${row.item_id}`)
    .sort()
    .join(",");
  const owns = (room.key_owns || [])
    .map((row) => `${row.user_id}:${row.item_id}`)
    .sort()
    .join(",");
  return [
    room.map_slug,
    room.host_user_id ?? "",
    room.title || "",
    room.member_count ?? "",
    claims,
    marks,
    dones,
    keys,
    owns,
  ].join("|");
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
  if (event.snapshot) {
    if (current && raidRoomLiveSig(current) === raidRoomLiveSig(event.snapshot)) {
      return withPresence(current);
    }
    return withPresence(event.snapshot);
  }
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
  return mode === "pen" || mode === "pin" || mode === "line" || mode === "erase";
}

export function strokeFingerprint(mark: RaidRoomMarkLike): string {
  const pts = markStrokePoints(mark);
  if (!pts.length) return `${mark.kind}:${mark.floor || ""}:${mark.x}:${mark.z}`;
  const body = pts
    .map((point) => `${roundStrokeCoord(point.x)},${roundStrokeCoord(point.z)}`)
    .join(";");
  return `${mark.kind}:${mark.floor || ""}:${body}`;
}

export type RaidRoomPlayerFix = {
  userId: number;
  x: number;
  y: number;
  z: number;
  yaw: number | null;
  mapId: string;
  fileName: string;
  at: number;
};

export type TarkovMapPlayerMark = {
  key: string;
  userId: number;
  name: string;
  color: string;
  x: number;
  y: number;
  z: number;
  yaw: number | null;
  self?: boolean;
};

function finiteCoord(raw: unknown): number | null {
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function parsePlayerFixEvent(
  raw: {
    user_id?: unknown;
    x?: unknown;
    y?: unknown;
    z?: unknown;
    yaw?: unknown;
    map_id?: unknown;
    file_name?: unknown;
  },
  at = Date.now(),
): RaidRoomPlayerFix | null {
  const userId = Number(raw.user_id);
  const x = finiteCoord(raw.x);
  const y = finiteCoord(raw.y);
  const z = finiteCoord(raw.z);
  if (!userId || x == null || y == null || z == null) return null;
  const yawRaw = raw.yaw;
  let yaw: number | null = null;
  if (yawRaw != null && yawRaw !== "") {
    const parsed = finiteCoord(yawRaw);
    if (parsed == null) return null;
    yaw = parsed;
  }
  return {
    userId,
    x,
    y,
    z,
    yaw,
    mapId: String(raw.map_id || "").trim(),
    fileName: String(raw.file_name || "").trim(),
    at,
  };
}

/** 日志地图未知时仍可画；对不上房间地图则丢掉。 */
export function playerFixMatchesRoomMap(
  fixMapId: string | undefined,
  roomMapId: string,
): boolean {
  const room = (roomMapId || "").trim();
  if (!room) return false;
  const fix = (fixMapId || "").trim();
  if (!fix) return true;
  const roomKeys = mapSlugKeys(room);
  for (const key of mapSlugKeys(fix)) {
    if (roomKeys.has(key)) return true;
  }
  return false;
}

export function playerFixIsFresh(
  at: number,
  now = Date.now(),
  ttlMs = PLAYER_FIX_TTL_MS,
): boolean {
  return now - at <= ttlMs;
}

export function upsertPlayerFix(
  current: readonly RaidRoomPlayerFix[],
  next: RaidRoomPlayerFix,
): RaidRoomPlayerFix[] {
  return [...current.filter((row) => row.userId !== next.userId), next];
}

export function dropPlayerFixesNotIn(
  current: readonly RaidRoomPlayerFix[],
  onlineIds: ReadonlySet<number>,
): RaidRoomPlayerFix[] {
  return current.filter((row) => onlineIds.has(row.userId));
}

export function pruneStalePlayerFixes(
  current: readonly RaidRoomPlayerFix[],
  now = Date.now(),
  ttlMs = PLAYER_FIX_TTL_MS,
): RaidRoomPlayerFix[] {
  return current.filter((row) => playerFixIsFresh(row.at, now, ttlMs));
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
