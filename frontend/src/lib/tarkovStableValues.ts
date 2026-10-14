import { useRef } from "react";
import type { TarkovLogPhasePayload } from "@/lib/tarkovGameLogs";
import type { TarkovMapPlayerMark } from "@/lib/tarkovRaidRooms";

/** 日志相位：这几项一样就当没变（mapLabel 由 mapId 推出）。 */
export function sameLogPhase(
  a: TarkovLogPhasePayload | null | undefined,
  b: TarkovLogPhasePayload | null | undefined,
): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return (
    a.kind === b.kind &&
    a.mapId === b.mapId &&
    a.raidId === b.raidId &&
    a.at === b.at &&
    (a.raidMode || "") === (b.raidMode || "")
  );
}

/** 新相位与旧相位等价时沿用旧对象，下游 context 消费者不重绘。 */
export function keepLogPhase(
  prev: TarkovLogPhasePayload | null,
  next: TarkovLogPhasePayload | null,
): TarkovLogPhasePayload | null {
  return sameLogPhase(prev, next) ? prev : next;
}

export type MemberPhaseLike = { kind?: string | null; online?: boolean };

/** 房间在座相位：只比这几项，mapLabel 由 mapId 推出。 */
export type RaidRoomLogPhaseLike = {
  /** 在座相位表用它做键，值里可省；列表形态（含自己那行）才带。 */
  userId?: number;
  kind?: string | null;
  mapId?: string | null;
  raidId?: string | null;
  at?: string | null;
};

export function sameMemberPhases(
  a: ReadonlyMap<number, MemberPhaseLike>,
  b: ReadonlyMap<number, MemberPhaseLike>,
): boolean {
  if (a === b) return true;
  if (a.size !== b.size) return false;
  for (const [userId, row] of a) {
    const other = b.get(userId);
    if (!other) return false;
    if ((row.kind || "") !== (other.kind || "")) return false;
    if (Boolean(row.online) !== Boolean(other.online)) return false;
  }
  return true;
}

/** 房间在座相位（每人一行的 kind / 地图）逐人比对。 */
export function sameRaidRoomPhases(
  a: ReadonlyMap<number, RaidRoomLogPhaseLike>,
  b: ReadonlyMap<number, RaidRoomLogPhaseLike>,
): boolean {
  if (a === b) return true;
  if (a.size !== b.size) return false;
  for (const [userId, row] of a) {
    const other = b.get(userId);
    if (!other) return false;
    if (
      (row.kind || "") !== (other.kind || "") ||
      (row.mapId || "") !== (other.mapId || "") ||
      (row.raidId || "") !== (other.raidId || "")
    ) {
      return false;
    }
  }
  return true;
}

/** 日志相位列表（含自己那行）逐项比对：日志 tick 会重解析出新数组。 */
export function sameRaidRoomPhaseList(
  a: readonly RaidRoomLogPhaseLike[],
  b: readonly RaidRoomLogPhaseLike[],
): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  return a.every((row, index) => {
    const other = b[index]!;
    return (
      row.userId === other.userId &&
      (row.kind || "") === (other.kind || "") &&
      (row.mapId || "") === (other.mapId || "") &&
      (row.raidId || "") === (other.raidId || "") &&
      (row.at || "") === (other.at || "")
    );
  });
}

export function samePlayerMarks(
  a: readonly TarkovMapPlayerMark[],
  b: readonly TarkovMapPlayerMark[],
): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  return a.every((row, index) => {
    const other = b[index]!;
    return (
      row.key === other.key &&
      row.userId === other.userId &&
      row.name === other.name &&
      row.color === other.color &&
      row.x === other.x &&
      row.y === other.y &&
      row.z === other.z &&
      row.yaw === other.yaw &&
      Boolean(row.self) === Boolean(other.self)
    );
  });
}

/** 结构相等时返回上一次的引用；给 memo 后仍会因上游新对象而抖动的派生值用。 */
export function useStableValue<T>(next: T, equal: (a: T, b: T) => boolean): T {
  const ref = useRef(next);
  if (ref.current !== next && !equal(ref.current, next)) ref.current = next;
  return ref.current;
}
