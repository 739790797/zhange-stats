import { Alert, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovTaskDones,
  fetchTarkovTasks,
  writeTarkovTaskDones,
  type TarkovTaskListItem,
} from "@/api/guidesApi";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { TarkovTaskFlowBoard } from "@/components/guides/tarkov/TarkovTaskFlowBoard";
import { apiError } from "@/lib/apiError";
import { nowBeijingStamp } from "@/lib/time";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovTaskHref, traderDisplayName } from "@/lib/tarkovHomeNav";
import {
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  notifyTarkovTaskProgress,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { formatLastQuestSyncLine } from "@/lib/tarkovTaskLogSync";
import { TarkovLogSyncRangeModal } from "@/components/guides/tarkov/TarkovLogSyncRangeModal";
import { useTarkovLogSyncDialog } from "@/lib/useTarkovLogSyncDialog";
import {
  describeTaskMap,
  displayTaskProgressName,
  groupTasksByTrader,
  isWritableTaskStatus,
  keepCatalogTaskProgress,
  loadTaskDoneIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  loadTaskSyncAt,
  resolveAccountTaskProgress,
  resolveTaskStatus,
  saveTaskProgress,
  saveTaskSyncMark,
  setTaskStatus,
  summarizeTaskProgress,
  taskMatchesQuery,
  taskProgressQueryData,
  TASK_STATUS_KINDS,
  TASK_STATUS_LABELS,
  type TaskProgressSummary,
  type TaskStatusKind,
  type TraderTaskGroup,
} from "@/lib/tarkovTaskTree";
import {
  buildTaskForest,
  countForestTasks,
  filterTaskForest,
  loadTaskProgressView,
  saveTaskProgressView,
  tarkovFlowTaskAnchor,
  tarkovFlowTraderAnchor,
  type TaskProgressView,
} from "@/lib/tarkovTaskForest";
import trade from "./TarkovGuideTrade.module.css";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovTaskManagerPanel.module.css";

function requestStatus(error: unknown): number | undefined {
  if (!error || typeof error !== "object") return undefined;
  return (error as { response?: { status?: number } }).response?.status;
}

const TASK_STATUS_RANK: Record<TaskStatusKind, number> = {
  active: 0,
  todo: 1,
  failed: 2,
  unreachable: 3,
  done: 4,
};

function rankTask(
  task: TarkovTaskListItem,
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
): number {
  return TASK_STATUS_RANK[resolveTaskStatus(task.id, done, started, task)];
}

function sortTasksForBoard(
  items: TarkovTaskListItem[],
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
): TarkovTaskListItem[] {
  return [...items].sort((a, b) => {
    const diff = rankTask(a, done, started) - rankTask(b, done, started);
    if (diff !== 0) return diff;
    return (a.name || a.id).localeCompare(b.name || b.id, "zh-CN");
  });
}

function formatBoardMeta(count: TaskProgressSummary, visible: number): string {
  const bits = [`显示 ${visible}`];
  if (count.active) bits.push(`进行中 ${count.active}`);
  if (count.failed) bits.push(`失败 ${count.failed}`);
  if (count.unreachable) bits.push(`无法完成 ${count.unreachable}`);
  if (count.completed) bits.push(`已完成 ${count.completed}`);
  return bits.join(" · ");
}

const TASK_STATUS_OPTIONS: { value: TaskStatusKind; label: string }[] =
  TASK_STATUS_KINDS.map((value) => ({
    value,
    label: TASK_STATUS_LABELS[value],
  }));

function collectTypeColumns(items: TarkovTaskListItem[]): string[] {
  const seen = new Set<string>();
  for (const item of items) {
    for (const raw of item.objective_types || []) {
      const key = String(raw || "").trim();
      if (key) seen.add(key);
    }
  }
  return orderObjectiveTypes([...seen]);
}

function statusRowClass(status: TaskStatusKind): string {
  if (status === "done") return styles.rowDone;
  if (status === "active") return styles.rowActive;
  if (status === "failed") return styles.rowFailed;
  if (status === "unreachable") return styles.rowUnreachable;
  return "";
}

function TaskStatusSelect({
  task,
  done,
  started,
  onSetStatus,
}: {
  task: TarkovTaskListItem;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
}) {
  const label = displayTaskProgressName(task);
  const status = resolveTaskStatus(task.id, done, started, task);
  const derived = !isWritableTaskStatus(status);
  return (
    <select
      className={`${styles.statusSelect}${
        status === "done"
          ? ` ${styles.statusSelectDone}`
          : status === "active"
            ? ` ${styles.statusSelectActive}`
            : status === "failed"
              ? ` ${styles.statusSelectFailed}`
              : status === "unreachable"
                ? ` ${styles.statusSelectUnreachable}`
                : ""
      }`}
      aria-label={`${label} 状态`}
      value={status}
      disabled={derived}
      onChange={(event) =>
        onSetStatus(task.id, event.target.value as TaskStatusKind)
      }
    >
      {TASK_STATUS_OPTIONS.map((option) => (
        <option
          key={option.value}
          value={option.value}
          disabled={
            !isWritableTaskStatus(option.value) && option.value !== status
          }
        >
          {option.label}
        </option>
      ))}
    </select>
  );
}

function TaskMapMark({ task }: { task: TarkovTaskListItem }) {
  const mapMark = describeTaskMap(task);
  if (!mapMark) return null;
  return (
    <span
      className={styles.rowMap}
      title={
        mapMark.english
          ? `${mapMark.label}（${mapMark.english}）`
          : mapMark.label
      }
    >
      <MapGlyph icon={mapMark.icon} />
      <span>{mapMark.label}</span>
    </span>
  );
}

function TaskRow({
  task,
  done,
  started,
  onSetStatus,
  typeColumns,
}: {
  task: TarkovTaskListItem;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  typeColumns: string[];
}) {
  const label = displayTaskProgressName(task);
  const status = resolveTaskStatus(task.id, done, started, task);
  const typeSet = new Set(orderObjectiveTypes(task.objective_types));
  return (
    <tr className={`${styles.row} ${statusRowClass(status)}`}>
      <td className={styles.cellName}>
        <Link className={styles.name} to={tarkovTaskHref(task.id)}>
          {label}
        </Link>
      </td>
      <td className={styles.cellStatus}>
        <TaskStatusSelect
          task={task}
          done={done}
          started={started}
          onSetStatus={onSetStatus}
        />
      </td>
      <td className={styles.cellMap}>
        <TaskMapMark task={task} />
      </td>
      {typeColumns.map((type) => (
        <td key={type} className={styles.cellType}>
          {typeSet.has(type) ? (
            <span
              className={`${taskStyles.typeChip} ${styles.typeHit}`}
              data-tone={tarkovObjectiveTypeTone(type)}
              title={tarkovObjectiveTypeLabel(type)}
            />
          ) : null}
        </td>
      ))}
    </tr>
  );
}

function MapGlyph({ icon }: { icon: string }) {
  if (!icon) return null;
  return (
    <svg className={styles.mapGlyph} viewBox="0 0 24 24" aria-hidden>
      <path d={icon} fill="currentColor" />
    </svg>
  );
}


export function TarkovTaskManagerPanel() {
  const gameMode = useTarkovGameMode();
  const logSync = useTarkovLogSyncDialog();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const trader = (searchParams.get("trader") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);
  const hydratedModeRef = useRef("");
  const touchedRef = useRef(false);
  const [doneIds, setDoneIds] = useState<string[]>(() => loadTaskDoneIds(gameMode));
  const [startedIds, setStartedIds] = useState<string[]>(() =>
    loadTaskStartedIds(gameMode),
  );
  const doneIdsRef = useRef(doneIds);
  const startedIdsRef = useRef(startedIds);
  doneIdsRef.current = doneIds;
  startedIdsRef.current = startedIds;
  const [saving, setSaving] = useState(false);
  const [lastSyncAt, setLastSyncAt] = useState(() => loadTaskSyncAt(gameMode));
  const [flowHighlightTrader, setFlowHighlightTrader] = useState("");
  const [flowHighlightTask, setFlowHighlightTask] = useState("");
  const [flowVisibleTrader, setFlowVisibleTrader] = useState("");
  const [progressView, setProgressView] = useState<TaskProgressView>(
    loadTaskProgressView,
  );

  useEffect(() => {
    setDoneIds(loadTaskDoneIds(gameMode));
    setStartedIds(loadTaskStartedIds(gameMode));
    setLastSyncAt(loadTaskSyncAt(gameMode));
    hydratedModeRef.current = "";
    touchedRef.current = false;
  }, [gameMode]);

  const applyProgress = useCallback(
    (
      nextDone: string[],
      nextStarted: string[],
      migrated = true,
      startedMigrated = false,
      objectives?: Array<{ task_id: string; objective_id: string }>,
    ) => {
      const cleanedStarted = nextStarted.filter((id) => !nextDone.includes(id));
      doneIdsRef.current = nextDone;
      startedIdsRef.current = cleanedStarted;
      setDoneIds(nextDone);
      setStartedIds(cleanedStarted);
      saveTaskProgress(
        gameMode,
        nextDone,
        cleanedStarted,
        migrated,
        startedMigrated,
        objectives,
      );
      queryClient.setQueryData(
        ["guides-tarkov-task-dones", gameMode],
        taskProgressQueryData(
          nextDone,
          cleanedStarted,
          objectives ?? loadTaskObjectivePairs(gameMode),
        ),
      );
    },
    [gameMode, queryClient],
  );

  useEffect(() => {
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode) return;
      if (detail.syncedAt) setLastSyncAt(detail.syncedAt);
      if (detail.changed === false) return;
      touchedRef.current = true;
      applyProgress(detail.done, detail.started, true, false, detail.objectives);
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () => window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [applyProgress, gameMode]);

  const applyServerProgress = useCallback(
    (data: {
      task_ids?: string[];
      started_ids?: string[];
      objective_dones?: Array<{ task_id: string; objective_id: string }>;
    }) => {
      applyProgress(
        data.task_ids || [],
        data.started_ids || [],
        true,
        true,
        data.objective_dones,
      );
    },
    [applyProgress],
  );

  const donesQuery = useQuery({
    queryKey: ["guides-tarkov-task-dones", gameMode],
    queryFn: fetchTarkovTaskDones,
    staleTime: 60_000,
    retry: 1,
  });

  const writeMut = useMutation({
    mutationFn: (payload: { done: string[]; started: string[] }) =>
      writeTarkovTaskDones(payload.done, {
        startedIds: payload.started,
        objectiveDones: loadTaskObjectivePairs(gameMode),
      }),
    onSuccess: (data) => applyServerProgress(data),
    onError: async (error) => {
      if (requestStatus(error) === 401) return;
      const result = await donesQuery.refetch();
      if (result.data) applyServerProgress(result.data);
    },
  });

  useEffect(() => {
    if (!donesQuery.isSuccess || donesQuery.data == null) return;
    if (hydratedModeRef.current === gameMode) return;
    hydratedModeRef.current = gameMode;
    if (touchedRef.current) return;
    const next = resolveAccountTaskProgress(donesQuery.data, gameMode);
    applyProgress(next.done, next.started, false, false, next.objectives);
  }, [applyProgress, donesQuery.data, donesQuery.isSuccess, gameMode]);

  useEffect(() => {
    setKeyword(q);
    qRef.current = q;
  }, [q]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = keyword.trim();
      if (qRef.current === next) return;
      qRef.current = next;
      const params = new URLSearchParams(searchParams);
      if (next) params.set("q", next);
      else params.delete("q");
      setSearchParams(params, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword, searchParams, setSearchParams]);

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-task-list", gameMode],
    queryFn: () => fetchTarkovTasks({ layout: "all" }),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const items = useMemo(
    () => catalogQuery.data?.items ?? [],
    [catalogQuery.data],
  );
  const traders = useMemo(
    () => catalogQuery.data?.traders ?? [],
    [catalogQuery.data],
  );
  const traderChips = useMemo(
    () => traders.map((item) => ({ slug: item.slug, name: item.name })),
    [traders],
  );
  const knownIds = useMemo(() => new Set(items.map((item) => item.id)), [items]);
  const visibleProgress = useMemo(
    () =>
      keepCatalogTaskProgress(
        doneIds,
        startedIds,
        catalogQuery.data ? knownIds : null,
      ),
    [catalogQuery.data, doneIds, knownIds, startedIds],
  );
  const done = useMemo(
    () => new Set(visibleProgress.done),
    [visibleProgress],
  );
  const started = useMemo(
    () => new Set(visibleProgress.started),
    [visibleProgress],
  );

  const itemsByTrader = useMemo(() => {
    const map = new Map<string, TarkovTaskListItem[]>();
    for (const item of items) {
      const slug = item.trader_slug || "";
      const list = map.get(slug) || [];
      list.push(item);
      map.set(slug, list);
    }
    return map;
  }, [items]);

  const scopedItems = useMemo(
    () => (trader ? itemsByTrader.get(trader) ?? [] : items),
    [items, itemsByTrader, trader],
  );

  const summary = useMemo(
    () =>
      summarizeTaskProgress(
        progressView === "tree" ? items : scopedItems,
        done,
        started,
      ),
    [done, items, progressView, scopedItems, started],
  );
  const itemById = useMemo(() => {
    const map = new Map<string, TarkovTaskListItem>();
    for (const item of items) map.set(item.id, item);
    return map;
  }, [items]);
  const groups = useMemo(
    () =>
      groupTasksByTrader(items, traderChips, done, {
        q,
      }).filter((group) => !trader || group.traderSlug === trader),
    [done, items, q, trader, traderChips],
  );
  const treeBoards = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return groupTasksByTrader(items, traderChips, done, {})
      .map((group) => {
        const native = group.items as TarkovTaskListItem[];
        const built = buildTaskForest(native);
        const forest = needle
          ? filterTaskForest(built, (row) => taskMatchesQuery(row, needle))
          : built;
        return {
          traderSlug: group.traderSlug,
          traderName: group.traderName,
          forest,
          count: summarizeTaskProgress(native, done, started),
          visible: countForestTasks(forest),
        };
      })
      .filter((row) => row.visible > 0);
  }, [done, items, q, started, traderChips]);
  const typeColumns = useMemo(
    () => collectTypeColumns(scopedItems),
    [scopedItems],
  );
  const traderNav = useMemo(
    () =>
      traders.map((item) => {
        const rows = itemsByTrader.get(item.slug) ?? [];
        return {
          item,
          labels: { english: traderDisplayName(item.slug, item.name) },
          count: summarizeTaskProgress(rows, done, started),
        };
      }),
    [done, itemsByTrader, started, traders],
  );

  const setTraderFilter = (nextTrader: string | null) => {
    const params = new URLSearchParams(searchParams);
    if (!nextTrader) params.delete("trader");
    else params.set("trader", nextTrader);
    setSearchParams(params, { replace: true });
  };

  const locateFlowTrader = (slug: string | null) => {
    const params = new URLSearchParams(searchParams);
    if (!slug) {
      params.delete("trader");
      setSearchParams(params, { replace: true });
      setFlowHighlightTrader("");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    params.set("trader", slug);
    setSearchParams(params, { replace: true });
    window.setTimeout(() => {
      document
        .getElementById(tarkovFlowTraderAnchor(slug))
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
    setFlowHighlightTrader(slug);
    window.setTimeout(() => setFlowHighlightTrader(""), 1600);
  };

  const jumpToFlowTask = (taskId: string) => {
    const el = document.getElementById(tarkovFlowTaskAnchor(taskId));
    if (el) {
      el.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "center",
      });
      setFlowHighlightTask(taskId);
      window.setTimeout(() => setFlowHighlightTask(""), 1600);
      return;
    }
    const slug = (itemById.get(taskId)?.trader_slug || "").trim();
    if (slug) locateFlowTrader(slug);
  };

  const onVisibleTrader = useCallback((slug: string) => {
    setFlowVisibleTrader(slug);
  }, []);

  const changeProgressView = (next: TaskProgressView) => {
    setProgressView(next);
    saveTaskProgressView(next);
  };

  const changeStatus = (taskId: string, status: TaskStatusKind) => {
    if (!isWritableTaskStatus(status)) return;
    const task = items.find((row) => row.id === taskId);
    const current = resolveTaskStatus(
      taskId,
      new Set(doneIdsRef.current),
      new Set(startedIdsRef.current),
      task,
    );
    if (current === status) return;
    if (!isWritableTaskStatus(current)) return;
    const next = setTaskStatus(
      doneIdsRef.current,
      startedIdsRef.current,
      taskId,
      status,
    );
    touchedRef.current = true;
    applyProgress(next.done, next.started);
    notifyTarkovTaskProgress({
      mode: gameMode,
      done: next.done,
      started: next.started,
      changed: true,
      source: "user",
    });
    writeMut.mutate({ done: next.done, started: next.started });
  };

  const stampSync = () => {
    const syncedAt = nowBeijingStamp();
    const marked = saveTaskSyncMark(gameMode, syncedAt);
    setLastSyncAt(marked.syncedAt);
    notifyTarkovTaskProgress({
      mode: gameMode,
      done: doneIdsRef.current,
      started: startedIdsRef.current,
      syncedAt: marked.syncedAt,
      changed: false,
      source: "user",
    });
    return marked;
  };

  const saveProgress = () => {
    if (saving || writeMut.isPending) return;
    setSaving(true);
    touchedRef.current = true;
    applyProgress(doneIdsRef.current, startedIdsRef.current);
    stampSync();
    writeMut.mutate(
      { done: doneIdsRef.current, started: startedIdsRef.current },
      {
        onSettled: () => setSaving(false),
      },
    );
    message.success("已保存进度");
  };

  if (catalogQuery.isLoading && !catalogQuery.data) {
    return (
      <div className={trade.status}>
        <Spin tip="加载任务…" />
      </div>
    );
  }

  if (catalogQuery.isError && !catalogQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="任务列表加载失败"
        description={apiError(catalogQuery.error, "任务列表加载失败")}
      />
    );
  }

  const flowSelected =
    progressView === "tree" ? flowVisibleTrader || trader : trader;
  const allOn = !flowSelected;
  const statSegments = (
    [
      {
        key: "done",
        label: "已完成",
        value: summary.completed,
        tone: styles.statDone,
        bar: styles.meterDone,
      },
      {
        key: "active",
        label: "进行中",
        value: summary.active,
        tone: styles.statActive,
        bar: styles.meterActive,
      },
      {
        key: "todo",
        label: "未完成",
        value: summary.incomplete,
        tone: styles.statTodo,
        bar: styles.meterTodo,
      },
      {
        key: "failed",
        label: "失败",
        value: summary.failed,
        tone: styles.statFailed,
        bar: styles.meterFailed,
      },
      {
        key: "unreachable",
        label: "无法完成",
        value: summary.unreachable,
        tone: styles.statUnreachable,
        bar: styles.meterUnreachable,
      },
    ] as const
  ).filter((row) => row.value > 0);
  const shownStats = statSegments.length
    ? statSegments
    : [
        {
          key: "empty",
          label: "未完成",
          value: 0,
          tone: styles.statTodo,
          bar: styles.meterTodo,
        },
      ];

  return (
    <div className={styles.stack}>
      {catalogQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="任务列表加载失败"
          description={apiError(catalogQuery.error, "任务列表加载失败")}
        />
      ) : null}

      <section className={styles.overview}>
        <div className={styles.stats}>
          {shownStats.map((row) => (
            <div key={row.key} className={`${styles.stat} ${row.tone}`}>
              <span className={styles.statLabel}>{row.label}</span>
              <span className={styles.statValue}>{row.value}</span>
            </div>
          ))}
        </div>
        <div className={styles.meter} aria-hidden>
          {shownStats.map((row) => (
            <span
              key={row.key}
              className={row.bar}
              style={{ flexGrow: row.value || 1 }}
            />
          ))}
        </div>
      </section>

      <div className={styles.workspace}>
        <aside className={styles.side}>
          <div className={styles.filters}>
            <input
              className={styles.search}
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索任务名"
              aria-label="搜索任务"
            />
            <table className={styles.filterTable}>
              <tbody>
                <tr>
                  <td>
                    <button
                      type="button"
                      className={`${styles.viewBtn}${
                        progressView === "list" ? ` ${styles.viewOn}` : ""
                      }`}
                      aria-pressed={progressView === "list"}
                      onClick={() => changeProgressView("list")}
                    >
                      列表
                    </button>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={`${styles.viewBtn}${
                        progressView === "tree" ? ` ${styles.viewOn}` : ""
                      }`}
                      aria-pressed={progressView === "tree"}
                      onClick={() => changeProgressView("tree")}
                    >
                      流程图
                    </button>
                  </td>
                </tr>
                <tr>
                  <td>
                    <button
                      type="button"
                      className={styles.saveBtn}
                      disabled={saving}
                      onClick={saveProgress}
                    >
                      {saving ? "正在保存…" : "保存进度"}
                    </button>
                  </td>
                  <td>
                    <button
                      type="button"
                      className={styles.syncBtn}
                      disabled={logSync.listing}
                      title={logSync.title}
                      onClick={() => void logSync.openDialog()}
                    >
                      {logSync.label}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <span className={styles.syncHint}>
              {logSync.scan
                ? `正在解析 ${logSync.scan.done} / ${logSync.scan.total}`
                : formatLastQuestSyncLine(lastSyncAt)}
            </span>
          </div>
          <div className={styles.rail} role="radiogroup" aria-label="按商人筛选">
            <button
              type="button"
              role="radio"
              aria-checked={allOn}
              className={`${styles.traderBtn} ${styles.traderAll}${allOn ? ` ${styles.traderOn}` : ""}`}
              onClick={() =>
                progressView === "tree"
                  ? locateFlowTrader(null)
                  : setTraderFilter(null)
              }
            >
              全部
            </button>
            {traderNav.map(({ item, labels, count }) => {
              const selected = flowSelected === item.slug;
              const pct = count.total
                ? Math.round((count.completed / count.total) * 100)
                : 0;
              return (
                <button
                  key={item.slug || item.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  aria-label={labels.english}
                  title={labels.english}
                  className={`${styles.traderBtn}${selected ? ` ${styles.traderOn}` : ""}`}
                  onClick={() =>
                    progressView === "tree"
                      ? locateFlowTrader(item.slug)
                      : setTraderFilter(item.slug)
                  }
                >
                  <TarkovTraderThumb slug={item.slug} size={36} />
                  <span className={styles.traderCaption}>
                    <span className={styles.traderName}>
                      {labels.english}
                    </span>
                    <span className={styles.traderMeta}>
                      <span
                        className={`${styles.traderCount}${
                          count.total > 0 && count.completed === count.total
                            ? ` ${styles.traderCountDone}`
                            : ""
                        }`}
                      >
                        {count.completed}
                      </span>
                      <span className={styles.bar} aria-hidden>
                        <span className={styles.barFill} style={{ width: `${pct}%` }} />
                      </span>
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className={styles.board}>
          {progressView === "tree" ? (
            <TarkovTaskFlowBoard
              lanes={treeBoards}
              done={done}
              started={started}
              itemById={itemById}
              highlightTrader={flowHighlightTrader}
              highlightTask={flowHighlightTask}
              onSetStatus={changeStatus}
              onJumpTask={jumpToFlowTask}
              onVisibleTrader={onVisibleTrader}
            />
          ) : groups.length ? (
            groups.map((group) => (
              <TraderGroup
                key={group.traderSlug || "none"}
                group={group}
                count={summarizeTaskProgress(
                  itemsByTrader.get(group.traderSlug) ?? group.items,
                  done,
                  started,
                )}
                done={done}
                started={started}
                typeColumns={typeColumns}
                onSetStatus={changeStatus}
              />
            ))
          ) : (
            <div className={styles.empty}>当前筛选下无任务</div>
          )}
        </div>
      </div>
      <TarkovLogSyncRangeModal
        open={logSync.open}
        sessions={logSync.sessions}
        onCancel={logSync.closeDialog}
        onConfirm={logSync.confirm}
      />
    </div>
  );
}

function TraderGroup({
  group,
  count,
  done,
  started,
  typeColumns,
  onSetStatus,
}: {
  group: TraderTaskGroup;
  count: TaskProgressSummary;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  typeColumns: string[];
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
}) {
  const title =
    traderDisplayName(group.traderSlug, group.traderName) || "未知商人";
  const rows = sortTasksForBoard(
    group.items as TarkovTaskListItem[],
    done,
    started,
  );
  return (
    <section className={styles.group}>
      <h3 className={styles.traderHead}>
        <span className={styles.traderHeadTitle}>
          {group.traderSlug ? (
            <TarkovTraderThumb
              slug={group.traderSlug}
              size={28}
              title={title}
            />
          ) : null}
          <span>{title}</span>
        </span>
        <span className={styles.sectionMeta}>
          {formatBoardMeta(count, rows.length)}
        </span>
      </h3>
      <div className={styles.tableWrap}>
      <table className={styles.table}>
        <colgroup>
          <col className={styles.colName} />
          <col className={styles.colStatus} />
          <col className={styles.colMap} />
          {typeColumns.map((type) => (
            <col key={type} className={styles.colType} />
          ))}
        </colgroup>
        <thead>
          <tr>
            <th className={styles.cellName} scope="col">
              任务
            </th>
            <th className={styles.cellStatus} scope="col">
              状态
            </th>
            <th className={styles.cellMap} scope="col">
              地点
            </th>
            {typeColumns.map((type) => (
              <th
                key={type}
                className={styles.cellType}
                scope="col"
                title={type}
              >
                {tarkovObjectiveTypeLabel(type)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <TaskRow
              key={item.id}
              task={item}
              done={done}
              started={started}
              typeColumns={typeColumns}
              onSetStatus={onSetStatus}
            />
          ))}
        </tbody>
      </table>
      </div>
    </section>
  );
}
