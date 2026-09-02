import { Alert, Spin, message } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addTarkovKeyOwn,
  fetchTarkovKeyOwns,
  fetchTarkovMapDetail,
  fetchTarkovRaidLogs,
  fetchTarkovRaidPrep,
  fetchTarkovRaidPrepState,
  fetchTarkovTaskDones,
  writeTarkovTaskDones,
  putTarkovRaidPrepState,
  removeTarkovKeyOwn,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovMapHref, TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  filterRaidPrepOverlaysForViewer,
  filterRaidPrepRows,
  groupRaidPrepRowsByProgress,
  hydrateRaidPrepCatalogRows,
  normalizeRaidPrepMapId,
  raidPrepAutoSwitchMapId,
  objectiveDonesToSkipMap,
  parseCsvParam,
  pinSelectedRaidPrepRows,
  planRaidPrepTaskProgressSync,
  raidPrepMapOptions,
  raidPrepObjectiveDoneScope,
  raidPrepObjectiveDoneLegacyScopes,
  mergeRaidPrepSkipMaps,
  raidPrepSkipMapsEqual,
  readRaidPrepObjectiveDoneWithLegacy,
  raidPrepSkippedIds,
  resolveRaidPrepLocateTargets,
  selectedTasksFromCatalog,
  serializeSelectedIds,
  raidPrepTaskProgressStatus,
  settleRaidPrepSelection,
  skipMapToObjectiveDones,
  useRaidPrepObjectiveDone,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";
import { mergeRaidPrepOcrSelection } from "@/lib/tarkovRaidPrepOcr";
import { applyTarkovKeyOwnsCache } from "@/lib/tarkovKeyPacks";
import { keyOwnsForUser, playerFixMatchesRoomMap } from "@/lib/tarkovRaidRooms";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { logMapLabel } from "@/lib/tarkovGameLogs";
import {
  useTarkovLastLogMapId,
  useTarkovLastLogPhase,
} from "@/lib/useTarkovLiveWatch";
import { useTarkovRaidDockOpen } from "@/lib/tarkovRaidDockPrefs";
import { useRaidPrepGeometry } from "@/lib/useRaidPrepGeometry";
import {
  commitTaskStatus,
  loadTaskDoneIds,
  loadTaskStartedIds,
  resolveAccountTaskProgress,
  taskProgressQueryData,
} from "@/lib/tarkovTaskTree";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovRaidPrepFilters } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import { TarkovRaidPrepTaskGroups } from "@/components/guides/tarkov/TarkovRaidPrepTaskGroups";
import { TarkovRaidPrepEntryModal } from "@/components/guides/tarkov/TarkovRaidPrepEntryModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import {
  TarkovGoonRoomNotice,
  TarkovGoonSightingHint,
} from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
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
  const queryClient = useQueryClient();
  const me = useAuthStore((s) => s.user);
  const [searchParams, setSearchParams] = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const mapId = normalizeRaidPrepMapId(searchParams.get("map") || "");
  const q = (searchParams.get("q") || "").trim();
  const selected = parseCsvParam(searchParams.get("sel"));
  const [keyword, setKeyword] = useState(q);
  const [entryOpen, setEntryOpen] = useState(!mapId);
  const [changeMapOpen, setChangeMapOpen] = useState(false);
  const [ocrOpen, setOcrOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useTarkovRaidDockOpen();
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const objDoneScope = raidPrepObjectiveDoneScope(mapId, gameMode, me?.id);
  const objDoneLegacy = useMemo(
    () => raidPrepObjectiveDoneLegacyScopes(mapId),
    [mapId],
  );
  const [objDone, toggleObjDone, replaceObjDone] = useRaidPrepObjectiveDone(
    objDoneScope,
    objDoneLegacy,
  );
  const [keyBringIds, setKeyBringIds] = useState<string[]>([]);
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const autoMapSigRef = useRef("");
  const [progressTick, setProgressTick] = useState(0);
  const hydratedKeyRef = useRef("");
  const persistReadyRef = useRef(false);
  const [persistTick, setPersistTick] = useState(0);
  const ownsQuery = useQuery({
    queryKey: ["guides-tarkov-key-owns"],
    queryFn: fetchTarkovKeyOwns,
    staleTime: 60_000,
  });
  const taskDonesQuery = useQuery({
    queryKey: ["guides-tarkov-task-dones", gameMode],
    queryFn: fetchTarkovTaskDones,
    staleTime: 30_000,
  });
  const stateQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-state", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrepState(mapId),
    enabled: Boolean(mapId && me),
    staleTime: 30_000,
  });
  const logsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-logs", mapId],
    queryFn: () => fetchTarkovRaidLogs({ mapId, limit: 8 }),
    enabled: Boolean(mapId && me),
    staleTime: 30_000,
  });
  const doneTaskIds = useMemo(() => {
    void progressTick;
    return resolveAccountTaskProgress(taskDonesQuery.data, gameMode).done;
  }, [gameMode, progressTick, taskDonesQuery.data]);
  const startedTaskIds = useMemo(() => {
    void progressTick;
    return resolveAccountTaskProgress(taskDonesQuery.data, gameMode).started;
  }, [gameMode, progressTick, taskDonesQuery.data]);
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

  const setMap = useCallback((id: string) => {
    patchParams((params) => {
      if (id) params.set("map", id);
      else params.delete("map");
      params.delete("sel");
      params.delete("q");
      params.delete("trader");
    });
    setKeyword("");
    locateIndexRef.current = {};
  }, [patchParams]);

  const autoMapId = raidPrepAutoSwitchMapId({
    currentMapId: mapId,
    logMapId: lastLogPhase?.mapId || lastLogMapId,
    phaseKind: lastLogPhase?.kind,
    fillEmpty: false,
  });
  useEffect(() => {
    if (!autoMapId) return;
    const sig = `${autoMapId}:${lastLogPhase?.raidId || ""}:${lastLogPhase?.kind || "idle"}`;
    if (autoMapSigRef.current === sig) return;
    autoMapSigRef.current = sig;
    setMap(autoMapId);
    message.info(`已按游戏日志切换到${logMapLabel(autoMapId)}`);
  }, [autoMapId, lastLogPhase?.kind, lastLogPhase?.raidId, setMap]);

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

  const geometry = useRaidPrepGeometry(mapId, selected);

  const catalog = useMemo(
    () => prepQuery.data?.items ?? [],
    [prepQuery.data],
  );
  const catalogRich = useMemo(
    () => hydrateRaidPrepCatalogRows(catalog, geometry.byId),
    [catalog, geometry.byId],
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

  const applySelected = useCallback(
    (next: string[]) => {
      const serialized = serializeSelectedIds(next);
      patchParams((params) => {
        if (serialized) params.set("sel", serialized);
        else params.delete("sel");
      });
    },
    [patchParams],
  );

  useEffect(() => {
    if (!mapId) {
      hydratedKeyRef.current = "";
      persistReadyRef.current = false;
      setKeyBringIds([]);
    }
  }, [mapId]);

  useEffect(() => {
    if (!mapId || !prepQuery.isSuccess) return;
    if (me && stateQuery.isLoading) return;
    const key = `${gameMode}:${mapId}:${stateQuery.dataUpdatedAt}:${taskDonesQuery.dataUpdatedAt}`;
    if (hydratedKeyRef.current === key) return;
    hydratedKeyRef.current = key;
    const urlSel = parseCsvParam(searchParamsRef.current.get("sel"));
    const fromState = stateQuery.data?.selected ?? [];
    let next = urlSel.length ? urlSel : fromState;
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: catalog.map((row) => row.id),
      selectedIds: next,
      startedIds: loadTaskStartedIds(gameMode),
      doneIds: doneTaskIds,
    });
    next = settleRaidPrepSelection({
      selectedIds: plan.nextIds,
      completedIds: doneTaskIds,
    }).nextIds;
    if (next.join(",") !== selected.join(",")) applySelected(next);
    if (stateQuery.data) {
      setKeyBringIds(stateQuery.data.key_brings || []);
      if (me) {
        const fromServer = objectiveDonesToSkipMap(
          (stateQuery.data.objective_dones || []).map((row) => ({
            task_id: row.task_id,
            objective_id: row.objective_id,
            user_id: me.id,
          })),
          me.id,
        );
        const local = readRaidPrepObjectiveDoneWithLegacy(
          objDoneScope,
          objDoneLegacy,
        );
        const merged = mergeRaidPrepSkipMaps(local, fromServer);
        if (!raidPrepSkipMapsEqual(local, merged)) replaceObjDone(merged);
      }
    }
    persistReadyRef.current = true;
    setPersistTick((n) => n + 1);
  }, [
    applySelected,
    catalog,
    doneTaskIds,
    gameMode,
    mapId,
    me,
    objDoneLegacy,
    objDoneScope,
    prepQuery.isSuccess,
    replaceObjDone,
    selected,
    stateQuery.data,
    stateQuery.dataUpdatedAt,
    stateQuery.isLoading,
    taskDonesQuery.dataUpdatedAt,
  ]);

  useEffect(() => {
    if (!mapId || !me || !persistReadyRef.current) return;
    const handle = window.setTimeout(() => {
      void putTarkovRaidPrepState(mapId, {
        selected,
        objective_dones: skipMapToObjectiveDones(objDone, {
          userId: me.id,
          name: myName,
        }).map((row) => ({
          task_id: row.task_id,
          objective_id: row.objective_id,
        })),
        key_brings: keyBringIds,
      }).catch(() => {
        /* 未登录或网络失败时本机勾选仍可用 */
      });
    }, 700);
    return () => window.clearTimeout(handle);
  }, [keyBringIds, mapId, me, myName, objDone, persistTick, selected]);

  useEffect(() => {
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode) return;
      const plan = planRaidPrepTaskProgressSync({
        catalogIds: catalog.map((row) => row.id),
        selectedIds: selected,
        startedIds: detail.started,
        doneIds: detail.done,
      });
      const settled = settleRaidPrepSelection({
        selectedIds: plan.nextIds,
        completedIds: detail.completedIds?.length ? detail.completedIds : detail.done,
      });
      if (settled.nextIds.join(",") !== selected.join(",")) {
        applySelected(settled.nextIds);
      }
      setProgressTick((n) => n + 1);
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () =>
      window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [applySelected, catalog, gameMode, selected]);

  useEffect(() => {
    const latest = logsQuery.data?.items?.[0];
    if (!latest || latest.aborted || !latest.ended_at) return;
    const settled = settleRaidPrepSelection({
      selectedIds: selected,
      completedIds: doneTaskIds,
      aborted: latest.aborted,
    });
    if (settled.removedIds.length) applySelected(settled.nextIds);
  }, [applySelected, doneTaskIds, logsQuery.data, selected]);

  const rows = useMemo(
    () => filterRaidPrepRows(catalogRich, { q }),
    [catalogRich, q],
  );

  const selectedTasks = useMemo(
    () => selectedTasksFromCatalog(catalogRich, selected),
    [catalogRich, selected],
  );
  const overlayTasks = geometry.items;
  const objectiveDones = useMemo(
    () =>
      me
        ? skipMapToObjectiveDones(objDone, {
            userId: me.id,
            name: myName,
          })
        : undefined,
    [me, myName, objDone],
  );
  const selectedIdSet = useMemo(() => new Set(selected), [selected]);
  const statusGroups = useMemo(() => {
    const grouped = groupRaidPrepRowsByProgress(
      rows,
      doneTaskIds,
      startedTaskIds,
    );
    return {
      active: pinSelectedRaidPrepRows(grouped.active, selectedIdSet),
      todo: pinSelectedRaidPrepRows(grouped.todo, selectedIdSet),
      done: pinSelectedRaidPrepRows(grouped.done, selectedIdSet),
    };
  }, [doneTaskIds, rows, selectedIdSet, startedTaskIds]);
  const taskStatusOf = (taskId: string) =>
    raidPrepTaskProgressStatus(taskId, doneTaskIds, startedTaskIds);
  const changeTaskStatus = useCallback(
    (taskId: string, status: RaidPrepTaskProgressStatus) => {
      if (raidPrepTaskProgressStatus(taskId, doneTaskIds, startedTaskIds) === status) {
        return;
      }
      const next = commitTaskStatus(gameMode, taskId, status);
      queryClient.setQueryData(
        ["guides-tarkov-task-dones", gameMode],
        taskProgressQueryData(next.done, next.started),
      );
      void writeTarkovTaskDones(next.done, {
        startedIds: next.started,
      }).catch(() => {});
    },
    [doneTaskIds, gameMode, queryClient, startedTaskIds],
  );
  const participantsByTask = useMemo(() => {
    const name = (me?.display_name || me?.username || "").trim() || "?";
    const map = new Map<string, Array<{ name: string; userId?: number }>>();
    for (const task of selectedTasks) {
      map.set(task.id, [{ name, userId: me?.id }]);
    }
    return map;
  }, [selectedTasks, me?.id, me?.display_name, me?.username]);
  const keyBrings = useMemo(
    () =>
      me
        ? keyBringIds.map((itemId) => ({
            item_id: itemId,
            user_id: me.id,
            display_name: myName,
          }))
        : [],
    [keyBringIds, me, myName],
  );
  const overlays = useMemo(
    () =>
      filterRaidPrepOverlaysForViewer(
        buildRaidPrepOverlays(overlayTasks, mapId),
        objDone,
      ),
    [overlayTasks, mapId, objDone],
  );
  const hideLocalFix = Boolean(
    lastLogMapId && !playerFixMatchesRoomMap(lastLogMapId, mapId),
  );
  const toggleKeyBring = (itemId: string) => {
    setKeyBringIds((current) =>
      current.includes(itemId)
        ? current.filter((id) => id !== itemId)
        : [...current, itemId],
    );
  };
  const toggleKeyOwn = useCallback(
    async (itemId: string) => {
      if (!me) return;
      const current = ownsQuery.data?.item_ids || [];
      const have = current.includes(itemId);
      const next = have
        ? current.filter((id) => id !== itemId)
        : [...current, itemId];
      applyTarkovKeyOwnsCache(queryClient, next);
      try {
        const data = have
          ? await removeTarkovKeyOwn(itemId)
          : await addTarkovKeyOwn(itemId);
        applyTarkovKeyOwnsCache(queryClient, data.item_ids || []);
      } catch (exc) {
        applyTarkovKeyOwnsCache(queryClient, current);
        message.error(apiError(exc, "更新钥匙拥有失败"));
      }
    },
    [me, ownsQuery.data?.item_ids, queryClient],
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

  const toggleSelected = useCallback(
    (id: string) => {
      patchParams((params) => {
        const current = parseCsvParam(params.get("sel"));
        if (
          !current.includes(id) &&
          raidPrepTaskProgressStatus(id, doneTaskIds, startedTaskIds) === "done"
        ) {
          return;
        }
        const next = current.includes(id)
          ? current.filter((item) => item !== id)
          : [...current, id].slice(0, RAID_PREP_MAX_SELECTED);
        const serialized = serializeSelectedIds(next);
        if (serialized) params.set("sel", serialized);
        else params.delete("sel");
      });
    },
    [doneTaskIds, patchParams, startedTaskIds],
  );

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
      let points = resolveRaidPrepLocateTargets(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(objDone, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const rich = await geometry.ensure(row.id);
          points = rich
            ? resolveRaidPrepLocateTargets(
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
    [geometry, mapId, objDone, overlayTasks],
  );

  const openGuide = useCallback((taskId: string) => {
    setGuideTaskId(taskId);
    setGuideOpen(true);
  }, []);

  const onQuestLabelClick = useCallback((taskId: string) => {
    setHighlightTaskId(taskId);
    openGuide(taskId);
  }, [openGuide]);


  if (!mapId) {
    return (
      <div className={styles.stagePick}>
        <h1 className={styles.srOnly}>联机大厅</h1>
        <TarkovRaidPrepEntryModal
          open={entryOpen}
          onClose={() => {
            setEntryOpen(false);
            navigate(TARKOV_HOME_PATH);
          }}
        />
      </div>
    );
  }

  return (
    <div className={styles.stage} data-dock={dockOpen ? "open" : "closed"}>
      <div className={styles.topBar}>
        <h1 className={styles.srOnly}>联机大厅</h1>
        <div className={styles.roomId}>
          <p className={styles.roomTitle}>
            联机大厅 · {mapLabel}
            <TarkovGoonSightingHint mapId={mapId} variant="inline" />
          </p>
        </div>
        <div className={styles.topActions}>
          <button
            type="button"
            className={styles.dockToggle}
            aria-expanded={dockOpen}
            aria-controls="tarkov-raid-dock"
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
          <TarkovGoonRoomNotice mapId={mapId} />
          <button
            type="button"
            className={styles.dockEdge}
            aria-expanded={dockOpen}
            aria-controls="tarkov-raid-dock"
            onClick={() => setDockOpen((open) => !open)}
          >
            <span className={styles.srOnly}>
              {dockOpen ? "收起任务栏" : "展开任务栏"}
            </span>
            <span aria-hidden>{dockOpen ? "›" : "‹"}</span>
          </button>
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
                  locks={mapQuery.data?.locks}
                  hazards={mapQuery.data?.hazards}
                  switches={mapQuery.data?.switches}
                  stationaryWeapons={mapQuery.data?.stationary_weapons}
                  btrStops={mapQuery.data?.btr_stops}
                  lootContainers={mapQuery.data?.loot_containers}
                  places={mapQuery.data?.places}
                  questOverlays={overlays}
                  focusRequest={focusRequest}
                  highlightTaskId={highlightTaskId}
                  authorUserId={me?.id || 0}
                  authorDisplayName={myName}
                  suppressLocalFix={hideLocalFix}
                  fill
                  onQuestLabelClick={onQuestLabelClick}
                  questParticipantsByTask={participantsByTask}
                  topRight={
                    <div className={styles.summaryStack}>
                      <TarkovRaidPrepSummary
                        tasks={selectedTasks}
                        mapId={mapId}
                        participantsByTask={participantsByTask}
                        keyOwns={keyOwns}
                        keyBrings={keyBrings}
                        canToggleKeyBring={Boolean(me)}
                        onToggleKeyBring={me ? toggleKeyBring : undefined}
                        canToggleKeyOwn={Boolean(me)}
                        onToggleKeyOwn={me ? toggleKeyOwn : undefined}
                        skippedByTask={objDone}
                        doneTaskIds={doneTaskIds}
                        objectiveDones={objectiveDones}
                        currentUserId={me?.id}
                        currentUser={
                          me
                            ? {
                                userId: me.id,
                                name: myName,
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
                        doneTaskIds={doneTaskIds}
                        onToggleObjective={toggleObjDone}
                      />
                    </div>
                  }
                />
              </Suspense>
            )}
          </div>
        </div>

        <aside
          id="tarkov-raid-dock"
          className={styles.dock}
          aria-label="任务列表"
        >
          <TarkovRaidPrepFilters
            keyword={keyword}
            onKeyword={setKeyword}
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
            {prepQuery.isLoading && !prepQuery.data && !rows.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : (
              <TarkovRaidPrepTaskGroups
                groups={statusGroups}
                empty={<div className={styles.empty}>当前搜索下无任务</div>}
                renderRow={(row) => (
                  <TarkovRaidPrepTaskCard
                    key={row.id}
                    row={row}
                    mapSlug={mapId}
                    compact
                    checked={selectedIdSet.has(row.id)}
                    highlighted={selectedIdSet.has(row.id)}
                    status={taskStatusOf(row.id)}
                    done={taskStatusOf(row.id) === "done"}
                    active={highlightTaskId === row.id}
                    color={
                      selectedIdSet.has(row.id)
                        ? colorByTask.get(row.id) || colorForTaskIndex(0)
                        : undefined
                    }
                    skipped={raidPrepSkippedIds(objDone, row.id)}
                    onToggleObjective={toggleObjDone}
                    onToggle={toggleSelected}
                    onNeedDetail={geometry.ensure}
                    onLocate={locateTask}
                    onTitle={openGuide}
                    onSetStatus={changeTaskStatus}
                  />
                )}
              />
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
