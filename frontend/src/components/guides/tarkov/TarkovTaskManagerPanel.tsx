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
import { apiError } from "@/lib/apiError";
import {
  isFileSystemAccessSupported,
  isPickerAbort,
  loadStoredLogsDir,
  queryLogsDirPermission,
  readLogsIndex,
  readSessionLogs,
  requestLogsDirPermission,
  type ReadableDir,
} from "@/lib/tarkovGameLogAccess";
import { parseTarkovLogBundle, takeSessionStubs } from "@/lib/tarkovGameLogs";
import { nowBeijingStamp } from "@/lib/time";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_TRADERS, tarkovTaskHref } from "@/lib/tarkovHomeNav";
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
import {
  formatLastQuestSyncLine,
  formatQuestSyncDeltaLine,
  mergeQuestProgressFromLogs,
  questProgressDelta,
} from "@/lib/tarkovTaskLogSync";
import {
  describeTaskMap,
  factionTaskSuffix,
  groupTasksByTrader,
  loadTaskDoneIds,
  loadTaskStartedIds,
  loadTaskSyncAt,
  resolveAccountTaskProgress,
  resolveTaskStatus,
  saveTaskProgress,
  saveTaskSyncMark,
  setTaskStatus,
  summarizeTaskProgress,
  taskProgressQueryData,
  type TaskProgressSummary,
  type TaskStatusKind,
  type TraderTaskGroup,
} from "@/lib/tarkovTaskTree";
import trade from "./TarkovGuideTrade.module.css";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovTaskManagerPanel.module.css";

function traderFilterLabel(slug: string, apiName: string): {
  english: string;
  chinese: string;
} {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return { english: known.english, chinese: known.chinese };
  const match = apiName.match(/^(.*?)\s*[（(](.+?)[）)]\s*$/);
  if (match) {
    return { english: match[1].trim(), chinese: match[2].trim() };
  }
  return { english: apiName, chinese: "" };
}

function requestStatus(error: unknown): number | undefined {
  if (!error || typeof error !== "object") return undefined;
  return (error as { response?: { status?: number } }).response?.status;
}

function friendlyError(error: unknown, fallback: string): string {
  if (isPickerAbort(error)) return "";
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function rankTask(
  id: string,
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
): number {
  if (done.has(id)) return 2;
  if (started.has(id)) return 0;
  return 1;
}

function sortTasksForBoard(
  items: TarkovTaskListItem[],
  done: ReadonlySet<string>,
  started: ReadonlySet<string>,
): TarkovTaskListItem[] {
  return [...items].sort((a, b) => {
    const diff = rankTask(a.id, done, started) - rankTask(b.id, done, started);
    if (diff !== 0) return diff;
    return (a.name || a.id).localeCompare(b.name || b.id, "zh-CN");
  });
}

function formatBoardMeta(count: TaskProgressSummary, visible: number): string {
  const bits = [`显示 ${visible}`];
  if (count.active) bits.push(`进行中 ${count.active}`);
  if (count.completed) bits.push(`已完成 ${count.completed}`);
  return bits.join(" · ");
}

const TASK_STATUS_OPTIONS: { value: TaskStatusKind; label: string }[] = [
  { value: "todo", label: "未完成" },
  { value: "active", label: "进行中" },
  { value: "done", label: "已完成" },
];

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

function TaskRow({
  task,
  complete,
  active,
  onSetStatus,
  typeColumns,
}: {
  task: TarkovTaskListItem;
  complete: boolean;
  active: boolean;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  typeColumns: string[];
}) {
  const label = `${task.name || task.id}${factionTaskSuffix(task.faction_name)}`;
  const status: TaskStatusKind = complete ? "done" : active ? "active" : "todo";
  const mapMark = describeTaskMap(task);
  const typeSet = new Set(orderObjectiveTypes(task.objective_types));
  return (
    <tr
      className={`${styles.row} ${
        status === "done"
          ? styles.rowDone
          : status === "active"
            ? styles.rowActive
            : ""
      }`}
    >
      <td className={styles.cellName}>
        <Link className={styles.name} to={tarkovTaskHref(task.id)}>
          {label}
        </Link>
      </td>
      <td className={styles.cellStatus}>
        <select
          className={`${styles.statusSelect}${
            status === "done"
              ? ` ${styles.statusSelectDone}`
              : status === "active"
                ? ` ${styles.statusSelectActive}`
                : ""
          }`}
          aria-label={`${label} 状态`}
          value={status}
          onChange={(event) =>
            onSetStatus(task.id, event.target.value as TaskStatusKind)
          }
        >
          {TASK_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </td>
      <td className={styles.cellMap}>
        {mapMark ? (
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
        ) : null}
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
  const done = useMemo(() => new Set(doneIds), [doneIds]);
  const started = useMemo(() => new Set(startedIds), [startedIds]);
  const [syncing, setSyncing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scan, setScan] = useState<{ done: number; total: number } | null>(null);
  const [lastSyncAt, setLastSyncAt] = useState(() => loadTaskSyncAt(gameMode));

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
      );
      queryClient.setQueryData(
        ["guides-tarkov-task-dones", gameMode],
        taskProgressQueryData(nextDone, cleanedStarted),
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
      applyProgress(detail.done, detail.started);
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () => window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [applyProgress, gameMode]);

  const applyServerProgress = useCallback(
    (data: { task_ids?: string[]; started_ids?: string[] }) => {
      applyProgress(
        data.task_ids || [],
        data.started_ids || [],
        true,
        true,
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
    applyProgress(next.done, next.started, false);
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
    () => summarizeTaskProgress(scopedItems, done, started),
    [done, scopedItems, started],
  );
  const groups = useMemo(
    () =>
      groupTasksByTrader(items, traderChips, done, {
        q,
      }).filter((group) => !trader || group.traderSlug === trader),
    [done, items, q, trader, traderChips],
  );
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
          labels: traderFilterLabel(item.slug, item.name),
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

  const changeStatus = (taskId: string, status: TaskStatusKind) => {
    const current = resolveTaskStatus(
      taskId,
      new Set(doneIdsRef.current),
      new Set(startedIdsRef.current),
    );
    if (current === status) return;
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

  const ensureLogsDir = async (): Promise<ReadableDir | null> => {
    if (!isFileSystemAccessSupported()) {
      message.warning("当前浏览器不能读取本机目录，请用 Chrome 或 Edge。");
      return null;
    }
    const stored = await loadStoredLogsDir();
    if (!stored) {
      message.info("先到「日志路径」绑定游戏日志目录。");
      return null;
    }
    const current = await queryLogsDirPermission(stored);
    const granted =
      current === "granted" ? current : await requestLogsDirPermission(stored);
    if (granted !== "granted") {
      message.warning("浏览器没有批准读取该日志目录。");
      return null;
    }
    return stored;
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

  const syncFromLogs = async () => {
    if (syncing) return;
    setSyncing(true);
    setScan(null);
    try {
      const handle = await ensureLogsDir();
      if (!handle) return;
      const { sessions } = await readLogsIndex(handle);
      const targets = takeSessionStubs(sessions, 0);
      if (!targets.length) {
        message.info("这个目录里没有启动记录。");
        return;
      }
      setScan({ done: 0, total: targets.length });
      const parsedSessions = [];
      for (const [index, stub] of targets.entries()) {
        const read = await readSessionLogs(handle, stub.folder);
        parsedSessions.push({
          folder: stub.folder,
          parsed: parseTarkovLogBundle(read.files),
        });
        setScan({ done: index + 1, total: targets.length });
      }
      const prevDone = doneIdsRef.current;
      const prevStarted = startedIdsRef.current;
      const hadSync = Boolean(lastSyncAt);
      const merged = mergeQuestProgressFromLogs(
        prevDone,
        prevStarted,
        parsedSessions,
        gameMode,
        knownIds,
      );
      touchedRef.current = true;
      applyProgress(merged.done, merged.started);
      writeMut.mutate({ done: merged.done, started: merged.started });
      stampSync();
      message.success(
        formatQuestSyncDeltaLine(
          hadSync ? "incremental" : "backfill",
          questProgressDelta(prevDone, prevStarted, merged.done, merged.started),
        ),
      );
    } catch (error) {
      const text = friendlyError(error, "") || apiError(error, "同步日志失败");
      if (text) message.error(text);
    } finally {
      setScan(null);
      setSyncing(false);
    }
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

  const allOn = !trader;
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
            <div
              key={row.key}
              className={`${styles.stat} ${row.tone}`}
              style={{ flexGrow: row.value || 1 }}
            >
              <div className={styles.statLabel}>{row.label}</div>
              <div className={styles.statValue}>{row.value}</div>
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
                      disabled={syncing}
                      onClick={() => void syncFromLogs()}
                    >
                      {syncing ? "正在同步…" : "同步日志"}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
            <span className={styles.syncHint}>
              {scan
                ? `正在读取 ${scan.done} / ${scan.total}`
                : formatLastQuestSyncLine(lastSyncAt)}
            </span>
          </div>
          <div className={styles.rail} role="radiogroup" aria-label="按商人筛选">
            <button
              type="button"
              role="radio"
              aria-checked={allOn}
              className={`${styles.traderBtn} ${styles.traderAll}${allOn ? ` ${styles.traderOn}` : ""}`}
              onClick={() => setTraderFilter(null)}
            >
              全部
            </button>
            {traderNav.map(({ item, labels, count }) => {
              const selected = trader === item.slug;
              const pct = count.total
                ? Math.round((count.completed / count.total) * 100)
                : 0;
              return (
                <button
                  key={item.slug || item.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  aria-label={
                    labels.chinese
                      ? `${labels.english}（${labels.chinese}）`
                      : labels.english
                  }
                  title={
                    labels.chinese
                      ? `${labels.english}（${labels.chinese}）`
                      : labels.english
                  }
                  className={`${styles.traderBtn}${selected ? ` ${styles.traderOn}` : ""}`}
                  onClick={() => setTraderFilter(item.slug)}
                >
                  <TarkovTraderThumb slug={item.slug} size={36} />
                  <span className={styles.traderCaption}>
                    <span className={styles.traderName}>
                      {labels.chinese || labels.english}
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
          {groups.length ? (
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
  const labels = traderFilterLabel(group.traderSlug, group.traderName);
  const title = labels.chinese
    ? `${labels.english} · ${labels.chinese}`
    : group.traderName || "未知商人";
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
          {formatBoardMeta(count, group.items.length)}
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
              complete={done.has(item.id)}
              active={started.has(item.id)}
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
