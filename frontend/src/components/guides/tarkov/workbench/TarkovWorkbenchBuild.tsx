import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Button, Input, Select, Spin, message } from "antd";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate } from "react-router-dom";
import {
  fetchTarkovWorkbenchAllowed,
  fetchTarkovWorkbenchCalculate,
  fetchTarkovWorkbenchGun,
  type TarkovWorkbenchGun,
  type TarkovWorkbenchPair,
  type TarkovWorkbenchPart,
  type TarkovWorkbenchSlotNode,
  type TarkovWorkbenchStats,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_WORKBENCH_PATH,
  tarkovWorkbenchHref,
} from "@/lib/tarkovHomeNav";
import { formatMoney, formatPercent, formatWeight } from "@/lib/tarkovItemFormat";
import { hdPreviewUrl, inventoryThumbUrl } from "@/lib/tarkovItemImages";
import { itemDetailHref } from "@/lib/tarkovItemTypes";
import {
  collectInstalledParts,
  collectSlotIds,
  DEFAULT_WORKBENCH_PART_SORT,
  filterWorkbenchParts,
  findSlotNode,
  formatSignedStat,
  pairsFromTree,
  partConflictsWith,
  replacePair,
  replaceSlotInstalled,
  sortWorkbenchParts,
  toggleWorkbenchPartSort,
  type WorkbenchPartSort,
  type WorkbenchPartSortKey,
} from "@/lib/tarkovWorkbench";
import {
  collectSlotHotspots,
  layoutWorkbenchIcons,
  nearestWorkbenchSlot,
  workbenchGunArtSource,
} from "@/lib/tarkovWorkbenchIconLayout";
import styles from "./TarkovWorkbenchBuild.module.css";

type Props = { gunId: string };

function partLabel(part: TarkovWorkbenchPart | null | undefined): string {
  return part?.name || part?.short_name || part?.id || "空";
}

function SlotPickerFloat({
  anchor,
  children,
  onClose,
}: {
  anchor: HTMLElement | null;
  children: ReactNode;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    if (!anchor) {
      setPos(null);
      return;
    }
    const place = () => {
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(480, window.innerWidth - 24);
      const gap = 8;
      let left = rect.right + gap;
      if (left + width > window.innerWidth - 12) {
        left = Math.max(12, rect.left - width - gap);
      }
      let top = rect.top;
      const maxTop = window.innerHeight - 36;
      top = Math.min(Math.max(12, top), maxTop);
      setPos({ left, top });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [anchor]);

  useEffect(() => {
    if (!anchor) return;
    const onDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target) return;
      if (anchor.contains(target)) return;
      if (panelRef.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [anchor, onClose]);

  if (!anchor || !pos || !children) return null;
  return createPortal(
    <div
      ref={panelRef}
      className={styles.pickerFloat}
      style={{ left: pos.left, top: pos.top }}
    >
      {children}
    </div>,
    document.body,
  );
}

function SlotPartPicker({
  slot,
  parts,
  loading,
  installedIds,
  installedParts,
  onClose,
  onInstall,
}: {
  slot: TarkovWorkbenchSlotNode;
  parts: TarkovWorkbenchPart[];
  loading: boolean;
  installedIds: string[];
  installedParts: Array<{ id: string; conflicting_ids?: string[] | null }>;
  onClose: () => void;
  onInstall: (part: TarkovWorkbenchPart) => void;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<WorkbenchPartSort>(DEFAULT_WORKBENCH_PART_SORT);
  const rows = useMemo(
    () => sortWorkbenchParts(filterWorkbenchParts(parts, query), sort),
    [parts, query, sort],
  );

  const sortMark = (key: WorkbenchPartSortKey) => {
    if (sort.key !== key) return "";
    return sort.dir === "asc" ? " ↑" : " ↓";
  };

  return (
    <div className={styles.picker}>
      <div className={styles.paneHead}>
        <span>
          {slot.name}
          {slot.required ? " · 必装" : ""}
          {slot.installed ? ` · ${partLabel(slot.installed)}` : " · 空"}
        </span>
        <Button type="link" size="small" onClick={onClose}>
          关闭
        </Button>
      </div>
      <Input
        className={styles.pickerSearch}
        allowClear
        size="small"
        placeholder="搜索配件"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {loading ? (
        <Spin size="small" />
      ) : (
        <>
          <div className={styles.partHead}>
            <span />
            <button
              type="button"
              className={styles.partHeadBtn}
              onClick={() => setSort((current) => toggleWorkbenchPartSort(current, "name"))}
            >
              配件{sortMark("name")}
            </button>
            <button
              type="button"
              className={styles.partHeadBtn}
              onClick={() =>
                setSort((current) => toggleWorkbenchPartSort(current, "ergonomics"))
              }
            >
              人机{sortMark("ergonomics")}
            </button>
            <button
              type="button"
              className={styles.partHeadBtn}
              onClick={() => setSort((current) => toggleWorkbenchPartSort(current, "recoil"))}
            >
              后坐{sortMark("recoil")}
            </button>
            <button
              type="button"
              className={styles.partHeadBtn}
              onClick={() => setSort((current) => toggleWorkbenchPartSort(current, "weight"))}
            >
              重量{sortMark("weight")}
            </button>
            <button
              type="button"
              className={styles.partHeadBtn}
              onClick={() => setSort((current) => toggleWorkbenchPartSort(current, "price"))}
            >
              估价{sortMark("price")}
            </button>
          </div>
          <div className={styles.parts}>
            {rows.map((part) => {
              const current = slot.installed?.id === part.id;
              const conflict = partConflictsWith(
                part,
                installedIds,
                slot.installed?.id,
                installedParts,
              );
              return (
                <button
                  key={part.id}
                  type="button"
                  className={[
                    styles.part,
                    current ? styles.partCurrent : "",
                    conflict ? styles.partConflict : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  onClick={() => onInstall(part)}
                  title={conflict ? "与已装配件冲突" : partLabel(part)}
                >
                  {inventoryThumbUrl(part.icon_link, part.id) ? (
                    <img
                      className={styles.slotIcon}
                      src={inventoryThumbUrl(part.icon_link, part.id)}
                      alt=""
                    />
                  ) : (
                    <span className={styles.slotIconEmpty} />
                  )}
                  <span className={styles.slotPart}>{partLabel(part)}</span>
                  <span className={styles.partMeta}>
                    {formatSignedStat(part.ergonomics)}
                  </span>
                  <span className={styles.partMeta}>
                    {formatPercent(part.recoil_modifier)}
                  </span>
                  <span className={styles.partMeta}>{formatWeight(part.weight)}</span>
                  <span className={styles.partMeta}>{formatMoney(part.price_rub)}</span>
                </button>
              );
            })}
            {rows.length ? null : <p className={styles.hint}>没有匹配配件</p>}
          </div>
        </>
      )}
    </div>
  );
}

function WorkbenchIconBoard({
  gun,
  slots,
  activeSlotId,
  conflicts,
  picker,
  onSelectSlot,
  onClosePicker,
  onUnload,
}: {
  gun: TarkovWorkbenchGun;
  slots: TarkovWorkbenchSlotNode[];
  activeSlotId: string | null;
  conflicts: Set<string>;
  picker: ReactNode;
  onSelectSlot: (id: string) => void;
  onClosePicker: (slotId?: string) => void;
  onUnload: (node: TarkovWorkbenchSlotNode) => void;
}) {
  const anchors = useRef<Record<string, HTMLButtonElement | null>>({});
  const pieces = useMemo(() => {
    return layoutWorkbenchIcons(collectSlotHotspots(slots));
  }, [slots]);
  const hasInstalled = pieces.some((piece) => !piece.empty);
  const gunArt = useMemo(() => {
    const raw = workbenchGunArtSource({
      imageLink: gun.image_link,
      presetImageLink: gun.preset_image_link,
      hasInstalled,
    });
    return hdPreviewUrl(raw) || raw;
  }, [gun.image_link, gun.preset_image_link, hasInstalled]);
  const activeAnchor = activeSlotId ? anchors.current[activeSlotId] || null : null;

  if (!gunArt && !pieces.length) {
    return <p className={styles.hint}>没有枪图</p>;
  }

  return (
    <div
      className={styles.iconBoard}
      aria-label="枪图与槽位"
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const rect = event.currentTarget.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        const x = ((event.clientX - rect.left) / rect.width) * 100;
        const y = ((event.clientY - rect.top) / rect.height) * 100;
        const slotId = nearestWorkbenchSlot(pieces, x, y);
        if (slotId) onSelectSlot(slotId);
      }}
    >
      {gunArt ? (
        <img
          className={styles.gunArt}
          src={gunArt}
          alt={gun.short_name || gun.name || ""}
        />
      ) : null}
      {pieces.map((piece) => {
        const src = piece.empty
          ? ""
          : inventoryThumbUrl(piece.icon, piece.itemId);
        const active = piece.slotId === activeSlotId;
        const conflict = Boolean(piece.itemId && conflicts.has(piece.itemId));
        return (
          <button
            key={piece.slotId}
            ref={(node) => {
              anchors.current[piece.slotId] = node;
            }}
            type="button"
            className={[
              styles.iconPiece,
              styles.hotspotAnchor,
              active ? styles.iconPieceActive : "",
              piece.empty ? styles.iconPieceEmpty : "",
              piece.empty && piece.required ? styles.iconPieceEmptyRequired : "",
              conflict ? styles.iconPieceConflict : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{ left: `${piece.x}%`, top: `${piece.y}%` }}
            onClick={(event) => {
              event.stopPropagation();
              if (active) onClosePicker(piece.slotId);
              else onSelectSlot(piece.slotId);
            }}
            onContextMenu={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const node = findSlotNode(slots, piece.slotId);
              if (node) onUnload(node);
              onClosePicker(piece.slotId);
            }}
          >
            {src ? (
              <img src={src} alt="" />
            ) : (
              <span className={styles.hotspotEmpty} />
            )}
            <span className={styles.hotspotName}>{piece.slotName}</span>
          </button>
        );
      })}
      <SlotPickerFloat
        anchor={activeAnchor}
        onClose={() => onClosePicker()}
      >
        {picker}
      </SlotPickerFloat>
    </div>
  );
}

export function TarkovWorkbenchBuild({ gunId }: Props) {
  const navigate = useNavigate();
  const gameMode = useTarkovGameMode();
  const [pairs, setPairs] = useState<TarkovWorkbenchPair[]>([]);
  const [ammoId, setAmmoId] = useState<string | null>(null);
  const [slots, setSlots] = useState<TarkovWorkbenchSlotNode[]>([]);
  const [stats, setStats] = useState<TarkovWorkbenchStats | null>(null);
  const [activeSlotId, setActiveSlotId] = useState<string | null>(null);
  const calcEpoch = useRef(0);

  const gunQuery = useQuery({
    queryKey: ["guides-tarkov-workbench-gun", gameMode, gunId],
    queryFn: () => fetchTarkovWorkbenchGun(gunId),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(gunId),
  });

  useEffect(() => {
    calcEpoch.current += 1;
  }, [gunId]);

  useEffect(() => {
    const gun = gunQuery.data;
    if (!gun) return;
    setSlots(gun.slots || []);
    setStats(gun.stats);
    setPairs(gun.factory_pairs?.length ? gun.factory_pairs : pairsFromTree(gun.slots));
    setAmmoId(gun.default_ammo_id || gun.stats?.ammo_id || null);
    setActiveSlotId(null);
  }, [gunQuery.data]);

  const calcMutation = useMutation({
    mutationFn: (next: {
      pairs: TarkovWorkbenchPair[];
      ammoId?: string | null;
      epoch: number;
    }) =>
      fetchTarkovWorkbenchCalculate({
        gunId,
        pairs: next.pairs,
        ammoId: next.ammoId === undefined ? ammoId : next.ammoId,
      }),
    onSuccess: (data, vars) => {
      if (vars.epoch !== calcEpoch.current) return;
      const nextSlots = data.slots || [];
      setSlots(nextSlots);
      setStats(data.stats);
      setPairs(pairsFromTree(nextSlots));
      if (vars.ammoId !== undefined) setAmmoId(vars.ammoId);
      setActiveSlotId((current) =>
        current && findSlotNode(nextSlots, current) ? current : null,
      );
    },
    onError: (error) => {
      message.error(apiError(error, "属性计算失败"));
    },
  });

  const slotIds = useMemo(() => collectSlotIds(slots), [slots]);
  const allowedQuery = useQuery({
    queryKey: ["guides-tarkov-workbench-allowed", gameMode, slotIds.join(",")],
    queryFn: () => fetchTarkovWorkbenchAllowed(slotIds),
    enabled: slotIds.length > 0,
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const activeSlot = activeSlotId ? findSlotNode(slots, activeSlotId) : null;
  const installedIds = useMemo(
    () => pairs.map((row) => row.item_id).filter(Boolean),
    [pairs],
  );
  const installedParts = useMemo(() => collectInstalledParts(slots), [slots]);
  const conflicts = useMemo(
    () => new Set(stats?.conflicts || []),
    [stats?.conflicts],
  );

  const applyPairs = (next: TarkovWorkbenchPair[], nextAmmo?: string | null) => {
    const epoch = ++calcEpoch.current;
    calcMutation.mutate({
      pairs: next,
      ammoId: nextAmmo,
      epoch,
    });
  };

  const unloadSlot = (node: TarkovWorkbenchSlotNode) => {
    if (!node.installed) return;
    if (node.required) {
      message.info("必装槽请改选配件，不能卸空");
      return;
    }
    const next = replacePair(pairs, node.id, null, collectSlotIds(node.children));
    setPairs(next);
    setSlots((current) => replaceSlotInstalled(current, node.id, null));
    applyPairs(next);
  };

  const closePicker = (slotId?: string) => {
    setActiveSlotId((current) => {
      if (slotId && current && current !== slotId) return current;
      return null;
    });
  };

  const installPart = (part: TarkovWorkbenchPart) => {
    if (!activeSlot) return;
    if (activeSlot.installed?.id === part.id) {
      closePicker();
      return;
    }
    if (partConflictsWith(part, installedIds, activeSlot.installed?.id, installedParts)) {
      message.warning("与已装配件冲突");
      return;
    }
    const next = replacePair(
      pairs,
      activeSlot.id,
      part.id,
      collectSlotIds(activeSlot.children),
    );
    setPairs(next);
    setSlots((current) => replaceSlotInstalled(current, activeSlot.id, part));
    applyPairs(next);
    closePicker();
  };

  if (gunQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin tip="加载工作台…" />
      </div>
    );
  }

  if (gunQuery.isError || !gunQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="无法打开这把枪"
        description={
          <>
            {apiError(gunQuery.error, "未找到枪械")}
            {" · "}
            <Link to={TARKOV_WORKBENCH_PATH}>返回选枪</Link>
          </>
        }
      />
    );
  }

  const gun = gunQuery.data;
  const ammoOptions = (gun.ammo || []).map((row) => ({
    value: row.id,
    label: row.name || row.short_name || row.id,
  }));

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 className={styles.title}>
          <Link to={itemDetailHref("guns", gun.id)}>
            {gun.name || gun.short_name || gun.id}
          </Link>
        </h2>
        <div className={styles.actions}>
          <Button onClick={() => navigate(tarkovWorkbenchHref())}>
            换一把枪
          </Button>
          <Button
            loading={calcMutation.isPending}
            onClick={() => {
              closePicker();
              applyPairs([], ammoId);
            }}
          >
            清空配件
          </Button>
          <Button
            loading={calcMutation.isPending}
            onClick={() => {
              closePicker();
              applyPairs(gun.factory_pairs || [], gun.default_ammo_id || null);
            }}
          >
            恢复预设
          </Button>
        </div>
      </div>

      <div className={styles.layout}>
        <section
          className={`${styles.pane} ${styles.previewPane}`}
          aria-label="预览与配件"
        >
          <div className={styles.preview}>
            <WorkbenchIconBoard
              gun={gun}
              slots={slots}
              activeSlotId={activeSlotId}
              conflicts={conflicts}
              picker={
                activeSlot ? (
                  <SlotPartPicker
                    key={activeSlot.id}
                    slot={activeSlot}
                    parts={allowedQuery.data?.slots?.[activeSlot.id] || []}
                    loading={allowedQuery.isLoading}
                    installedIds={installedIds}
                    installedParts={installedParts}
                    onClose={() => closePicker()}
                    onInstall={installPart}
                  />
                ) : null
              }
              onSelectSlot={(id) => {
                setActiveSlotId(id);
              }}
              onClosePicker={closePicker}
              onUnload={unloadSlot}
            />
          </div>
        </section>

        <section className={`${styles.pane} ${styles.statsPane}`} aria-label="属性">
          <div className={styles.paneHead}>属性</div>
          <div className={styles.stats}>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>人机</span>
              <span className={styles.statValue}>
                {stats?.ergonomics ?? "—"}
              </span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>垂直后坐</span>
              <span className={styles.statValue}>
                {stats?.recoil_vertical ?? "—"}
              </span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>水平后坐</span>
              <span className={styles.statValue}>
                {stats?.recoil_horizontal ?? "—"}
              </span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>重量</span>
              <span className={styles.statValue}>
                {formatWeight(stats?.weight)}
              </span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>瞄具距离</span>
              <span className={styles.statValue}>
                {stats?.sighting_range ?? "—"}
              </span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>弹匣容量</span>
              <span className={styles.statValue}>
                {stats?.mag_capacity ?? "—"}
              </span>
            </div>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>估价</span>
              <span className={styles.statValue}>
                {formatMoney(stats?.price_rub)}
              </span>
            </div>
            {stats?.overswing ? (
              <p className={styles.warn}>过摆：当前重量超过人机阈值</p>
            ) : null}
            {conflicts.size ? (
              <p className={styles.warn}>冲突件已标红，请卸下或更换</p>
            ) : null}
            {ammoOptions.length ? (
              <div className={styles.ammo}>
                <div className={styles.statLabel}>弹药</div>
                <Select
                  size="small"
                  showSearch
                  optionFilterProp="label"
                  style={{ width: "100%", marginTop: 6 }}
                  value={ammoId || undefined}
                  options={ammoOptions}
                  onChange={(value) => applyPairs(pairs, value)}
                />
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
