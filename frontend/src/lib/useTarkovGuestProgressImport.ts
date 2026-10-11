/** 访客登录后问一次：本浏览器未登录时记下的塔科夫进度要不要并进账号。 */

import { useEffect, useRef } from "react";
import { message, Modal } from "antd";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { mergeTarkovKeyOwns } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
  TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY,
  collectionLayoutFromStorage,
  loadCollectionLayout,
  saveCollectionLayout,
} from "@/lib/tarkovCollection";
import { TARKOV_GAME_MODES } from "@/lib/tarkovGameMode";
import {
  summarizeTarkovGuestProgress,
  tarkovGuestProgressParts,
} from "@/lib/tarkovGuestProgress";
import {
  TARKOV_KEY_PACKS_STORAGE_KEY,
  applyTarkovKeyOwnsCache,
  parseOwnedState,
} from "@/lib/tarkovKeyPacks";
import {
  TARKOV_PMC_FACTION_STORAGE_KEY,
  loadTarkovPmcFaction,
  parseTarkovPmcFactionMap,
  persistTarkovPmcFaction,
} from "@/lib/tarkovPmcFaction";
import {
  browserLocalStorage,
  discardTarkovGuestProgress,
  readTarkovGuestProgress,
  type TarkovGuestProgress,
} from "@/lib/tarkovProgressOwner";
import {
  RAID_PREP_OBJ_DONE_STORAGE,
  importGuestRaidPrepObjectiveDone,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_DONES_STORAGE_KEY,
  importGuestTaskProgress,
} from "@/lib/tarkovTaskTree";

/** 任务账与步骤并回本机，随后由账号同步上传；钥匙直接并进账号；阵营与收集格只补本机还没有的模式。 */
async function importTarkovGuestProgress(
  stash: TarkovGuestProgress,
  userId: number,
  queryClient: QueryClient,
): Promise<void> {
  const keyIds = parseOwnedState(stash[TARKOV_KEY_PACKS_STORAGE_KEY]);
  if (keyIds.length) {
    const data = await mergeTarkovKeyOwns(keyIds);
    applyTarkovKeyOwnsCache(queryClient, data.item_ids || []);
  }
  importGuestTaskProgress(stash[TARKOV_TASK_DONES_STORAGE_KEY]);
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
    const parts = tarkovGuestProgressParts(summarizeTarkovGuestProgress(stash));
    if (!parts.length) {
      discardTarkovGuestProgress(storage);
      return;
    }
    const modal = Modal.confirm({
      title: "导入本浏览器未登录时的进度？",
      content: `未登录时在这台设备上记下了${parts.join("、")}。导入会并进当前账号；不导入就丢掉这份本机记录。`,
      okText: "导入",
      cancelText: "不导入",
      onOk: () =>
        importTarkovGuestProgress(stash, userId, queryClient)
          .then(() => {
            discardTarkovGuestProgress(storage);
            message.success("已导入未登录时的进度");
            onImportedRef.current();
          })
          .catch((error: unknown) => {
            message.error(apiError(error, "导入失败，下次打开塔科夫页面会再问"));
          }),
      onCancel: () => discardTarkovGuestProgress(storage),
    });
    return () => modal.destroy();
  }, [queryClient, userId]);
}
