import { Alert, Spin } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovMapDetail,
  fetchTarkovRaidPrep,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovMapHref } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  normalizeRaidPrepMapId,
  parseCsvParam,
  partitionRaidPrepRows,
  selectedTasksFromCatalog,
  serializeSelectedIds,
} from "@/lib/tarkovRaidPrep";
import {
  useTarkovTaskMineMode,
} from "@/lib/tarkovTaskProgress";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovTaskProgressSwitch } from "@/components/guides/tarkov/TarkovTaskProgressSwitch";
import { TarkovRaidPrepFilters } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import {
  TarkovRaidPrepEntryModal,
  raidPrepEntryFallbackPath,
} from "@/components/guides/tarkov/TarkovRaidPrepEntryModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { useAuthStore } from "@/stores/authStore";
import catalog from "./TarkovItemCatalogPanel.module.css";
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
  const mapId = normalizeRaidPrepMapId(searchParams.get("map") || "");
  const trader = (searchParams.get("trader") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const pstatus = (searchParams.get("pstatus") || "").trim();
  const selected = parseCsvParam(searchParams.get("sel"));
  const [mine, setMine] = useTarkovTaskMineMode();
  const [keyword, setKeyword] = useState(q);
  const [entryOpen, setEntryOpen] = useState(!mapId);
  const [changeMapOpen, setChangeMapOpen] = useState(false);
  const qRef = useRef(q);
  const statusFilter = mine ? pstatus || "all" : "";

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

  useEffect(() => {
    if (!mine && pstatus) {
      const next = new URLSearchParams(searchParams);
      next.delete("pstatus");
      setSearchParams(next, { replace: true });
    }
  }, [mine, pstatus, searchParams, setSearchParams]);

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
      const next = new URLSearchParams(searchParams);
      mutate(next);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setMap = (id: string) => {
    patchParams((params) => {
      if (id) params.set("map", id);
      else params.delete("map");
      params.delete("sel");
      params.delete("q");
      params.delete("trader");
      params.delete("pstatus");
    });
    setKeyword("");
  };

  const prepQuery = useQuery({
    queryKey: [
      "guides-tarkov-raid-prep",
      gameMode,
      mapId,
      trader,
      q,
      mine,
      statusFilter,
    ],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        q,
        trader: trader || undefined,
        progress: mine,
        progressStatus:
          mine && statusFilter && statusFilter !== "all"
            ? statusFilter
            : undefined,
      }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const overlayPrepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-overlay", gameMode, mapId, mine],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        progress: mine,
      }),
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

  useEffect(() => {
    const items = overlayPrepQuery.data?.items;
    if (!overlayPrepQuery.isSuccess || !items) return;
    const valid = new Set(items.map((row) => row.id));
    const next = selected.filter((id) => valid.has(id));
    if (next.join(",") === selected.join(",")) return;
    patchParams((params) => {
      const serialized = serializeSelectedIds(next);
      if (serialized) params.set("sel", serialized);
      else params.delete("sel");
    });
  }, [patchParams, overlayPrepQuery.data, overlayPrepQuery.isSuccess, selected]);

  const rows = useMemo(
    () => prepQuery.data?.items ?? [],
    [prepQuery.data],
  );

  const selectedTasks = useMemo(() => {
    const catalog = overlayPrepQuery.isSuccess
      ? overlayPrepQuery.data?.items ?? []
      : rows;
    return selectedTasksFromCatalog(catalog, selected);
  }, [overlayPrepQuery.data, overlayPrepQuery.isSuccess, rows, selected]);
  const { picked, rest } = useMemo(
    () => partitionRaidPrepRows(rows, selectedTasks),
    [rows, selectedTasks],
  );
  const participantsByTask = useMemo(() => {
    const name = (me?.display_name || me?.username || "").trim() || "我";
    const map = new Map<string, Array<{ name: string; userId?: number }>>();
    for (const task of selectedTasks) {
      map.set(task.id, [{ name, userId: me?.id }]);
    }
    return map;
  }, [selectedTasks, me?.id, me?.display_name, me?.username]);
  const overlays = useMemo(
    () => buildRaidPrepOverlays(selectedTasks, mapId),
    [selectedTasks, mapId],
  );

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
    <div className={styles.stage}>
      <div className={styles.topBar}>
        <h1 className={styles.srOnly}>战局准备</h1>
        <div className={styles.topActions}>
          <TarkovTaskProgressSwitch
            enabled={mine}
            onChange={(value) => {
              setMine(value);
              const next = new URLSearchParams(searchParams);
              setSearchParams(next, { replace: true });
            }}
          />
          <Link className={styles.wiki} to={tarkovMapHref(mapId)}>
            地图页
          </Link>
        </div>
      </div>

      {mine && prepQuery.data && !prepQuery.data.progress_bound ? (
        <Alert
          type="info"
          showIcon
          message="还没绑定 Tarkov Tracker"
          description="打开顶栏「绑定 Token」后，才能按完成 / 进行中 / 缺少前置筛选。"
        />
      ) : null}

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
              <div className={catalog.status}>
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
                  questOverlays={overlays}
                  fill
                  topRight={
                    <TarkovRaidPrepSummary
                      tasks={selectedTasks}
                      mapId={mapId}
                      participantsByTask={participantsByTask}
                    />
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
            progressStatus={mine ? pstatus || "all" : undefined}
            onProgressStatus={
              mine
                ? (status) =>
                    patchParams((params) => {
                      if (status && status !== "all") params.set("pstatus", status);
                      else params.delete("pstatus");
                    })
                : undefined
            }
            leading={
              <button
                type="button"
                className={styles.changeMapBtn}
                onClick={() => setChangeMapOpen(true)}
              >
                更换地图
              </button>
            }
          />
          <div className={styles.taskList}>
            {prepQuery.isLoading && !prepQuery.data && !picked.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : (
              <>
                {selected.length > 0 &&
                overlayPrepQuery.isLoading &&
                !picked.length ? (
                  <div className={styles.pickedBlock}>
                    <p className={styles.pickedLabel}>已选 {selected.length}</p>
                    <div className={styles.empty}>
                      <Spin />
                    </div>
                  </div>
                ) : picked.length ? (
                  <div className={styles.pickedBlock}>
                    <p className={styles.pickedLabel}>已选 {picked.length}</p>
                    {picked.map((row) => (
                      <TarkovRaidPrepTaskCard
                        key={row.id}
                        row={row}
                        mapId={mapId}
                        checked
                        highlighted
                        onToggle={() => toggleSelected(row.id)}
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
                        mapId={mapId}
                        checked={false}
                        highlighted={false}
                        onToggle={() => toggleSelected(row.id)}
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
    </div>
  );
}
