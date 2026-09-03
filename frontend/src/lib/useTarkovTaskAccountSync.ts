/** 登录后把本机任务进度并进账号，换设备也能拉回进行中。 */

import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTarkovTaskDones, writeTarkovTaskDones } from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  notifyTarkovTaskProgress,
  sameIdLists,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import {
  loadTaskDoneIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  planAccountTaskHydrate,
  sameObjectiveLists,
  saveTaskProgress,
  taskProgressQueryData,
} from "@/lib/tarkovTaskTree";
import { useAuthStore } from "@/stores/authStore";

export function useTarkovTaskAccountSync() {
  const token = useAuthStore((s) => s.token);
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
      if (hydratingRef.current || detail.source !== "user") return;
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
    const plan = planAccountTaskHydrate({
      serverDone: query.data.task_ids || [],
      serverStarted: query.data.started_ids || [],
      serverObjectives: query.data.objective_dones || [],
      localDone: loadTaskDoneIds(gameMode),
      localStarted: loadTaskStartedIds(gameMode),
      localObjectives: loadTaskObjectivePairs(gameMode),
    });
    const prevDone = loadTaskDoneIds(gameMode);
    const prevStarted = loadTaskStartedIds(gameMode);
    const prevObjectives = loadTaskObjectivePairs(gameMode);
    const changed =
      !sameIdLists(prevDone, plan.done) ||
      !sameIdLists(prevStarted, plan.started) ||
      !sameObjectiveLists(prevObjectives, plan.objectives);
    saveTaskProgress(
      gameMode,
      plan.done,
      plan.started,
      !plan.upload,
      !plan.upload,
      plan.objectives,
    );
    queryClient.setQueryData(
      ["guides-tarkov-task-dones", gameMode],
      taskProgressQueryData(plan.done, plan.started, plan.objectives),
    );
    if (changed) {
      notifyTarkovTaskProgress({
        mode: gameMode,
        done: plan.done,
        started: plan.started,
        objectives: plan.objectives,
        changed: true,
        source: "hydrate",
      });
    }
    hydratingRef.current = false;
    if (!plan.upload) return;
    void writeTarkovTaskDones(plan.done, {
      startedIds: plan.started,
      objectiveDones: plan.objectives,
    })
      .then((data) => {
        const done = data.task_ids || plan.done;
        const started = data.started_ids || plan.started;
        const objectives = data.objective_dones || plan.objectives;
        saveTaskProgress(gameMode, done, started, true, true, objectives);
        queryClient.setQueryData(
          ["guides-tarkov-task-dones", gameMode],
          taskProgressQueryData(done, started, objectives),
        );
      })
      .catch(() => {
        hydrateKeyRef.current = "";
      });
  }, [gameMode, query.data, query.isSuccess, queryClient, token]);
}
