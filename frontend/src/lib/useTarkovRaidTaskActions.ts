import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { TarkovRaidPrepTask } from "@/api/guidesApi";
import {
  addTarkovTaskObjectiveDone,
  removeTarkovTaskDone,
  removeTarkovTaskObjectiveDone,
  writeTaskProgressLedger,
} from "@/api/guidesApi";
import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import {
  commitTaskObjective,
  commitTaskStatus,
  ledgerIdsToClear,
  loadTaskDoneIds,
  loadTaskFailedIds,
  loadTaskStartedIds,
  taskProgressQueryData,
  overlayTaskProgressCache,
} from "@/lib/tarkovTaskTree";
import {
  mergeObjectivePairs,
  type RaidPrepObjectivePair,
} from "@/lib/tarkovObjectivePairs";
import {
  planRaidPrepObjectiveToggle,
  raidPrepAllObjectiveIds,
  raidPrepSkippedIds,
  raidPrepTaskProgressStatus,
  resolveRaidPrepLocateTargets,
  type RaidPrepPoint,
  type RaidPrepSkipMap,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";

export type RaidTaskFocusRequest = RaidPrepPoint & { seq: number };

type Opts = {
  /** 房间要「在座且在本图」才能改；单人准备恒真。 */
  enabled: boolean;
  gameMode: TarkovGameMode;
  mapId: string;
  /** 整图目录（已灌几何），整任务完成时用来回填小步骤。 */
  catalog: readonly TarkovRaidPrepTask[];
  doneSet: ReadonlySet<string>;
  startedSet: ReadonlySet<string>;
  /** 本机步骤勾选（含旧作用域）。 */
  objDone: RaidPrepSkipMap;
  /** 展示态：本机 ∪ 账号进度账。 */
  objDoneView: RaidPrepSkipMap;
  replaceObjDone: (next: RaidPrepSkipMap) => void;
  toggleObjDoneLocal: (taskId: string, objectiveId: string) => void;
  /** 本图 overlay 用的任务（定位点从它取，缺了再回源）。 */
  overlayTasks: readonly TarkovRaidPrepTask[];
  ensureGeometry: (
    taskId: string,
  ) => Promise<TarkovRaidPrepTask | undefined>;
  /** 换图时把定位序号清掉，下一次从头开始循环。 */
  locateResetKey?: string;
};

/**
 * 备战页与房间共用的任务操作：小步骤勾选、下拉状态、定位、打开攻略。
 *
 * 两个面板原先各拷一份，房间那份还少了账号对账与步骤回填 —— 这里以备战页的
 * 完整版为准，房间接上后行为与单人一致。
 */
export function useTarkovRaidTaskActions({
  enabled,
  gameMode,
  mapId,
  catalog,
  doneSet,
  startedSet,
  objDone,
  objDoneView,
  replaceObjDone,
  toggleObjDoneLocal,
  overlayTasks,
  ensureGeometry,
  locateResetKey = "",
}: Opts) {
  const queryClient = useQueryClient();
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [focusRequest, setFocusRequest] = useState<RaidTaskFocusRequest | null>(
    null,
  );
  const locateIndexRef = useRef<Record<string, number>>({});
  const focusSeqRef = useRef(0);
  const objToggleSeqRef = useRef(0);
  const locateResetRef = useRef(locateResetKey);
  if (locateResetRef.current !== locateResetKey) {
    locateResetRef.current = locateResetKey;
    locateIndexRef.current = {};
  }

  const taskStatusOf = useCallback(
    (taskId: string) =>
      raidPrepTaskProgressStatus(taskId, doneSet, startedSet),
    [doneSet, startedSet],
  );

  /** 结果落在本机勾选上：读 → 并 → 比 → 变才替换（7 处同一模式，收口到这里）。 */
  const applyObjectiveDones = useCallback(
    (pairs: readonly RaidPrepObjectivePair[] | null | undefined) => {
      const merged = mergeObjectivePairs(objDone, pairs);
      if (merged) replaceObjDone(merged);
    },
    [objDone, replaceObjDone],
  );

  const toggleObjDone = useCallback(
    (taskId: string, objectiveId: string) => {
      if (!enabled) return;
      const seq = ++objToggleSeqRef.current;
      const plan = planRaidPrepObjectiveToggle({
        localHas: raidPrepSkippedIds(objDone, taskId).has(objectiveId),
        viewHas: raidPrepSkippedIds(objDoneView, taskId).has(objectiveId),
        taskDone: doneSet.has(taskId),
      });
      if (plan.toggleLocal) toggleObjDoneLocal(taskId, objectiveId);
      const pairs = commitTaskObjective(
        gameMode,
        taskId,
        objectiveId,
        plan.nextChecked,
      );
      const progress = plan.reopenTask
        ? commitTaskStatus(gameMode, taskId, "active", undefined, undefined, catalog)
        : {
            done: loadTaskDoneIds(gameMode),
            started: loadTaskStartedIds(gameMode),
            failed: loadTaskFailedIds(gameMode),
            objectives: pairs,
          };
      queryClient.setQueryData(["guides-tarkov-task-dones", gameMode], (prev) =>
        overlayTaskProgressCache(
          prev,
          taskProgressQueryData(
            progress.done,
            progress.started,
            progress.objectives,
            progress.failed,
          ),
        ),
      );
      const applyServer = (data: {
        task_ids?: string[];
        started_ids?: string[];
        failed_ids?: string[];
        objective_dones?: typeof pairs;
        cleared?: Array<{ task_id?: string | null; cleared_at?: string | null }> | null;
        reset_at?: string | null;
        pending_clear_at?: string | null;
        reset_profile_id?: string | null;
        reset_epoch?: number | null;
      } | null) => {
        if (!data || seq !== objToggleSeqRef.current) return;
        queryClient.setQueryData(["guides-tarkov-task-dones", gameMode], (prev) =>
          overlayTaskProgressCache(
            prev,
            taskProgressQueryData(
              data.task_ids || loadTaskDoneIds(gameMode),
              data.started_ids || loadTaskStartedIds(gameMode),
              data.objective_dones || pairs,
              data.failed_ids || loadTaskFailedIds(gameMode),
            ),
            data,
          ),
        );
      };
      void (
        plan.reopenTask
          ? removeTarkovTaskDone(taskId)
              .catch(() => null)
              .then(() => removeTarkovTaskObjectiveDone(taskId, objectiveId))
              .then(applyServer)
          : (plan.nextChecked
              ? addTarkovTaskObjectiveDone(taskId, objectiveId)
              : removeTarkovTaskObjectiveDone(taskId, objectiveId)
            ).then(applyServer)
      ).catch(() => {});
    },
    [
      catalog,
      doneSet,
      enabled,
      gameMode,
      objDone,
      objDoneView,
      queryClient,
      toggleObjDoneLocal,
    ],
  );

  const changeTaskStatus = useCallback(
    (taskId: string, status: RaidPrepTaskProgressStatus) => {
      if (raidPrepTaskProgressStatus(taskId, doneSet, startedSet) === status) {
        return;
      }
      const task = catalog.find((row) => row.id === taskId);
      const fillIds =
        status === "done" && task ? raidPrepAllObjectiveIds(task) : undefined;
      const prev = {
        done: loadTaskDoneIds(gameMode),
        started: loadTaskStartedIds(gameMode),
        failed: loadTaskFailedIds(gameMode),
      };
      const next = commitTaskStatus(
        gameMode,
        taskId,
        status,
        fillIds,
        task?.mutex_ids,
        catalog,
      );
      if (fillIds?.length) {
        applyObjectiveDones(
          next.objectives.map((row) => ({
            task_id: row.task_id,
            objective_id: row.objective_id,
          })),
        );
      }
      queryClient.setQueryData(["guides-tarkov-task-dones", gameMode], (prev) =>
        overlayTaskProgressCache(
          prev,
          taskProgressQueryData(
            next.done,
            next.started,
            next.objectives,
            next.failed,
          ),
        ),
      );
      void writeTaskProgressLedger(
        {
          done: next.done,
          started: next.started,
          failed: next.failed,
          objectives: next.objectives,
        },
        prev,
      )
        .then((data) => {
          // 账号那份是权威：合并 PUT 只加不删，先按回包对账再补 DELETE。
          const objectives = data.objective_dones || next.objectives;
          queryClient.setQueryData(["guides-tarkov-task-dones", gameMode], (prev) =>
            overlayTaskProgressCache(
              prev,
              taskProgressQueryData(
                next.done,
                next.started,
                objectives,
                next.failed,
              ),
              data,
            ),
          );
          const extras = ledgerIdsToClear(
            {
              done: data.task_ids,
              started: data.started_ids,
              failed: data.failed_ids,
            },
            next,
          );
          if (extras.length) {
            void writeTaskProgressLedger(
              {
                done: next.done,
                started: next.started,
                failed: next.failed,
                objectives,
              },
              {
                done: data.task_ids,
                started: data.started_ids,
                failed: data.failed_ids,
              },
            ).catch(() => {});
          }
          applyObjectiveDones(objectives);
        })
        .catch(() => {});
    },
    [applyObjectiveDones, catalog, doneSet, gameMode, queryClient, startedSet],
  );

  const locateTask = useCallback(
    async (row: TarkovRaidPrepTask) => {
      let points = resolveRaidPrepLocateTargets(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(objDoneView, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const rich = await ensureGeometry(row.id);
          points = rich
            ? resolveRaidPrepLocateTargets(
                rich,
                mapId,
                raidPrepSkippedIds(objDoneView, row.id),
              )
            : [];
        } catch {
          return;
        }
      }
      if (!points.length) return;
      const index = locateIndexRef.current[row.id] || 0;
      const point = points[index % points.length]!;
      locateIndexRef.current[row.id] = index + 1;
      focusSeqRef.current += 1;
      setHighlightTaskId(row.id);
      setFocusRequest({ ...point, seq: focusSeqRef.current });
      window.setTimeout(() => {
        document
          .querySelector(`[data-raid-prep-task="${row.id}"]`)
          ?.scrollIntoView({ block: "nearest" });
      }, 0);
    },
    [ensureGeometry, mapId, objDoneView, overlayTasks],
  );

  const openGuide = useCallback((taskId: string) => {
    setGuideTaskId(taskId);
    setGuideOpen(true);
  }, []);

  const onQuestLabelClick = useCallback(
    (taskId: string) => {
      setHighlightTaskId(taskId);
      openGuide(taskId);
    },
    [openGuide],
  );

  return {
    taskStatusOf,
    toggleObjDone,
    changeTaskStatus,
    locateTask,
    guideOpen,
    setGuideOpen,
    guideTaskId,
    setGuideTaskId,
    openGuide,
    onQuestLabelClick,
    highlightTaskId,
    setHighlightTaskId,
    focusRequest,
  };
}
