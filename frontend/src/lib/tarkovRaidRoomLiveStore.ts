import { create } from "zustand";
import {
  dropPlayerFixesNotIn,
  playerFixMatchesRoomMap,
  pruneStalePlayerFixes,
  upsertPlayerFix,
  type RaidRoomDraftStroke,
  type RaidRoomPlayerFix,
} from "@/lib/tarkovRaidRooms";

type RaidRoomLiveState = {
  roomId: string;
  drafts: RaidRoomDraftStroke[];
  fixes: RaidRoomPlayerFix[];
  bind: (roomId: string) => void;
  setDraft: (draft: RaidRoomDraftStroke | null, userId: number) => void;
  clearDrafts: () => void;
  upsertFix: (fix: RaidRoomPlayerFix) => void;
  dropFixesNotIn: (onlineIds: ReadonlySet<number>) => void;
  dropFixUser: (userId: number) => void;
  filterMap: (mapId: string) => void;
  pruneFixes: () => void;
};

export const useRaidRoomLiveStore = create<RaidRoomLiveState>((set) => ({
  roomId: "",
  drafts: [],
  fixes: [],
  bind: (roomId) =>
    set((current) =>
      current.roomId === roomId
        ? current
        : { roomId, drafts: [], fixes: [] },
    ),
  setDraft: (draft, userId) =>
    set((current) => {
      const rest = current.drafts.filter((row) => row.userId !== userId);
      if (!draft || !draft.points.length) return { drafts: rest };
      return { drafts: [...rest, draft] };
    }),
  clearDrafts: () => set({ drafts: [] }),
  upsertFix: (fix) =>
    set((current) => ({ fixes: upsertPlayerFix(current.fixes, fix) })),
  dropFixesNotIn: (onlineIds) =>
    set((current) => ({
      fixes: dropPlayerFixesNotIn(current.fixes, onlineIds),
    })),
  dropFixUser: (userId) =>
    set((current) => ({
      fixes: current.fixes.filter((row) => row.userId !== userId),
    })),
  filterMap: (mapId) =>
    set((current) => ({
      fixes: current.fixes.filter((row) =>
        playerFixMatchesRoomMap(row.mapId, mapId),
      ),
    })),
  pruneFixes: () =>
    set((current) => {
      const next = pruneStalePlayerFixes(current.fixes);
      return next.length === current.fixes.length ? current : { fixes: next };
    }),
}));
