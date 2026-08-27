import { Alert, Spin } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovMapDetail,
  fetchTarkovRaidPrep,
  type TarkovRaidPrepTask,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_TRADERS,
  tarkovMapHref,
  tarkovTaskHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapThumbUrl } from "@/lib/tarkovMapThumbs";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import {
  RAID_PREP_MAX_SELECTED,
  RAID_PREP_TYPE_FILTERS,
  buildRaidPrepOverlays,
  colorForTaskId,
  neededKeyNamesForMap,
  normalizeRaidPrepMapId,
  objectiveZoneNames,
  parseCsvParam,
  raidPrepMapOptions,
  serializeSelectedIds,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_PROGRESS_FILTERS,
  tarkovTaskProgressLabel,
  useTarkovTaskMineMode,
} from "@/lib/tarkovTaskProgress";
import {
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovTaskProgressSwitch } from "@/components/guides/tarkov/TarkovTaskProgressSwitch";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { TarkovRaidPrepLobby } from "@/components/guides/tarkov/TarkovRaidPrepLobby";
import catalog from "./TarkovItemCatalogPanel.module.css";
import mapStyles from "./TarkovMapsPanel.module.css";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

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

function MapThumb({
  slug,
  icon,
  compact,
}: {
  slug: string;
  icon: string;
  compact?: boolean;
}) {
  const [broken, setBroken] = useState(false);
  const src = tarkovMapThumbUrl(slug);
  if (!src || broken) {
    return (
      <svg
        className={compact ? styles.chipFallback : mapStyles.thumbFallback}
        viewBox="0 0 24 24"
        aria-hidden
      >
        <path fill="currentColor" d={icon} />
      </svg>
    );
  }
  return (
    <img
      className={compact ? styles.chipThumb : mapStyles.thumb}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
    />
  );
}

export function TarkovRaidPrepPanel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mapId = normalizeRaidPrepMapId(searchParams.get("map") || "");
  const trader = (searchParams.get("trader") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const kappa = searchParams.get("kappa") === "1";
  const pinsOnly = searchParams.get("pins") === "1";
  const pstatus = (searchParams.get("pstatus") || "").trim();
  const types = parseCsvParam(searchParams.get("types"));
  const selected = parseCsvParam(searchParams.get("sel"));
  const [mine, setMine] = useTarkovTaskMineMode();
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);
  const statusFilter = mine ? pstatus || "all" : "";
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);

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
    });
  };

  const prepQuery = useQuery({
    queryKey: [
      "guides-tarkov-raid-prep",
      mapId,
      trader,
      q,
      kappa,
      types.join(","),
      mine,
      statusFilter,
    ],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        q,
        trader: trader || undefined,
        kappa: kappa || undefined,
        types,
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

  const mapQuery = useQuery({
    queryKey: ["guides-tarkov-map", mapId],
    queryFn: () => fetchTarkovMapDetail(mapId),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  useEffect(() => {
    const items = prepQuery.data?.items;
    if (!items) return;
    const valid = new Set(items.map((row) => row.id));
    const next = selected.filter((id) => valid.has(id));
    if (next.join(",") === selected.join(",")) return;
    patchParams((params) => {
      const serialized = serializeSelectedIds(next);
      if (serialized) params.set("sel", serialized);
      else params.delete("sel");
    });
  }, [patchParams, prepQuery.data, selected]);

  const rows = useMemo(() => {
    const items = prepQuery.data?.items ?? [];
    if (!pinsOnly) return items;
    return items.filter((row) => row.has_map_markers);
  }, [prepQuery.data, pinsOnly]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const selectedTasks = useMemo(
    () => rows.filter((row) => selectedSet.has(row.id)),
    [rows, selectedSet],
  );
  const overlays = useMemo(
    () => buildRaidPrepOverlays(selectedTasks, mapId),
    [selectedTasks, mapId],
  );
  const typeOptions = useMemo(() => {
    const seen = new Set<string>(RAID_PREP_TYPE_FILTERS);
    for (const type of types) seen.add(type);
    for (const row of prepQuery.data?.items || []) {
      for (const type of row.objective_types || []) {
        if (type) seen.add(type);
      }
    }
    return orderObjectiveTypes([...seen]);
  }, [prepQuery.data, types]);

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

  const selectMarked = () => {
    const ids = rows
      .filter((row) => row.has_map_markers)
      .map((row) => row.id)
      .slice(0, RAID_PREP_MAX_SELECTED);
    patchParams((params) => {
      const serialized = serializeSelectedIds(ids);
      if (serialized) params.set("sel", serialized);
      else params.delete("sel");
    });
  };

  const clearSelected = () => {
    patchParams((params) => params.delete("sel"));
  };

  const toggleType = (type: string) => {
    patchParams((params) => {
      const current = parseCsvParam(params.get("types"));
      const next = current.includes(type)
        ? current.filter((item) => item !== type)
        : [...current, type];
      if (next.length) params.set("types", next.join(","));
      else params.delete("types");
    });
  };

  const currentMap = mapOptions.find((item) => item.id === mapId);
  const traders = prepQuery.data?.traders ?? [];
  const allOn = !trader;

  if (!mapId) {
    return (
      <div className={styles.stack}>
        <TarkovRaidPrepLobby mapId="" />
        <p className={styles.hint}>
          先选这把要打的地图。选中后会列出相关任务；勾选任务即可把目标区域和刷新点叠到图上。
        </p>
        <div className={mapStyles.grid}>
          {mapOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`${mapStyles.card} ${styles.pickCard}`}
              onClick={() => setMap(option.id)}
            >
              <div className={mapStyles.thumbWrap}>
                <MapThumb slug={option.id} icon={option.icon} />
              </div>
              <div className={mapStyles.body}>
                <div className={mapStyles.name}>{option.label}</div>
                <div className={mapStyles.english}>{option.english}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.stack}>
      <TarkovRaidPrepLobby mapId={mapId} />
      <div className={styles.mapBar} role="radiogroup" aria-label="选择地图">
        {mapOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={option.id === mapId}
            className={`${styles.mapChip} ${
              option.id === mapId ? styles.mapChipOn : ""
            }`}
            onClick={() => setMap(option.id)}
          >
            <MapThumb slug={option.id} icon={option.icon} compact />
            {option.label}
          </button>
        ))}
      </div>

      <div className={taskStyles.toolbar}>
        <div className={taskStyles.toolbarTop}>
          <div className={styles.sideHead}>
            <span className={styles.count}>
              {currentMap?.label || mapId}
              {typeof prepQuery.data?.task_count === "number"
                ? ` · ${prepQuery.data.task_count} 条任务`
                : ""}
              {selected.length ? ` · 已选 ${selected.length}` : ""}
            </span>
            <Link className={styles.wiki} to={tarkovMapHref(mapId)}>
              地图页
            </Link>
          </div>
          <TarkovTaskProgressSwitch
            enabled={mine}
            onChange={(value) => {
              setMine(value);
              const next = new URLSearchParams(searchParams);
              setSearchParams(next, { replace: true });
            }}
          />
        </div>

        <div className={taskStyles.queryRow}>
          <input
            className={taskStyles.search}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="按任务名称筛选"
            aria-label="搜索任务"
          />
          <button
            type="button"
            aria-pressed={kappa}
            className={`${taskStyles.chip} ${kappa ? taskStyles.chipOn : ""}`}
            onClick={() =>
              patchParams((params) => {
                if (!kappa) params.set("kappa", "1");
                else params.delete("kappa");
              })
            }
          >
            Kappa
          </button>
          <button
            type="button"
            aria-pressed={pinsOnly}
            className={`${taskStyles.chip} ${pinsOnly ? taskStyles.chipOn : ""}`}
            onClick={() =>
              patchParams((params) => {
                if (!pinsOnly) params.set("pins", "1");
                else params.delete("pins");
              })
            }
          >
            仅有点位
          </button>
        </div>

        <div className={taskStyles.filterRow}>
          <span className={taskStyles.filterLabel}>商人</span>
          <div
            className={taskStyles.traderBar}
            role="radiogroup"
            aria-label="按商人筛选"
          >
            <button
              type="button"
              role="radio"
              aria-checked={allOn}
              className={`${taskStyles.traderBtn} ${taskStyles.traderBtnAll} ${
                allOn ? taskStyles.traderBtnOn : ""
              }`}
              onClick={() =>
                patchParams((params) => params.delete("trader"))
              }
            >
              全部
            </button>
            {traders.map((item) => {
              const { english, chinese } = traderFilterLabel(
                item.slug,
                item.name,
              );
              const on = trader === item.slug;
              return (
                <button
                  key={item.slug || item.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  aria-label={chinese ? `${english}（${chinese}）` : english}
                  title={chinese ? `${english}（${chinese}）` : english}
                  className={`${taskStyles.traderBtn} ${
                    on ? taskStyles.traderBtnOn : ""
                  }`}
                  onClick={() =>
                    patchParams((params) => params.set("trader", item.slug))
                  }
                >
                  <TarkovTraderThumb slug={item.slug} size={40} />
                </button>
              );
            })}
          </div>
        </div>

        <div className={taskStyles.filterRow}>
          <span className={taskStyles.filterLabel}>目标</span>
          <div className={taskStyles.chipBar}>
            {typeOptions.map((type) => (
              <button
                key={type}
                type="button"
                aria-pressed={types.includes(type)}
                className={`${taskStyles.chip} ${
                  types.includes(type) ? taskStyles.chipOn : ""
                }`}
                title={type}
                onClick={() => toggleType(type)}
              >
                {tarkovObjectiveTypeLabel(type)}
              </button>
            ))}
          </div>
        </div>

        {mine ? (
          <div className={taskStyles.filterRow}>
            <span className={taskStyles.filterLabel}>进度</span>
            <div
              className={taskStyles.chipBar}
              role="radiogroup"
              aria-label="按进度筛选"
            >
              <button
                type="button"
                role="radio"
                aria-checked={!pstatus || pstatus === "all"}
                className={`${taskStyles.chip} ${
                  !pstatus || pstatus === "all" ? taskStyles.chipOn : ""
                }`}
                onClick={() =>
                  patchParams((params) => params.delete("pstatus"))
                }
              >
                全部
              </button>
              {TARKOV_TASK_PROGRESS_FILTERS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={pstatus === item.id}
                  className={`${taskStyles.chip} ${
                    pstatus === item.id ? taskStyles.chipOn : ""
                  }`}
                  onClick={() =>
                    patchParams((params) => params.set("pstatus", item.id))
                  }
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}
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

      <p className={styles.hint}>
        勾选任务后，目标区域轮廓、坐标点和物品可能刷新点会叠在地图上。区域名没有坐标时只出现在右侧列表。这不能替代 Wiki 图文走法。
      </p>

      <div className={styles.workspace}>
        <div className={styles.mapPane}>
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
              />
            </Suspense>
          )}
        </div>

        <aside className={styles.side}>
          <div className={styles.sideHead}>
            <span className={styles.count}>
              {rows.length} / {prepQuery.data?.task_count ?? 0}
            </span>
            <div className={styles.actions}>
              <button
                type="button"
                className={taskStyles.chip}
                onClick={selectMarked}
              >
                全选有点位
              </button>
              <button
                type="button"
                className={taskStyles.chip}
                onClick={clearSelected}
              >
                清空
              </button>
            </div>
          </div>
          <div className={styles.taskList}>
            {prepQuery.isLoading && !prepQuery.data ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : rows.length ? (
              rows.map((row) => (
                <TaskRow
                  key={row.id}
                  row={row}
                  mapId={mapId}
                  selected={selectedSet.has(row.id)}
                  onToggle={() => toggleSelected(row.id)}
                />
              ))
            ) : (
              <div className={styles.empty}>当前筛选下无任务</div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function TaskRow({
  row,
  mapId,
  selected,
  onToggle,
}: {
  row: TarkovRaidPrepTask;
  mapId: string;
  selected: boolean;
  onToggle: () => void;
}) {
  const types = orderObjectiveTypes(row.objective_types);
  const zones = objectiveZoneNames(row);
  const keys = neededKeyNamesForMap(row, mapId);
  const progress = tarkovTaskProgressLabel(row.progress_status);
  return (
    <div
      className={`${styles.taskRow} ${selected ? styles.taskRowOn : ""}`}
      role="button"
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
    >
      <input
        className={styles.check}
        type="checkbox"
        checked={selected}
        readOnly
        tabIndex={-1}
        aria-label={row.name || row.id}
      />
      {selected ? (
        <span
          className={styles.swatch}
          style={{ background: colorForTaskId(row.id) }}
        />
      ) : null}
      {row.trader_slug ? (
        <TarkovTraderThumb
          slug={row.trader_slug}
          size={32}
          title={row.trader_name || row.trader_slug}
        />
      ) : null}
      <div className={styles.taskBody}>
        <div className={styles.taskTitle}>
          <Link
            className={styles.taskName}
            to={tarkovTaskHref(row.id)}
            onClick={(event) => event.stopPropagation()}
          >
            {row.name || row.normalized_name || row.id}
          </Link>
          {row.has_map_markers ? (
            <span className={styles.mark}>有点位</span>
          ) : null}
          {progress ? <span className={styles.meta}>{progress}</span> : null}
          {row.wiki_link ? (
            <a
              className={styles.wiki}
              href={row.wiki_link}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => event.stopPropagation()}
            >
              Wiki
            </a>
          ) : null}
        </div>
        {types.length ? (
          <span className={taskStyles.typeList}>
            {types.map((type) => (
              <span
                key={type}
                className={taskStyles.typeChip}
                data-tone={tarkovObjectiveTypeTone(type)}
                title={type}
              >
                {tarkovObjectiveTypeLabel(type)}
              </span>
            ))}
          </span>
        ) : null}
        {zones.length ? (
          <div className={styles.tags}>
            {zones.map((name) => (
              <span key={name} className={styles.zoneTag}>
                {tarkovMapLabel(name)}
              </span>
            ))}
          </div>
        ) : null}
        {keys.length ? (
          <div className={styles.tags}>
            {keys.map((name) => (
              <span key={name} className={styles.keyTag}>
                {name}
              </span>
            ))}
          </div>
        ) : null}
        <div className={styles.meta}>
          {[
            row.min_player_level ? `Lv.${row.min_player_level}` : "",
            row.kappa_required ? "Kappa" : "",
          ]
            .filter(Boolean)
            .join(" · ")}
        </div>
      </div>
    </div>
  );
}
