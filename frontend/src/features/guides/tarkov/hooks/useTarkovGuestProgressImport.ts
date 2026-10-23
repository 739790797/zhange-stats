/** 访客登录后问一次：本浏览器未登录时记下的塔科夫进度要不要并进账号。 */

import { useEffect, useRef } from "react";
import { message, Modal } from "antd";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { fetchTarkovTaskDonesFor, mergeTarkovKeyOwns } from "@/features/guides/tarkov/api/guidesApi";
import { apiError } from "@/shared/api/apiError";
import { TARKOV_GAME_MODES, type TarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import {
  browserLocalStorage,
  discardTarkovGuestProgress,
  readTarkovGuestProgress,
  type TarkovGuestProgress,
} from "@/features/guides/tarkov/model/tarkovProgressOwner";

/**
 * 账号上清空 / 转生重置过（reset_epoch>0）的模式：访客任务账没有时间可和边界比，不并。
 * 读不到账号就整笔失败：不能把「没读到」当成「重置过」，否则任务被跳过、暂存又被丢掉，进度就没了。
 */
async function guestTaskSkipModes(): Promise<Set<TarkovGameMode>> {
  const skip = new Set<TarkovGameMode>();
  await Promise.all(
    TARKOV_GAME_MODES.map(async (mode) => {
      const data = await fetchTarkovTaskDonesFor(mode);
      if ((data.reset_epoch ?? 0) > 0) skip.add(mode);
    }),
  );
  return skip;
}

/** 任务账与步骤并回本机，随后由账号同步上传；钥匙直接并进账号；阵营与收集格只补本机还没有的模式。 */
async function importTarkovGuestProgress(
  stash: TarkovGuestProgress,
  userId: number,
  queryClient: QueryClient,
): Promise<{ skippedTaskModes: TarkovGameMode[] }> {
  /* 只在真导入时（用户点「导入」）才拉这几个重模块，外壳常驻代码不背它们。 */
  const [
    { TARKOV_KEY_PACKS_STORAGE_KEY, applyTarkovKeyOwnsCache, parseOwnedState },
    { TARKOV_TASK_DONES_STORAGE_KEY, importGuestTaskProgress },
    { RAID_PREP_OBJ_DONE_STORAGE, importGuestRaidPrepObjectiveDone },
    {
      TARKOV_PMC_FACTION_STORAGE_KEY,
      loadTarkovPmcFaction,
      parseTarkovPmcFactionMap,
      persistTarkovPmcFaction,
    },
    {
      TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
      TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY,
      collectionLayoutFromStorage,
      loadCollectionLayout,
      saveCollectionLayout,
    },
  ] = await Promise.all([
    import("@/features/guides/tarkov/model/tarkovKeyPacks"),
    import("@/features/guides/tarkov/model/tarkovTaskTree"),
    import("@/features/guides/tarkov/model/tarkovRaidPrep"),
    import("@/features/guides/tarkov/model/tarkovPmcFaction"),
    import("@/features/guides/tarkov/model/tarkovCollection"),
  ]);
  /* 先读边界再写任何东西：读失败时整笔放弃，暂存原样留着，下次再问。 */
  const skip = await guestTaskSkipModes();
  const keyIds = parseOwnedState(stash[TARKOV_KEY_PACKS_STORAGE_KEY]);
  if (keyIds.length) {
    const data = await mergeTarkovKeyOwns(keyIds);
    applyTarkovKeyOwnsCache(queryClient, data.item_ids || []);
  }
  importGuestTaskProgress(stash[TARKOV_TASK_DONES_STORAGE_KEY], skip);
  importGuestRaidPrepObjectiveDone(stash[RAID_PREP_OBJ_DONE_STORAGE], userId);
  const factions = parseTarkovPmcFactionMap(
    stash[TARKOV_PMC_FACTION_STORAGE_KEY] ?? null,
  );
  for (const mode of TARKOV_GAME_MODES) {
    const faction = factions[mode];
    if (faction && !loadTarkovPmcFaction(mode)) {
      persistTarkovPmcFaction(mode, faction);
    }
    const layout = collectionLayoutFromStorage(
      stash[TARKOV_COLLECTION_LAYOUT_STORAGE_KEY],
      stash[TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY],
      mode,
    );
    if (layout?.placements.length && !loadCollectionLayout(mode)?.placements.length) {
      saveCollectionLayout(mode, layout);
    }
  }
  return { skippedTaskModes: TARKOV_GAME_MODES.filter((mode) => skip.has(mode)) };
}

/** onImported 之后调用方应重挂塔科夫子树，让账号同步按并集重新水合并上传。 */
export function useTarkovGuestProgressImport(
  userId: number | null | undefined,
  onImported: () => void,
): void {
  const queryClient = useQueryClient();
  const onImportedRef = useRef(onImported);
  onImportedRef.current = onImported;

  useEffect(() => {
    const storage = browserLocalStorage();
    if (!userId || !storage) return;
    const stash = readTarkovGuestProgress(storage);
    if (!stash) return;
    let cancelled = false;
    let modal: { destroy: () => void } | null = null;
    /* 统计要解析任务账 / 步骤 / 钥匙 / 收集格，几个模块都不小；只有真有访客暂存时才拉。 */
    void import("@/features/guides/tarkov/model/tarkovGuestProgress")
      .then(({ summarizeTarkovGuestProgress, tarkovGuestProgressParts }) => {
        if (cancelled) return;
        const parts = tarkovGuestProgressParts(summarizeTarkovGuestProgress(stash));
        if (!parts.length) {
          discardTarkovGuestProgress(storage);
          return;
        }
        modal = Modal.confirm({
          title: "导入本浏览器未登录时的进度？",
          content: `未登录时在这台设备上记下了${parts.join("、")}。导入会并进当前账号；不导入就丢掉这份本机记录。`,
          okText: "导入",
          cancelText: "不导入",
          onOk: () =>
            importTarkovGuestProgress(stash, userId, queryClient)
              .then(({ skippedTaskModes }) => {
                discardTarkovGuestProgress(storage);
                if (skippedTaskModes.length) {
                  const names = skippedTaskModes
                    .map((m) => (m === "pve" ? "PvE" : "正式"))
                    .join("、");
                  message.success(
                    `已导入未登录时的进度。账号${names}模式清空 / 转生过，那部分任务没有并入，请用「同步日志」从清空之后重放。`,
                    6,
                  );
                } else {
                  message.success("已导入未登录时的进度");
                }
                onImportedRef.current();
              })
              .catch((error: unknown) => {
                message.error(apiError(error, "导入失败，下次打开塔科夫页面会再问"));
              }),
          onCancel: () => discardTarkovGuestProgress(storage),
        });
      })
      .catch(() => {
        /* 分包没拿到：暂存原样留着，下次打开塔科夫页面再问。 */
      });
    return () => {
      cancelled = true;
      modal?.destroy();
    };
  }, [queryClient, userId]);
}
