/** 房间码解析与「回到房间」链接：轻模块，外壳顶栏常驻，不拖整份 tarkovRaidRooms。 */

import { tarkovRaidRoomHref } from "@/features/guides/tarkov/model/tarkovHomeNav";

export const RAID_ROOM_SLOT_COUNT = 5;

const RAID_ROOM_PUBLIC_ID_RE = /^(?:(?:pve-)?[1-5]|[a-z0-9]{8,16})$/i;

/** 旧的 1–5 / pve-N 席位号：新房间改用随机码，但旧房间码仍要能粘进输入框。 */
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
  if (!key || key === "solo") return "";
  if (RAID_ROOM_PUBLIC_ID_RE.test(key)) return key;
  return "";
}

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
