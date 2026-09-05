import { Alert, Spin, message } from "antd";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovCollection,
  fetchTarkovCollectionLayout,
  saveTarkovCollectionLayout,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  applyTarkovCollectionOwnsCache,
  canPlaceCollectionItem,
  clearCollectionLayout,
  collectedIdsFromLayout,
  collectionLayoutQueryKey,
  collectionDropCell,
  collectionBoardCellSize,
  collectionItemSize,
  collectionOccupiedBounds,
  collectionViewGridSize,
  groupCollectionTrayItems,
  layoutFromApi,
  layoutToApi,
  layoutToCollectionSlots,
  loadCollectionLayout,
  moveCollectionItem,
  pickCollectionLayoutSource,
  reconcileCollectionLayout,
  rotateCollectionDragGrab,
  saveCollectionLayout,
  toggleCollectionItem,
  type CollectionDrop,
  type CollectionLayout,
  type CollectionSlot,
  type TarkovCollectionItem,
} from "@/lib/tarkovCollection";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  collectionItemImageUrl,
  inventoryThumbUrl,
} from "@/lib/tarkovItemImages";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovCollectionPanel.module.css";

const DRAG_THRESHOLD = 5;

type DragState = {
  itemId: string;
  pointerId: number;
  startX: number;
  startY: number;
  x: number;
  y: number;
  grabX: number;
  grabY: number;
  stride: number;
  moved: boolean;
  rotated: boolean;
  anchorCol: number;
  anchorRow: number;
  hover: CollectionDrop | null;
  valid: boolean;
};

function boardContentSize(el: HTMLElement): { width: number; height: number } {
  const css = getComputedStyle(el);
  return {
    width:
      el.clientWidth -
      (Number.parseFloat(css.paddingLeft) || 0) -
      (Number.parseFloat(css.paddingRight) || 0),
    height:
      el.clientHeight -
      (Number.parseFloat(css.paddingTop) || 0) -
      (Number.parseFloat(css.paddingBottom) || 0),
  };
}

function readGridMetrics(el: HTMLElement): {
  cell: number;
  gap: number;
  pad: number;
} {
  const css = getComputedStyle(el);
  return {
    cell: Number.parseFloat(css.getPropertyValue("--cell")) || 64,
    gap: Number.parseFloat(css.getPropertyValue("--gap")) || 2,
    pad: Number.parseFloat(css.getPropertyValue("--pad")) || 4,
  };
}

function ghostSize(
  width: number,
  height: number,
  cell: number,
  gap: number,
): { width: number; height: number } {
  return {
    width: width * cell + Math.max(0, width - 1) * gap,
    height: height * cell + Math.max(0, height - 1) * gap,
  };
}

function snappedGhostRect(
  hover: CollectionDrop | null,
  grid: HTMLElement | null,
  width: number,
  height: number,
): { left: number; top: number; width: number; height: number } | null {
  if (!hover || hover.kind !== "grid" || !grid) return null;
  const metrics = readGridMetrics(grid);
  const rect = grid.getBoundingClientRect();
  const stride = metrics.cell + metrics.gap;
  const size = ghostSize(width, height, metrics.cell, metrics.gap);
  return {
    left: rect.left + metrics.pad + hover.col * stride,
    top: rect.top + metrics.pad + hover.row * stride,
    width: size.width,
    height: size.height,
  };
}

function itemLabel(item: TarkovCollectionItem): string {
  return item.name || item.short_name || item.id;
}

function itemShortLabel(item: TarkovCollectionItem): string {
  return (item.short_name || item.name || item.id).trim();
}

function ItemShortName({ item }: { item: TarkovCollectionItem }) {
  const short = itemShortLabel(item);
  const full = itemLabel(item);
  return (
    <Link
      className={styles.itemName}
      to={itemHrefFromTypes(item.id, item.types || [])}
      title={full}
      onClick={onItemNameClick}
    >
      {short}
    </Link>
  );
}

function isToggleClick(event: { ctrlKey: boolean; metaKey: boolean }): boolean {
  return event.ctrlKey || event.metaKey;
}

function onItemNameClick(
  event: { ctrlKey: boolean; metaKey: boolean; preventDefault: () => void; stopPropagation: () => void },
) {
  if (isToggleClick(event)) event.preventDefault();
  event.stopPropagation();
}

function CollectionItemImage({
  item,
  className,
}: {
  item: TarkovCollectionItem;
  className?: string;
}) {
  const hd = collectionItemImageUrl(item.icon_link, item.id);
  const fallback = inventoryThumbUrl(item.icon_link, item.id);
  const src = hd || fallback;
  if (!src) return null;
  return (
    <img
      className={className}
      src={src}
      alt=""
      draggable={false}
      decoding="async"
      onError={(event) => {
        if (fallback && event.currentTarget.src !== fallback) {
          event.currentTarget.src = fallback;
        }
      }}
    />
  );
}

function FirMark() {
  return (
    <span className={styles.fir} title="战局内找到">
      <svg viewBox="0 0 16 16" aria-hidden>
        <circle
          cx="8"
          cy="8"
          r="6.2"
          fill="rgba(0,0,0,.5)"
          stroke="#f2f0e6"
          strokeWidth="1.35"
        />
        <path
          d="M4.55 8.2l2.2 2.25 4.75-5.05"
          fill="none"
          stroke="#f2f0e6"
          strokeWidth="1.55"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

function CadDimension({
  kind,
  cells,
  col0,
  row0,
}: {
  kind: "h" | "v";
  cells: number;
  col0: number;
  row0: number;
}) {
  const style =
    kind === "h"
      ? {
          left: `calc(var(--cad) + var(--pad) + ${col0} * (var(--cell) + var(--gap)))`,
          width: `calc(${cells} * var(--cell) + ${cells - 1} * var(--gap))`,
        }
      : {
          top: `calc(var(--cad) + var(--pad) + ${row0} * (var(--cell) + var(--gap)))`,
          height: `calc(${cells} * var(--cell) + ${cells - 1} * var(--gap))`,
        };
  return (
    <div
      className={kind === "h" ? styles.cadH : styles.cadV}
      style={style}
      aria-label={kind === "h" ? `宽 ${cells} 格` : `高 ${cells} 格`}
    >
      <i className={styles.cadTick} />
      <i className={styles.cadLine} />
      <span className={styles.cadLabel}>{cells}格</span>
      <i className={styles.cadLine} />
      <i className={styles.cadTick} />
    </div>
  );
}

function CollectionItemCard({
  item,
  rotated,
  dragging,
  onPointerDown,
}: {
  item: TarkovCollectionItem;
  rotated?: boolean;
  dragging?: boolean;
  onPointerDown: (
    event: ReactPointerEvent<HTMLDivElement>,
    item: TarkovCollectionItem,
    rotated: boolean,
  ) => void;
}) {
  const count = Number(item.count || 1);
  const size = collectionItemSize(item, rotated);
  return (
    <div
      className={`${styles.item} ${styles.trayItem}${
        dragging ? ` ${styles.itemDragging}` : ""
      }`}
      style={
        {
          "--w": size.width,
          "--h": size.height,
          gridColumn: `span ${size.width}`,
          gridRow: `span ${size.height}`,
        } as CSSProperties
      }
      onPointerDown={(event) => onPointerDown(event, item, Boolean(rotated))}
      onContextMenu={(event) => {
        if (isToggleClick(event)) event.preventDefault();
      }}
    >
      <div className={styles.itemBody}>
        <CollectionItemImage item={item} className={styles.itemIcon} />
        <ItemShortName item={item} />
        {item.found_in_raid ? <FirMark /> : null}
        {count > 1 ? <span className={styles.count}>{count}</span> : null}
      </div>
    </div>
  );
}

export function TarkovCollectionPanel() {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const [layout, setLayout] = useState<CollectionLayout | null>(null);
  const [unplacedRotated, setUnplacedRotated] = useState<Record<string, boolean>>(
    {},
  );
  const [drag, setDrag] = useState<DragState | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const layoutRef = useRef<CollectionLayout | null>(null);
  const itemsRef = useRef<TarkovCollectionItem[]>([]);
  const gridEl = useRef<HTMLElement | null>(null);
  const gridSizeRef = useRef({ cols: 3, rows: 3 });
  const trayEl = useRef<HTMLElement | null>(null);
  const [boardNode, setBoardNode] = useState<HTMLDivElement | null>(null);
  const [cellPx, setCellPx] = useState(36);
  const saveGen = useRef(0);
  const hydratedKey = useRef("");

  useEffect(() => {
    setUnplacedRotated({});
  }, [gameMode]);

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-collection", gameMode],
    queryFn: fetchTarkovCollection,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const items = catalogQuery.data?.items;
  const task = catalogQuery.data?.task;
  itemsRef.current = items || [];

  const layoutQuery = useQuery({
    queryKey: collectionLayoutQueryKey(gameMode),
    queryFn: fetchTarkovCollectionLayout,
    retry: 1,
  });

  const persistLayout = useCallback(
    (next: CollectionLayout) => {
      saveCollectionLayout(gameMode, next);
      applyTarkovCollectionOwnsCache(
        queryClient,
        gameMode,
        collectedIdsFromLayout(next),
      );
      queryClient.setQueryData(collectionLayoutQueryKey(gameMode), {
        ...layoutToApi(next),
        saved: true,
      });
      const gen = (saveGen.current += 1);
      saveTarkovCollectionLayout(layoutToApi(next))
        .then((data) => {
          if (gen !== saveGen.current) return;
          queryClient.setQueryData(collectionLayoutQueryKey(gameMode), data);
        })
        .catch((error) => {
          if (gen !== saveGen.current) return;
          message.error(apiError(error, "收集格子保存失败"));
        });
    },
    [gameMode, queryClient],
  );

  useEffect(() => {
    if (!items) {
      setLayout(null);
      layoutRef.current = null;
      return;
    }
    if (layoutQuery.isLoading) return;
    const key = `${gameMode}:${layoutQuery.dataUpdatedAt}`;
    if (hydratedKey.current === key && layoutRef.current) return;
    const remote = layoutQuery.isSuccess
      ? layoutFromApi(layoutQuery.data)
      : null;
    const local = loadCollectionLayout(gameMode);
    const picked = pickCollectionLayoutSource({
      saved:
        layoutQuery.isSuccess &&
        typeof layoutQuery.data?.saved === "boolean"
          ? layoutQuery.data.saved
          : undefined,
      remote,
      local,
    });
    const next = reconcileCollectionLayout(picked.layout, items);
    layoutRef.current = next;
    setLayout(next);
    saveCollectionLayout(gameMode, next);
    hydratedKey.current = key;
    if (layoutQuery.isSuccess && picked.migrateLocal) persistLayout(next);
  }, [
    gameMode,
    items,
    layoutQuery.data,
    layoutQuery.dataUpdatedAt,
    layoutQuery.isLoading,
    layoutQuery.isSuccess,
    persistLayout,
  ]);

  const commitLayout = useCallback(
    (next: CollectionLayout) => {
      layoutRef.current = next;
      setLayout(next);
      persistLayout(next);
    },
    [persistLayout],
  );

  const toggleItem = useCallback(
    (itemId: string, rotated = false) => {
      const current = layoutRef.current;
      if (!current) return;
      const next = toggleCollectionItem(
        current,
        itemsRef.current,
        itemId,
        rotated,
      );
      if (!next) return;
      commitLayout(next);
      setUnplacedRotated((prev) => {
        if (!(itemId in prev)) return prev;
        const { [itemId]: _dropped, ...rest } = prev;
        return rest;
      });
    },
    [commitLayout],
  );

  const { slots, uncollected } = useMemo(() => {
    if (!layout) {
      return { slots: [] as CollectionSlot[], uncollected: items || [] };
    }
    return layoutToCollectionSlots(layout, items || []);
  }, [layout, items]);

  const trayGroups = useMemo(
    () => groupCollectionTrayItems(uncollected),
    [uncollected],
  );

  const bounds = useMemo(
    () =>
      layout
        ? collectionOccupiedBounds(layout, items || [])
        : { width: 0, height: 0, used: 0, col0: 0, row0: 0 },
    [layout, items],
  );

  const gridSize = collectionViewGridSize();
  gridSizeRef.current = gridSize;

  useEffect(() => {
    if (!boardNode) return;
    const { cols, rows } = collectionViewGridSize();
    const update = () => {
      const { width, height } = boardContentSize(boardNode);
      setCellPx(collectionBoardCellSize(width, height, cols, rows));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(boardNode);
    return () => observer.disconnect();
  }, [boardNode]);

  const hitDrop = useCallback(
    (
      clientX: number,
      clientY: number,
      anchorCol: number,
      anchorRow: number,
    ): CollectionDrop | null => {
      const tray = trayEl.current;
      if (tray) {
        const rect = tray.getBoundingClientRect();
        if (
          clientX >= rect.left &&
          clientX <= rect.right &&
          clientY >= rect.top &&
          clientY <= rect.bottom
        ) {
          return { kind: "tray" };
        }
      }
      const grid = gridEl.current;
      if (!grid) return null;
      const rect = grid.getBoundingClientRect();
      if (
        clientX < rect.left ||
        clientX > rect.right ||
        clientY < rect.top ||
        clientY > rect.bottom
      ) {
        return null;
      }
      const metrics = readGridMetrics(grid);
      const { cols, rows } = gridSizeRef.current;
      const cell = collectionDropCell(
        clientX - rect.left,
        clientY - rect.top,
        metrics.cell,
        metrics.gap,
        metrics.pad,
        anchorCol,
        anchorRow,
        cols,
        rows,
      );
      if (!cell) return null;
      return { kind: "grid", col: cell.col, row: cell.row };
    },
    [],
  );

  const dropValid = useCallback(
    (itemId: string, dest: CollectionDrop | null, rotated: boolean) => {
      const current = layoutRef.current;
      const catalog = itemsRef.current;
      if (!current || !dest) return false;
      if (dest.kind === "tray") return true;
      return canPlaceCollectionItem(
        current,
        catalog,
        itemId,
        dest.col,
        dest.row,
        rotated,
      );
    },
    [],
  );

  const beginDrag = (
    event: ReactPointerEvent<HTMLDivElement>,
    item: TarkovCollectionItem,
    rotated: boolean,
  ) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest("button")) return;
    if (isToggleClick(event)) {
      event.preventDefault();
      toggleItem(item.id, rotated);
      return;
    }
    if (target.closest("a")) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const metrics = readGridMetrics(event.currentTarget);
    const stride = metrics.cell + metrics.gap;
    const size = collectionItemSize(item, rotated);
    const next: DragState = {
      itemId: item.id,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      x: event.clientX,
      y: event.clientY,
      grabX: event.clientX - rect.left,
      grabY: event.clientY - rect.top,
      stride,
      moved: false,
      rotated,
      anchorCol: Math.max(
        0,
        Math.min(size.width - 1, Math.floor((event.clientX - rect.left) / stride)),
      ),
      anchorRow: Math.max(
        0,
        Math.min(size.height - 1, Math.floor((event.clientY - rect.top) / stride)),
      ),
      hover: null,
      valid: false,
    };
    dragRef.current = next;
    setDrag(next);
  };

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const current = dragRef.current;
      if (!current || event.pointerId !== current.pointerId) return;
      const dx = event.clientX - current.startX;
      const dy = event.clientY - current.startY;
      const moved = current.moved || Math.hypot(dx, dy) >= DRAG_THRESHOLD;
      const hover = moved
        ? hitDrop(
            event.clientX,
            event.clientY,
            current.anchorCol,
            current.anchorRow,
          )
        : null;
      const next = {
        ...current,
        x: event.clientX,
        y: event.clientY,
        moved,
        hover,
        valid: moved && dropValid(current.itemId, hover, current.rotated),
      };
      dragRef.current = next;
      setDrag(next);
    };
    const finish = (event: PointerEvent) => {
      const current = dragRef.current;
      if (!current || event.pointerId !== current.pointerId) return;
      dragRef.current = null;
      setDrag(null);
      if (!current.moved || !layoutRef.current) return;
      const dest = current.valid ? current.hover : null;
      if (!dest) return;
      const next = moveCollectionItem(
        layoutRef.current,
        itemsRef.current,
        current.itemId,
        dest,
        current.rotated,
      );
      if (next) commitLayout(next);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "r" && event.key !== "R") return;
      const current = dragRef.current;
      if (!current) return;
      event.preventDefault();
      const item = itemsRef.current.find((row) => row.id === current.itemId);
      if (!item) return;
      const size = collectionItemSize(item, current.rotated);
      const nextGrab = rotateCollectionDragGrab(
        size.width,
        size.height,
        current.anchorCol,
        current.anchorRow,
        current.grabX,
        current.grabY,
        current.stride,
      );
      const rotated = !current.rotated;
      const hover = current.moved
        ? hitDrop(
            current.x,
            current.y,
            nextGrab.anchorCol,
            nextGrab.anchorRow,
          )
        : current.hover;
      const next = {
        ...current,
        rotated,
        anchorCol: nextGrab.anchorCol,
        anchorRow: nextGrab.anchorRow,
        grabX: nextGrab.grabX,
        grabY: nextGrab.grabY,
        hover,
        valid: current.moved && dropValid(current.itemId, hover, rotated),
      };
      dragRef.current = next;
      setDrag(next);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", finish);
    window.addEventListener("pointercancel", finish);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", finish);
      window.removeEventListener("pointercancel", finish);
      window.removeEventListener("keydown", onKey);
    };
  }, [commitLayout, dropValid, hitDrop]);

  const draggingItem = drag
    ? itemsRef.current.find((item) => item.id === drag.itemId)
    : undefined;
  const dragSize = draggingItem
    ? collectionItemSize(draggingItem, drag?.rotated)
    : null;
  const snappedGhost =
    drag && dragSize
      ? snappedGhostRect(drag.hover, gridEl.current, dragSize.width, dragSize.height)
      : null;
  const ghostMetrics = gridEl.current ? readGridMetrics(gridEl.current) : null;
  const floatingGhost = dragSize
    ? ghostSize(
        dragSize.width,
        dragSize.height,
        ghostMetrics?.cell || 40,
        ghostMetrics?.gap || 2,
      )
    : null;
  const ghost = snappedGhost || (drag && floatingGhost
    ? {
        left: drag.x - drag.grabX,
        top: drag.y - drag.grabY,
        width: floatingGhost.width,
        height: floatingGhost.height,
      }
    : null);

  if (
    (catalogQuery.isLoading && !catalogQuery.data) ||
    (layoutQuery.isLoading && !layout)
  ) {
    return (
      <div className={trade.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError && !catalogQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="收集清单加载失败"
        description={apiError(catalogQuery.error, "收集清单加载失败")}
      />
    );
  }

  const total = items?.length || 0;

  return (
    <div
      className={`${styles.page}${drag?.moved ? ` ${styles.dragging}` : ""}`}
      style={{ "--cell": `${cellPx}px` } as CSSProperties}
    >
      {!task ? (
        <p className={styles.empty}>当前赛季目录里没有收藏家任务。</p>
      ) : null}
      {task && !items?.length ? (
        <p className={styles.empty}>这份收藏家任务暂时没有需上交的道具。</p>
      ) : null}
      <div className={styles.workspace}>
        <section className={styles.boardPane} aria-label="收藏家格子">
          <header className={styles.paneHead}>
            <h3 className={styles.boxTitle}>已收集</h3>
            <p className={styles.paneMeta}>
              {slots.length}/{total} · {gridSize.cols}×{gridSize.rows}
            </p>
            {layout && layout.placements.length ? (
              <button
                type="button"
                className={styles.clearBtn}
                onClick={() => commitLayout(clearCollectionLayout())}
              >
                清空
              </button>
            ) : null}
          </header>
          <div className={styles.board} ref={setBoardNode}>
            <div
              className={styles.cadWrap}
              style={
                {
                  "--cols": gridSize.cols,
                  "--rows": gridSize.rows,
                } as CSSProperties
              }
            >
              {bounds.used ? (
                <>
                  <CadDimension
                    kind="h"
                    cells={bounds.width}
                    col0={bounds.col0}
                    row0={bounds.row0}
                  />
                  <CadDimension
                    kind="v"
                    cells={bounds.height}
                    col0={bounds.col0}
                    row0={bounds.row0}
                  />
                </>
              ) : null}
              <div
                className={styles.grid}
                ref={(node) => {
                  gridEl.current = node;
                }}
              >
                {Array.from({ length: gridSize.cols * gridSize.rows }, (_, cell) => (
                  <span
                    key={cell}
                    className={styles.cellBg}
                    style={{
                      gridColumn: (cell % gridSize.cols) + 1,
                      gridRow: Math.floor(cell / gridSize.cols) + 1,
                    }}
                  />
                ))}
                {bounds.used ? (
                  <span
                    className={styles.bounds}
                    style={{
                      gridColumn: `${bounds.col0 + 1} / span ${bounds.width}`,
                      gridRow: `${bounds.row0 + 1} / span ${bounds.height}`,
                    }}
                  />
                ) : null}
                {drag?.moved && drag.hover?.kind === "grid" && draggingItem ? (
                  <span
                    className={`${styles.dropPreview}${
                      drag.valid ? ` ${styles.dropOk}` : ` ${styles.dropBad}`
                    }`}
                    style={{
                      gridColumn: `${drag.hover.col + 1} / span ${
                        collectionItemSize(draggingItem, drag.rotated).width
                      }`,
                      gridRow: `${drag.hover.row + 1} / span ${
                        collectionItemSize(draggingItem, drag.rotated).height
                      }`,
                    }}
                  />
                ) : null}
                {slots.map((slot) => (
                  <PlacedItem
                    key={slot.item.id}
                    slot={slot}
                    dragging={drag?.itemId === slot.item.id && drag.moved}
                    onPointerDown={beginDrag}
                  />
                ))}
              </div>
              {!slots.length && total ? (
                <p className={styles.boardHint}>
                  从右侧拖入，或 Ctrl+点击自动落入
                </p>
              ) : null}
            </div>
          </div>
        </section>
        <section
          className={`${styles.tray}${
            drag?.moved && drag.hover?.kind === "tray" ? ` ${styles.trayHot}` : ""
          }`}
          aria-label="未收集道具"
          ref={(node) => {
            trayEl.current = node;
          }}
        >
          <header className={styles.paneHead}>
            <h3 className={styles.boxTitle}>未收集</h3>
            <p className={styles.paneMeta}>{uncollected.length}</p>
          </header>
          <div className={styles.trayBody}>
            {trayGroups.length ? (
              trayGroups.map((group) => (
                <section key={group.key} className={styles.trayGroup}>
                  <h4 className={styles.trayGroupTitle}>
                    {group.label}
                    <span>{group.items.length}</span>
                  </h4>
                  <div className={styles.trayGrid}>
                    {group.items.map((item) => (
                      <CollectionItemCard
                        key={item.id}
                        item={item}
                        rotated={Boolean(unplacedRotated[item.id])}
                        dragging={drag?.itemId === item.id && drag.moved}
                        onPointerDown={beginDrag}
                      />
                    ))}
                  </div>
                </section>
              ))
            ) : (
              <p className={styles.empty}>
                道具都在格子里。拖回这里即未收集。
              </p>
            )}
          </div>
        </section>
      </div>
      {drag?.moved && draggingItem && ghost ? (
        <div
          className={styles.ghost}
          style={{
            left: ghost.left,
            top: ghost.top,
            width: ghost.width,
            height: ghost.height,
          }}
        >
          {collectionItemImageUrl(draggingItem.icon_link, draggingItem.id) ||
          inventoryThumbUrl(draggingItem.icon_link, draggingItem.id) ? (
            <CollectionItemImage item={draggingItem} />
          ) : (
            <span>{itemLabel(draggingItem)}</span>
          )}
        </div>
      ) : null}
    </div>
  );
}

function PlacedItem({
  slot,
  dragging,
  onPointerDown,
}: {
  slot: CollectionSlot;
  dragging?: boolean;
  onPointerDown: (
    event: ReactPointerEvent<HTMLDivElement>,
    item: TarkovCollectionItem,
    rotated: boolean,
  ) => void;
}) {
  const { item } = slot;
  const count = Number(item.count || 1);
  return (
    <div
      className={`${styles.item}${dragging ? ` ${styles.itemDragging}` : ""}`}
      style={{
        gridColumn: `${slot.col + 1} / span ${slot.width}`,
        gridRow: `${slot.row + 1} / span ${slot.height}`,
      }}
      onPointerDown={(event) => onPointerDown(event, item, Boolean(slot.rotated))}
      onContextMenu={(event) => {
        if (isToggleClick(event)) event.preventDefault();
      }}
    >
      <div className={styles.itemBody}>
        <CollectionItemImage item={item} className={styles.itemIcon} />
        <ItemShortName item={item} />
        {item.found_in_raid ? <FirMark /> : null}
        {count > 1 ? <span className={styles.count}>{count}</span> : null}
      </div>
    </div>
  );
}
