/** 登录后把本机任务进度并进账号，换设备也能拉回进行中。 */

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTarkovTaskDones, writeTaskProgressLedger } from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  notifyTarkovTaskProgress,
  sameIdLists,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import {
  loadTaskDoneIds,
  loadTaskFailedIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  planAccountTaskHydrate,
  sameObjectiveLists,
  saveTaskProgress,
  taskProgressQueryData,
  loadTaskClearedDone,
  ledgerIdsToClear,
} from "@/lib/tarkovTaskTree";
import { mutexIndexFromTasks } from "@/lib/tarkovTaskMutex";
import { useAuthStore } from "@/stores/authStore";

export function useTarkovTaskAccountSync() {
  const token = Boolean(useAuthStore((s) => s.user));
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const hydrateKeyRef = useRef("");
  const skipRef = useRef(false);
  const hydratingRef = useRef(false);

  const query = useQuery({
    queryKey: ["guides-tarkov-task-dones", gameMode],
    queryFn: fetchTarkovTaskDones,
    enabled: Boolean(token),
    staleTime: 60_000,
    retry: 1,
  });

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
    if (!token || !query.isSuccess || query.data == null) return;
    if (skipRef.current) return;
    const key = gameMode;
    if (hydrateKeyRef.current === key) return;
    hydrateKeyRef.current = key;
    hydratingRef.current = true;
    const catalog = queryClient.getQueryData<{
      items?: Array<{ id?: string | null; mutex_ids?: string[] | null }>;
    }>(["guides-tarkov-task-list", gameMode]);
    const plan = planAccountTaskHydrate({
      serverDone: query.data.task_ids || [],
      serverStarted: query.data.started_ids || [],
      serverFailed: query.data.failed_ids || [],
      serverObjectives: query.data.objective_dones || [],
      localDone: loadTaskDoneIds(gameMode),
      localStarted: loadTaskStartedIds(gameMode),
      localFailed: loadTaskFailedIds(gameMode),
      localObjectives: loadTaskObjectivePairs(gameMode),
      clearedDone: loadTaskClearedDone(gameMode),
      mutexById: catalog?.items?.length
        ? mutexIndexFromTasks(catalog.items)
        : undefined,
    });
    const prevDone = loadTaskDoneIds(gameMode);
    const prevStarted = loadTaskStartedIds(gameMode);
    const prevFailed = loadTaskFailedIds(gameMode);
    const prevObjectives = loadTaskObjectivePairs(gameMode);
    const changed =
      !sameIdLists(prevDone, plan.done) ||
      !sameIdLists(prevStarted, plan.started) ||
      !sameIdLists(prevFailed, plan.failed) ||
      !sameObjectiveLists(prevObjectives, plan.objectives);
    saveTaskProgress(
      gameMode,
      plan.done,
      plan.started,
      !plan.upload,
      !plan.upload,
      plan.objectives,
      plan.failed,
    );
    queryClient.setQueryData(
      ["guides-tarkov-task-dones", gameMode],
      taskProgressQueryData(
        plan.done,
        plan.started,
        plan.objectives,
        plan.failed,
      ),
    );
    if (changed) {
      notifyTarkovTaskProgress({
        mode: gameMode,
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
        done: query.data.task_ids || [],
        started: query.data.started_ids || [],
        failed: query.data.failed_ids || [],
      },
    )
      .then((data) => {
        const objectives = data.objective_dones || plan.objectives;
        saveTaskProgress(
          gameMode,
          plan.done,
          plan.started,
          true,
          true,
          objectives,
          plan.failed,
        );
        queryClient.setQueryData(
          ["guides-tarkov-task-dones", gameMode],
          taskProgressQueryData(
            plan.done,
            plan.started,
            objectives,
            plan.failed,
          ),
        );
        const extras = ledgerIdsToClear(
          {
            done: data.task_ids,
            started: data.started_ids,
            failed: data.failed_ids,
          },
          plan,
        );
        if (!extras.length) return;
        return writeTaskProgressLedger(
          {
            done: plan.done,
            started: plan.started,
            failed: plan.failed,
            objectives,
          },
          {
            done: data.task_ids,
            started: data.started_ids,
            failed: data.failed_ids,
          },
        );
      })
      .catch(() => {
        hydrateKeyRef.current = "";
      });
  }, [gameMode, query.data, query.isSuccess, queryClient, token]);
}
