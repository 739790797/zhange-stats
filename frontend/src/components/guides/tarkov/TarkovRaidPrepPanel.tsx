import { Alert, Spin, message } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovKeyOwns,
  fetchTarkovMapDetail,
  fetchTarkovRaidPrep,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovMapHref } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  filterRaidPrepRows,
  normalizeRaidPrepMapId,
  parseCsvParam,
  partitionRaidPrepRows,
  planRaidPrepTaskProgressSync,
  raidPrepMapOptions,
  raidPrepObjectiveDoneScope,
  raidPrepSkippedIds,
  resolveRaidPrepLocatePoints,
  selectedTasksFromCatalog,
  serializeSelectedIds,
  skipMapToObjectiveDones,
  useRaidPrepObjectiveDone,
} from "@/lib/tarkovRaidPrep";
import { mergeRaidPrepOcrSelection } from "@/lib/tarkovRaidPrepOcr";
import { keyOwnsForUser } from "@/lib/tarkovRaidRooms";
import { loadTaskDoneIds, loadTaskStartedIds } from "@/lib/tarkovTaskTree";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovRaidPrepFilters } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import {
  TarkovRaidPrepEntryModal,
  raidPrepEntryFallbackPath,
} from "@/components/guides/tarkov/TarkovRaidPrepEntryModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import { TarkovRaidPrepOcrModal } from "@/components/guides/tarkov/TarkovRaidPrepOcrModal";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import { useAuthStore } from "@/stores/authStore";
import catalogCss from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

export function TarkovRaidPrepPanel() {
  const gameMode = useTarkovGameMode();
  const navigate = useNavigate();
  const me = useAuthStore((s) => s.user);
  const [searchParams, setSearchParams] = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const mapId = normalizeRaidPrepMapId(searchParams.get("map") || "");
  const trader = (searchParams.get("trader") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const selected = parseCsvParam(searchParams.get("sel"));
  const [keyword, setKeyword] = useState(q);
  const [entryOpen, setEntryOpen] = useState(!mapId);
  const [changeMapOpen, setChangeMapOpen] = useState(false);
  const [ocrOpen, setOcrOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useState(false);
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const [objDone, toggleObjDone] = useRaidPrepObjectiveDone(
    raidPrepObjectiveDoneScope("solo", mapId),
  );
  const ownsQuery = useQuery({
    queryKey: ["guides-tarkov-key-owns"],
    queryFn: fetchTarkovKeyOwns,
    staleTime: 60_000,
  });
  const myName = (me?.display_name || me?.username || "").trim() || (me ? `用户${me.id}` : "");
  const keyOwns = useMemo(
    () =>
      keyOwnsForUser(ownsQuery.data?.item_ids, me ? { userId: me.id, name: myName } : null),
    [ownsQuery.data?.item_ids, me, myName],
  );
  const focusSeqRef = useRef(0);
  const locateIndexRef = useRef<Record<string, number>>({});
  const qRef = useRef(q);

  useEffect(() => {
    setKeyword(q);
    qRef.current = q;
  }, [q]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = keyword.trim();
      if (qRef.current === next) return;
      qRef.current = next;
      const params = new URLSearchParams(searchParamsRef.current);
      if (next) params.set("q", next);
      else params.delete("q");
      setSearchParams(params, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword, setSearchParams]);

  useEffect(() => {
    if (!searchParams.get("types")) return;
    const next = new URLSearchParams(searchParams);
    next.delete("types");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    setEntryOpen(!mapId);
  }, [mapId]);

  const patchParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParamsRef.current);
      mutate(next);
      setSearchParams(next, { replace: true });
    },
    [setSearchParams],
  );

  const setMap = (id: string) => {
    patchParams((params) => {
      if (id) params.set("map", id);
      else params.delete("map");
      params.delete("sel");
      params.delete("q");
      params.delete("trader");
    });
    setKeyword("");
    locateIndexRef.current = {};
  };

  /** 目录不含区轮廓；筛选在前端。 */
  const prepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrep({ map: mapId }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const mapQuery = useQuery({
    queryKey: ["guides-tarkov-map", gameMode, mapId],
    queryFn: () => fetchTarkovMapDetail(mapId),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const selectedKey = selected.join(",");
  const geometryQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-geometry", gameMode, mapId, selectedKey],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        geometry: true,
        ids: selected,
      }),
    enabled: Boolean(mapId) && selected.length > 0,
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const catalog = useMemo(
    () => prepQuery.data?.items ?? [],
    [prepQuery.data],
  );

  useEffect(() => {
    if (!prepQuery.isSuccess || !catalog.length) return;
    const valid = new Set(catalog.map((row) => row.id));
    const next = selected.filter((id) => valid.has(id));
    if (next.join(",") === selected.join(",")) return;
    patchParams((params) => {
      const serialized = serializeSelectedIds(next);
      if (serialized) params.set("sel", serialized);
      else params.delete("sel");
    });
  }, [patchParams, prepQuery.isSuccess, catalog, selected]);

  const rows = useMemo(
    () =>
      filterRaidPrepRows(catalog, { trader, q }),
    [catalog, trader, q],
  );

  const selectedTasks = useMemo(
    () => selectedTasksFromCatalog(catalog, selected),
    [catalog, selected],
  );
  const overlayTasks = useMemo(
    () => selectedTasksFromCatalog(geometryQuery.data?.items ?? [], selected),
    [geometryQuery.data, selected],
  );
  const { picked, rest } = useMemo(
    () => partitionRaidPrepRows(rows, selectedTasks),
    [rows, selectedTasks],
  );
  const participantsByTask = useMemo(() => {
    const name = (me?.display_name || me?.username || "").trim() || "?";
    const map = new Map<string, Array<{ name: string; userId?: number }>>();
    for (const task of selectedTasks) {
      map.set(task.id, [{ name, userId: me?.id }]);
    }
    return map;
  }, [selectedTasks, me?.id, me?.display_name, me?.username]);
  const overlays = useMemo(
    () => buildRaidPrepOverlays(overlayTasks, mapId, objDone),
    [overlayTasks, mapId, objDone],
  );
  const colorByTask = useMemo(() => {
    const map = new Map<string, string>();
    selected.forEach((id, index) => {
      map.set(id, colorForTaskIndex(index));
    });
    return map;
  }, [selected]);
  const mapLabel =
    raidPrepMapOptions().find((item) => item.id === mapId)?.label || mapId;

  const toggleSelected = (id: string) => {
    patchParams((params) => {
      const current = parseCsvParam(params.get("sel"));
      const next = current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id].slice(0, RAID_PREP_MAX_SELECTED);
      const serialized = serializeSelectedIds(next);
      if (serialized) params.set("sel", serialized);
      else params.delete("sel");
    });
  };

  const syncFromTaskProgress = () => {
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: catalog.map((row) => row.id),
      selectedIds: selected,
      startedIds: loadTaskStartedIds(gameMode),
      doneIds: loadTaskDoneIds(gameMode),
    });
    if (plan.addedIds.length) {
      patchParams((params) => {
        const serialized = serializeSelectedIds(plan.nextIds);
        if (serialized) params.set("sel", serialized);
        else params.delete("sel");
      });
      setDockOpen(true);
      message.success(plan.hint);
      return;
    }
    message.info(plan.hint);
  };

  const locateTask = useCallback(
    async (row: (typeof rows)[number]) => {
      let points = resolveRaidPrepLocatePoints(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(objDone, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const extra = await fetchTarkovRaidPrep({
            map: mapId,
            geometry: true,
            ids: [row.id],
          });
          const rich = extra.items.find((item) => item.id === row.id);
          points = rich
            ? resolveRaidPrepLocatePoints(
                rich,
                mapId,
                raidPrepSkippedIds(objDone, row.id),
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
    [mapId, overlayTasks, objDone],
  );

  const taskLocateHandler = useCallback(
    (row: (typeof rows)[number]) =>
      row.has_map_markers ? () => locateTask(row) : undefined,
    [locateTask],
  );

  const openGuide = useCallback((taskId: string) => {
    setGuideTaskId(taskId);
    setGuideOpen(true);
  }, []);

  const traders = prepQuery.data?.traders ?? [];

  if (!mapId) {
    return (
      <div className={styles.stagePick}>
        <h1 className={styles.srOnly}>战局准备</h1>
        <TarkovRaidPrepEntryModal
          open={entryOpen}
          onClose={() => {
            setEntryOpen(false);
            navigate(raidPrepEntryFallbackPath());
          }}
        />
      </div>
    );
  }

  return (
    <div className={styles.stage} data-dock={dockOpen ? "open" : "closed"}>
      <div className={styles.topBar}>
        <h1 className={styles.srOnly}>战局准备</h1>
        <div className={styles.roomId}>
          <p className={styles.roomTitle}>战局准备 · {mapLabel}</p>
        </div>
        <div className={styles.topActions}>
          <button
            type="button"
            className={styles.dockToggle}
            onClick={() => setDockOpen((open) => !open)}
          >
            {dockOpen ? "收起任务" : "任务列表"}
          </button>
          <Link className={styles.wiki} to={tarkovMapHref(mapId)}>
            地图页
          </Link>
        </div>
      </div>

      {prepQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="任务点位加载失败"
          description={apiError(prepQuery.error, "任务点位加载失败")}
        />
      ) : null}

      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          <div className={styles.mapFill}>
            {mapQuery.isLoading ? (
              <div className={catalogCss.status}>
                <Spin tip="加载地图…" />
              </div>
            ) : mapQuery.isError ? (
              <Alert
                type="error"
                showIcon
                message="地图加载失败"
                description={apiError(mapQuery.error, "地图加载失败")}
              />
            ) : (
              <Suspense fallback={<PanelFallback tip="加载地图…" />}>
                <TarkovMapViewer
                  slug={mapId}
                  parentSlug={mapQuery.data?.parent_slug || undefined}
                  extracts={mapQuery.data?.extracts}
                  bosses={mapQuery.data?.bosses}
                  spawns={mapQuery.data?.spawns}
                  questOverlays={overlays}
                  focusRequest={focusRequest}
                  highlightTaskId={highlightTaskId}
                  fill
                  onQuestLabelClick={(taskId) => {
                    setHighlightTaskId(taskId);
                    openGuide(taskId);
                  }}
                  questParticipantsByTask={participantsByTask}
                  topRight={
                    <div className={styles.summaryStack}>
                      <TarkovRaidPrepSummary
                        tasks={selectedTasks}
                        mapId={mapId}
                        participantsByTask={participantsByTask}
                        keyOwns={keyOwns}
                        skippedByTask={objDone}
                        objectiveDones={
                          me
                            ? skipMapToObjectiveDones(objDone, {
                                userId: me.id,
                                name:
                                  (me.display_name || me.username || "").trim() ||
                                  `用户${me.id}`,
                              })
                            : undefined
                        }
                        currentUser={
                          me
                            ? {
                                userId: me.id,
                                name:
                                  (me.display_name || me.username || "").trim() ||
                                  `用户${me.id}`,
                              }
                            : null
                        }
                        onToggleObjective={toggleObjDone}
                        onTitle={openGuide}
                      />
                      <TarkovRaidPrepGuideOverview
                        open={guideOpen}
                        onOpenChange={setGuideOpen}
                        tasks={selectedTasks}
                        mapId={mapId}
                        activeId={guideTaskId}
                        onActiveIdChange={setGuideTaskId}
                        participantsByTask={participantsByTask}
                        skippedByTask={objDone}
                        objectiveDones={
                          me
                            ? skipMapToObjectiveDones(objDone, {
                                userId: me.id,
                                name:
                                  (me.display_name || me.username || "").trim() ||
                                  `用户${me.id}`,
                              })
                            : undefined
                        }
                        currentUserId={me?.id}
                        onToggleObjective={toggleObjDone}
                      />
                    </div>
                  }
                />
              </Suspense>
            )}
          </div>
        </div>

        <aside className={styles.dock} aria-label="任务列表">
          <TarkovRaidPrepFilters
            keyword={keyword}
            onKeyword={setKeyword}
            traders={traders}
            trader={trader}
            onTrader={(slug) =>
              patchParams((params) => {
                if (slug) params.set("trader", slug);
                else params.delete("trader");
              })
            }
            leading={
              <div className={styles.dockLeadActions}>
                <button
                  type="button"
                  className={styles.changeMapBtn}
                  onClick={() => setChangeMapOpen(true)}
                >
                  更换地图
                </button>
                <button
                  type="button"
                  className={styles.changeMapBtn}
                  onClick={() => setOcrOpen(true)}
                >
                  截图识别
                </button>
                <button
                  type="button"
                  className={styles.changeMapBtn}
                  disabled={!catalog.length}
                  title="按个人中心进行中的任务，勾选本图相关项"
                  onClick={syncFromTaskProgress}
                >
                  从任务进度同步
                </button>
              </div>
            }
          />
          <div
            className={styles.taskList}
            onClick={() => setHighlightTaskId("")}
          >
            {prepQuery.isLoading && !prepQuery.data && !picked.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : (
              <>
                {selected.length > 0 &&
                prepQuery.isLoading &&
                !picked.length ? (
                  <div className={styles.pickedBlock}>
                    <p className={styles.pickedLabel}>我的已选 {selected.length}</p>
                    <div className={styles.empty}>
                      <Spin />
                    </div>
                  </div>
                ) : picked.length ? (
                  <div className={styles.pickedBlock}>
                    <p className={styles.pickedLabel}>我的已选 {picked.length}</p>
                    {picked.map((row, index) => (
                      <TarkovRaidPrepTaskCard
                        key={row.id}
                        row={row}
                        mapSlug={mapId}
                        compact
                        checked
                        highlighted
                        active={highlightTaskId === row.id}
                        color={colorByTask.get(row.id) || colorForTaskIndex(index)}
                        skipped={raidPrepSkippedIds(objDone, row.id)}
                        onToggleObjective={(objectiveId) =>
                          toggleObjDone(row.id, objectiveId)
                        }
                        onToggle={() => toggleSelected(row.id)}
                        onLocate={taskLocateHandler(row)}
                        onTitle={() => openGuide(row.id)}
                      />
                    ))}
                  </div>
                ) : null}
                {rest.length ? (
                  <>
                    {picked.length ? (
                      <p className={styles.restLabel}>筛选结果</p>
                    ) : null}
                    {rest.map((row) => (
                      <TarkovRaidPrepTaskCard
                        key={row.id}
                        row={row}
                        mapSlug={mapId}
                        checked={false}
                        highlighted={false}
                        active={highlightTaskId === row.id}
                        skipped={raidPrepSkippedIds(objDone, row.id)}
                        onToggleObjective={(objectiveId) =>
                          toggleObjDone(row.id, objectiveId)
                        }
                        onToggle={() => toggleSelected(row.id)}
                        onLocate={taskLocateHandler(row)}
                        onTitle={() => openGuide(row.id)}
                      />
                    ))}
                  </>
                ) : prepQuery.isLoading && !prepQuery.data ? (
                  <div className={styles.empty}>
                    <Spin />
                  </div>
                ) : (
                  <div className={styles.empty}>
                    {picked.length || selected.length
                      ? "当前筛选下无其他任务"
                      : "当前筛选下无任务"}
                  </div>
                )}
              </>
            )}
          </div>
        </aside>
      </div>

      <TarkovRaidPrepEntryModal
        open={changeMapOpen}
        step="solo"
        currentMapId={mapId}
        onClose={() => setChangeMapOpen(false)}
        onSoloMap={setMap}
      />
      <TarkovRaidPrepOcrModal
        open={ocrOpen}
        onClose={() => setOcrOpen(false)}
        catalog={catalog}
        selectedIds={selected}
        onConfirm={(ids) => {
          patchParams((params) => {
            const next = mergeRaidPrepOcrSelection(selected, ids);
            const serialized = serializeSelectedIds(next);
            if (serialized) params.set("sel", serialized);
            else params.delete("sel");
          });
        }}
      />
    </div>
  );
}
