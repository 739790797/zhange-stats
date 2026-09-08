import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Button, Input, Modal, Spin, message } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  fetchTarkovWorkbenchAllowed,
  fetchTarkovWorkbenchCalculate,
  fetchTarkovWorkbenchGun,
  type TarkovWorkbenchCommunityBuild,
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
  collectWorkbenchGridSlots,
  layoutWorkbenchGrid,
  workbenchGunArtSource,
  WORKBENCH_GUN_COL,
  WORKBENCH_GUN_COL_SPAN,
} from "@/lib/tarkovWorkbenchIconLayout";
import { TarkovWorkbenchCommunityModal } from "./TarkovWorkbenchCommunityModal";
import { TarkovWorkbenchStatsPane } from "./TarkovWorkbenchStatsPane";
import styles from "./TarkovWorkbenchBuild.module.css";

type Props = { gunId: string; onChangeGun?: () => void };

function partLabel(part: TarkovWorkbenchPart | null | undefined): string {
  return part?.name || part?.short_name || part?.id || "空";
}

function slotPickerTitle(slot: TarkovWorkbenchSlotNode): string {
  const installed = slot.installed
    ? partLabel(slot.installed)
    : "空";
  return `${slot.name}${slot.required ? " · 必装" : ""} · ${installed}`;
}

function SlotPartPicker({
  slot,
  parts,
  loading,
  installedIds,
  installedParts,
  onInstall,
}: {
  slot: TarkovWorkbenchSlotNode;
  parts: TarkovWorkbenchPart[];
  loading: boolean;
  installedIds: string[];
  installedParts: Array<{ id: string; conflicting_ids?: string[] | null }>;
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

function gridCellClass(
  cell: {
    slotId: string;
    itemId: string;
    empty: boolean;
    required: boolean;
  },
  activeSlotId: string | null,
  conflicts: Set<string>,
): string {
  const active = cell.slotId === activeSlotId;
  const conflict = Boolean(cell.itemId && conflicts.has(cell.itemId));
  return [
    styles.gridCell,
    active ? styles.gridCellActive : "",
    cell.empty ? styles.gridCellEmpty : "",
    cell.empty && cell.required ? styles.gridCellEmptyRequired : "",
    conflict ? styles.gridCellConflict : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function WorkbenchIconBoard({
  gun,
  slots,
  activeSlotId,
  conflicts,
  onSelectSlot,
  onClosePicker,
  onUnload,
}: {
  gun: TarkovWorkbenchGun;
  slots: TarkovWorkbenchSlotNode[];
  activeSlotId: string | null;
  conflicts: Set<string>;
  onSelectSlot: (id: string) => void;
  onClosePicker: (slotId?: string) => void;
  onUnload: (node: TarkovWorkbenchSlotNode) => void;
}) {
  const layout = useMemo(
    () => layoutWorkbenchGrid(collectWorkbenchGridSlots(slots)),
    [slots],
  );
  const hasInstalled = layout.cells.some((cell) => !cell.empty);
  const gunArt = useMemo(() => {
    const raw = workbenchGunArtSource({
      imageLink: gun.image_link,
      presetImageLink: gun.preset_image_link,
      hasInstalled,
    });
    return hdPreviewUrl(raw) || raw;
  }, [gun.image_link, gun.preset_image_link, hasInstalled]);
  const gridCells = layout.cells.filter((cell) => !cell.extras);
  const extraCells = layout.cells.filter((cell) => cell.extras);

  if (!gunArt && !layout.cells.length) {
    return <p className={styles.hint}>没有枪图</p>;
  }

  const renderCell = (
    cell: (typeof layout.cells)[number],
    style?: { gridColumn: number; gridRow: number },
  ) => {
    const src = cell.empty ? "" : inventoryThumbUrl(cell.icon, cell.itemId);
    return (
      <button
        key={cell.slotId}
        type="button"
        className={gridCellClass(cell, activeSlotId, conflicts)}
        style={style}
        title={`${cell.slotName}${cell.shortName ? ` · ${cell.shortName}` : ""}`}
        onClick={() => onSelectSlot(cell.slotId)}
        onContextMenu={(event) => {
          event.preventDefault();
          const node = findSlotNode(slots, cell.slotId);
          if (node) onUnload(node);
          onClosePicker(cell.slotId);
        }}
      >
        <span className={styles.gridCellInner}>
          {src ? (
            <img src={src} alt="" />
          ) : (
            <span className={styles.gridCellPlus} aria-hidden>
              +
            </span>
          )}
          {cell.shortName ? (
            <span className={styles.gridShortName}>{cell.shortName}</span>
          ) : null}
        </span>
        <span className={styles.gridLabel}>{cell.slotName}</span>
      </button>
    );
  };

  return (
    <div className={styles.iconBoard} aria-label="配件示意图">
      <div className={styles.attachmentGridWrap}>
        <div
          className={styles.attachmentGrid}
          style={{
            gridTemplateRows: `repeat(${layout.totalRows}, var(--wb-cell-h))`,
          }}
        >
          <div
            className={styles.gunCell}
            style={{
              gridColumn: `${WORKBENCH_GUN_COL} / ${WORKBENCH_GUN_COL + WORKBENCH_GUN_COL_SPAN}`,
              gridRow: String(layout.gunRow),
            }}
          >
            {gunArt ? (
              <img src={gunArt} alt={gun.short_name || gun.name || ""} />
            ) : (
              <span className={styles.gridCellPlus} aria-hidden>
                +
              </span>
            )}
            <span className={styles.gridLabel}>
              {gun.short_name || gun.name || ""}
            </span>
          </div>
          {gridCells.map((cell) =>
            renderCell(cell, {
              gridColumn: cell.col || 1,
              gridRow: cell.row || 1,
            }),
          )}
        </div>
        {extraCells.length ? (
          <div className={styles.gridExtras}>{extraCells.map((cell) => renderCell(cell))}</div>
        ) : null}
      </div>
    </div>
  );
}

export function TarkovWorkbenchBuild({ gunId, onChangeGun }: Props) {
  const navigate = useNavigate();
  const gameMode = useTarkovGameMode();
  const [pairs, setPairs] = useState<TarkovWorkbenchPair[]>([]);
  const [ammoId, setAmmoId] = useState<string | null>(null);
  const [slots, setSlots] = useState<TarkovWorkbenchSlotNode[]>([]);
  const [stats, setStats] = useState<TarkovWorkbenchStats | null>(null);
  const [activeSlotId, setActiveSlotId] = useState<string | null>(null);
  const [communityOpen, setCommunityOpen] = useState(false);
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

  const applyPairsAsync = (
    next: TarkovWorkbenchPair[],
    nextAmmo?: string | null,
  ) => {
    const epoch = ++calcEpoch.current;
    return calcMutation.mutateAsync({
      pairs: next,
      ammoId: nextAmmo,
      epoch,
    });
  };

  const applyPairs = (next: TarkovWorkbenchPair[], nextAmmo?: string | null) => {
    void applyPairsAsync(next, nextAmmo);
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

  const applyCommunity = (build: TarkovWorkbenchCommunityBuild) => {
    setCommunityOpen(false);
    closePicker();
    void applyPairsAsync(build.pairs || [], build.ammo_id ?? null)
      .then(() => {
        if (build.dropped_pair_count) {
          message.warning(
            `已装入「${build.name}」，省略了 ${build.dropped_pair_count} 件本站没有的配件`,
          );
        } else {
          message.success(`已装入「${build.name}」`);
        }
      })
      .catch(() => {
        /* calcMutation onError 已提示 */
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
            <Link to={TARKOV_WORKBENCH_PATH}>返回工作台</Link>
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
          <Button
            onClick={() => {
              closePicker();
              setCommunityOpen(true);
            }}
          >
            社区方案
          </Button>
          <Button
            onClick={() =>
              onChangeGun ? onChangeGun() : navigate(tarkovWorkbenchHref())
            }
          >
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
              onSelectSlot={(id) => {
                setActiveSlotId(id);
              }}
              onClosePicker={closePicker}
              onUnload={unloadSlot}
            />
          </div>
          <Modal
            open={Boolean(activeSlot)}
            title={activeSlot ? slotPickerTitle(activeSlot) : ""}
            footer={
              activeSlot?.installed && !activeSlot.required ? (
                <Button
                  onClick={() => {
                    if (activeSlot) unloadSlot(activeSlot);
                  }}
                >
                  卸下
                </Button>
              ) : null
            }
            destroyOnClose
            centered
            width={720}
            className={styles.pickerModal}
            classNames={{
              body: styles.pickerModalBody,
              content: styles.pickerModalContent,
            }}
            onCancel={() => closePicker()}
          >
            {activeSlot ? (
              <SlotPartPicker
                key={activeSlot.id}
                slot={activeSlot}
                parts={allowedQuery.data?.slots?.[activeSlot.id] || []}
                loading={allowedQuery.isLoading}
                installedIds={installedIds}
                installedParts={installedParts}
                onInstall={installPart}
              />
            ) : null}
          </Modal>
        </section>
        <TarkovWorkbenchStatsPane
          stats={stats}
          ammoId={ammoId}
          ammoOptions={ammoOptions}
          hasConflicts={conflicts.size > 0}
          onAmmoChange={(value) => applyPairs(pairs, value)}
        />
      </div>
      <TarkovWorkbenchCommunityModal
        gunId={gunId}
        open={communityOpen}
        onCancel={() => setCommunityOpen(false)}
        onPick={applyCommunity}
      />
    </div>
  );
}
