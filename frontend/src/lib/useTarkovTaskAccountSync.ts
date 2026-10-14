/**
 * 登录后把本机任务进度并进账号，换设备也能拉回进行中。
 *
 * 清空进度 / 转生的边界在账号（reset_at / pending_clear_at / reset_epoch）。本机账基于的 epoch 和账号对不上，
 * 说明别处清空或重置过：本机账作废，整份以账号为准，绝不再和账号做并集（并集正是旧任务被带回来的入口）。
 *
 * 只按真正从服务端拿到的响应判断 epoch。各面板会把 ["guides-tarkov-task-dones", mode] 缓存改写成
 * 只有四个进度字段的对象（不带 reset_epoch），那份缓存不能拿来判断边界。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovTaskDonesFor,
  writeTaskProgressLedger,
  type TarkovTaskDones,
} from "@/api/guidesApi";
import { useTarkovGameMode, type TarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  notifyTarkovTaskProgress,
  sameIdLists,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import {
  TARKOV_TASK_DONES_STORAGE_KEY,
  TARKOV_TASK_LEDGER_STALE_EVENT,
  adoptQuestBoundary,
  adoptServerTaskLedger,
  followStoredQuestEpoch,
  loadTaskDoneIds,
  loadTaskFailedIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  planAccountTaskHydrate,
  sameObjectiveLists,
  saveQuestServerEpoch,
  saveTaskProgress,
  taskProgressQueryData,
  loadTaskClearedDone,
  loadQuestProfileResetPending,
  loadQuestServerEpoch,
  loadTabQuestEpoch,
  clearQuestProfileResetPending,
  questLedgerEpochNow,
  questLedgerIsStale,
  ledgerIdsToClear,
} from "@/lib/tarkovTaskTree";
import {
  clearedMapFromServer,
  mergeClearedMaps,
  questBoundaryFromServer,
} from "@/lib/tarkovQuestBoundary";
import { mutexIndexFromTasks } from "@/lib/tarkovTaskMutex";
import { useAuthStore } from "@/stores/authStore";

export const TASK_DONES_QUERY_KEY = "guides-tarkov-task-dones";

/** 账号已在别处清空 / 重置：整份换成账号那份，并通知各面板。 */
export function adoptAccountTaskLedger(mode: TarkovGameMode, data: TarkovTaskDones): void {
  adoptServerTaskLedger(mode, {
    done: data.task_ids || [],
    started: data.started_ids || [],
    failed: data.failed_ids || [],
    objectives: data.objective_dones || [],
    cleared: clearedMapFromServer(data.cleared),
    boundary: questBoundaryFromServer(data),
  });
  notifyTarkovTaskProgress({
    mode,
    done: loadTaskDoneIds(mode),
    started: loadTaskStartedIds(mode),
    failed: loadTaskFailedIds(mode),
    objectives: loadTaskObjectivePairs(mode),
    changed: true,
    source: "hydrate",
  });
}

export function useTarkovTaskAccountSync() {
  const token = Boolean(useAuthStore((s) => s.user));
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const hydrateKeyRef = useRef("");
  const skipRef = useRef(false);
  const hydratingRef = useRef(false);
  /** 409 之后加 1：让对账副作用重新跑一遍，并强制回源。 */
  const [refreshTick, setRefreshTick] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshTick((n) => n + 1), []);

  useEffect(() => {
    hydrateKeyRef.current = "";
    skipRef.current = false;
  }, [gameMode, token]);

  useEffect(() => {
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode || detail.changed === false) return;
      if (hydratingRef.current) return;
      if (detail.source !== "user" && detail.source !== "log") return;
      skipRef.current = true;
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () => window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [gameMode]);

  useEffect(() => {
    if (!token) return;
    const onStale = () => {
      // 写入被 409：别处清空 / 重置过，或本页还没和账号对过。重拉账号后按 epoch 决定替换还是合并。
      hydrateKeyRef.current = "";
      skipRef.current = false;
      bumpRefresh();
    };
    // 别的标签页改了本机账（清空 / 同步 / 重置）：localStorage 的 epoch 变了就跟上，让面板重读本机账
    const onStorage = (event: StorageEvent) => {
      if (event.key !== TARKOV_TASK_DONES_STORAGE_KEY) return;
      if (!followStoredQuestEpoch(gameMode)) return;
      notifyTarkovTaskProgress({
        mode: gameMode,
        done: loadTaskDoneIds(gameMode),
        started: loadTaskStartedIds(gameMode),
        failed: loadTaskFailedIds(gameMode),
        objectives: loadTaskObjectivePairs(gameMode),
        changed: true,
        source: "hydrate",
      });
    };
    window.addEventListener(TARKOV_TASK_LEDGER_STALE_EVENT, onStale);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(TARKOV_TASK_LEDGER_STALE_EVENT, onStale);
      window.removeEventListener("storage", onStorage);
    };
  }, [bumpRefresh, gameMode, token]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const mode = gameMode;
    void (async () => {
      let data: TarkovTaskDones;
      try {
        data = await queryClient.fetchQuery({
          queryKey: [TASK_DONES_QUERY_KEY, mode],
          queryFn: () => fetchTarkovTaskDonesFor(mode),
          staleTime: refreshTick ? 0 : 60_000,
          retry: 1,
        });
      } catch {
        return;
      }
      if (cancelled) return;
      // 缓存可能已被面板改写成不带边界字段的对象；没有 reset_epoch 就不是服务端原样，重新拉一次
      if (typeof data.reset_epoch !== "number") {
        try {
          data = await fetchTarkovTaskDonesFor(mode);
        } catch {
          return;
        }
        if (cancelled) return;
      }
      reconcile(mode, data);
    })();
    return () => {
      cancelled = true;
    };

    function reconcile(mode: TarkovGameMode, data: TarkovTaskDones) {
      const boundary = questBoundaryFromServer(data);
      adoptQuestBoundary(mode, boundary);
      const stale =
        questLedgerIsStale(loadQuestServerEpoch(mode), boundary.epoch) ||
        questLedgerIsStale(loadTabQuestEpoch(mode), boundary.epoch);
      if (stale) {
        hydrateKeyRef.current = mode;
        hydratingRef.current = true;
        adoptAccountTaskLedger(mode, data);
        queryClient.setQueryData([TASK_DONES_QUERY_KEY, mode], data);
        hydratingRef.current = false;
        return;
      }
      saveQuestServerEpoch(mode, boundary.epoch);
      if (skipRef.current) return;
      if (hydrateKeyRef.current === mode) return;
      hydrateKeyRef.current = mode;
      hydrate(mode, data);
    }

    function hydrate(mode: TarkovGameMode, data: TarkovTaskDones) {
      hydratingRef.current = true;
      const catalog = queryClient.getQueryData<{
        items?: Array<{ id?: string | null; mutex_ids?: string[] | null }>;
      }>(["guides-tarkov-task-list", mode]);
      const pendingReset = loadQuestProfileResetPending(mode);
      const epoch = questLedgerEpochNow();
      const plan = planAccountTaskHydrate({
        serverDone: data.task_ids || [],
        serverStarted: data.started_ids || [],
        serverFailed: data.failed_ids || [],
        serverObjectives: data.objective_dones || [],
        localDone: loadTaskDoneIds(mode),
        localStarted: loadTaskStartedIds(mode),
        localFailed: loadTaskFailedIds(mode),
        localObjectives: loadTaskObjectivePairs(mode),
        clearedDone: mergeClearedMaps(
          loadTaskClearedDone(mode),
          clearedMapFromServer(data.cleared),
        ),
        mutexById: catalog?.items?.length
          ? mutexIndexFromTasks(catalog.items)
          : undefined,
        authoritativeLocal: pendingReset,
      });
      const prevDone = loadTaskDoneIds(mode);
      const prevStarted = loadTaskStartedIds(mode);
      const prevFailed = loadTaskFailedIds(mode);
      const prevObjectives = loadTaskObjectivePairs(mode);
      const changed =
        !sameIdLists(prevDone, plan.done) ||
        !sameIdLists(prevStarted, plan.started) ||
        !sameIdLists(prevFailed, plan.failed) ||
        !sameObjectiveLists(prevObjectives, plan.objectives);
      saveTaskProgress(
        mode,
        plan.done,
        plan.started,
        !plan.upload,
        !plan.upload,
        plan.objectives,
        plan.failed,
      );
      queryClient.setQueryData([TASK_DONES_QUERY_KEY, mode], {
        ...data,
        ...taskProgressQueryData(plan.done, plan.started, plan.objectives, plan.failed),
      });
      if (changed) {
        notifyTarkovTaskProgress({
          mode,
          done: plan.done,
          started: plan.started,
          failed: plan.failed,
          objectives: plan.objectives,
          changed: true,
          source: "hydrate",
        });
      }
      hydratingRef.current = false;
      if (!plan.upload) return;
      void writeTaskProgressLedger(
        {
          done: plan.done,
          started: plan.started,
          failed: plan.failed,
          objectives: plan.objectives,
        },
        {
          done: data.task_ids || [],
          started: data.started_ids || [],
          failed: data.failed_ids || [],
        },
        pendingReset ? { replace: true } : undefined,
      )
        .then((written) => {
          if (questLedgerEpochNow() !== epoch) {
            if (!loadQuestProfileResetPending(mode)) return;
            const healEpoch = questLedgerEpochNow();
            void writeTaskProgressLedger(
              {
                done: loadTaskDoneIds(mode),
                started: loadTaskStartedIds(mode),
                failed: loadTaskFailedIds(mode),
                objectives: loadTaskObjectivePairs(mode),
              },
              {
                done: written.task_ids,
                started: written.started_ids,
                failed: written.failed_ids,
              },
              { replace: true },
            ).then(() => {
              if (questLedgerEpochNow() !== healEpoch) return;
              clearQuestProfileResetPending(mode);
            });
            return;
          }
          if (pendingReset) clearQuestProfileResetPending(mode);
          const objectives = written.objective_dones || plan.objectives;
          saveTaskProgress(mode, plan.done, plan.started, true, true, objectives, plan.failed);
          queryClient.setQueryData([TASK_DONES_QUERY_KEY, mode], {
            ...written,
            ...taskProgressQueryData(plan.done, plan.started, objectives, plan.failed),
          });
          const extras = ledgerIdsToClear(
            {
              done: written.task_ids,
              started: written.started_ids,
              failed: written.failed_ids,
            },
            plan,
          );
          if (!extras.length) return;
          return writeTaskProgressLedger(
            { done: plan.done, started: plan.started, failed: plan.failed, objectives },
            {
              done: written.task_ids,
              started: written.started_ids,
              failed: written.failed_ids,
            },
          );
        })
        .catch(() => {
          hydrateKeyRef.current = "";
        });
    }
  }, [gameMode, queryClient, refreshTick, token]);
}
