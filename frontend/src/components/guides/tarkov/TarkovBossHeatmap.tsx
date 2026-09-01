import { Modal, Tooltip } from "antd";
import { Suspense, lazy, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TarkovMapBoss } from "@/api/guidesApi";
import { PanelFallback } from "@/components/RouteFallback";
import { tarkovBossHref, tarkovMapHref } from "@/lib/tarkovHomeNav";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import {
  buildBossHeatmap,
  formatHoverAria,
  formatHoverSquadCount,
  formatHoverSquadSizes,
  heatmapCellHoverBlocks,
  heatmapMapParentSlug,
  heatmapSpawnLocationOptions,
  hoverEscortSchemes,
  hoverUsesLocationCounts,
  lookupEscortPortrait,
  sharedHoverLand,
  type HeatmapBoss,
  type HeatmapBossInput,
  type HeatmapHoverBlock,
  type HeatmapRecipe,
  type HeatmapSpawnPoint,
  type HoverEscortScheme,
} from "@/lib/tarkovBossHeatmap";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import styles from "./TarkovBossHeatmap.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

type SpawnPick = {
  boss: HeatmapBoss;
  mapSlug: string;
  mapName: string;
  chancePct: number;
  points: HeatmapSpawnPoint[];
  recipes: HeatmapRecipe[];
};

type Props = {
  bosses: readonly HeatmapBossInput[];
  portraits?: ReadonlyMap<string, string>;
};

const EMPTY_PORTRAITS = new Map<string, string>();

export function TarkovBossHeatmap({ bosses, portraits }: Props) {
  const model = useMemo(() => buildBossHeatmap(bosses), [bosses]);
  const portraitMap = portraits || EMPTY_PORTRAITS;
  const [spawn, setSpawn] = useState<SpawnPick | null>(null);
  const [focus, setFocus] = useState<TarkovMapFocusRequest | null>(null);

  if (!model.bosses.length || !model.maps.length) {
    return <div className={styles.hint}>暂无刷怪数据</div>;
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.grid}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.thName}>名称</th>
              {model.maps.map((col) => (
                <th key={col.slug} className={styles.thMap}>
                  <Link className={styles.thMapBtn} to={tarkovMapHref(col.slug)}>
                    <span className={styles.mapShort}>{col.short}</span>
                    {col.pool ? <span className={styles.poolMark}>五选一</span> : null}
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.bosses.map((boss, rowIdx) => (
              <tr key={boss.id}>
                <th className={styles.tdName} scope="row">
                  <Link className={styles.bossLink} to={tarkovBossHref(boss.slug)}>
                    {boss.portrait ? (
                      <img
                        className={styles.avatar}
                        src={boss.portrait}
                        alt=""
                        width={32}
                        height={32}
                      />
                    ) : (
                      <span className={styles.avatar} />
                    )}
                    <span className={styles.bossName}>{boss.name}</span>
                  </Link>
                </th>
                {model.maps.map((col, colIdx) => {
                  const cell = model.cells[rowIdx][colIdx];
                  if (!cell.label) {
                    return <td key={col.slug} className={styles.tdEmpty} />;
                  }
                  const blocks = heatmapCellHoverBlocks(cell.recipes, boss);
                  return (
                    <td
                      key={col.slug}
                      className={`${styles.tdCell} ${cell.pool ? styles.poolCell : ""}`}
                      style={{ ["--heat" as string]: cell.chancePct }}
                    >
                      <Tooltip
                        title={
                          <EscortHoverTip
                            blocks={blocks}
                            portraits={portraitMap}
                            mapSlug={col.slug}
                          />
                        }
                        mouseEnterDelay={0.08}
                        mouseLeaveDelay={0.08}
                        placement="top"
                        trigger={["hover"]}
                        {...(spawn ? { open: false } : {})}
                        autoAdjustOverflow
                        overlayClassName={styles.tip}
                        getPopupContainer={() => document.body}
                        destroyTooltipOnHide
                        zIndex={1200}
                      >
                          <span
                          className={styles.cellBtn}
                          role="button"
                          tabIndex={0}
                          aria-label={`${cell.label}${cell.locationCount > 1 ? `，${cell.locationCount}个区域` : ""}，点击查看刷新区域，${formatHoverAria(blocks)}`}
                          onClick={() => {
                            const first = heatmapSpawnLocationOptions(
                              cell.spawnPoints,
                            )[0];
                            setSpawn({
                              boss,
                              mapSlug: col.slug,
                              mapName: col.name,
                              chancePct: cell.chancePct,
                              points: cell.spawnPoints,
                              recipes: cell.recipes,
                            });
                            setFocus(
                              first
                                ? { x: first.x, y: first.y, z: first.z, seq: 1 }
                                : null,
                            );
                          }}
                          onKeyDown={(event) => {
                            if (event.key !== "Enter" && event.key !== " ") return;
                            event.preventDefault();
                            (event.currentTarget as HTMLSpanElement).click();
                          }}
                        >
                          <span>{cell.label}</span>
                          {cell.locationCount > 1 ? (
                            <span className={styles.times}>{cell.locationCount}个区域</span>
                          ) : null}
                        </span>
                      </Tooltip>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SpawnMapModal
        spawn={spawn}
        focus={focus}
        onClose={() => {
          setSpawn(null);
          setFocus(null);
        }}
        onFocus={(point) =>
          setFocus((prev) => ({
            x: point.x,
            y: point.y,
            z: point.z,
            seq: (prev?.seq || 0) + 1,
          }))
        }
      />
    </div>
  );
}

function overlayBoss(spawn: SpawnPick): TarkovMapBoss {
  const byName = new Map<string, HeatmapSpawnPoint[]>();
  for (const row of spawn.points) {
    const list = byName.get(row.name) || [];
    list.push(row);
    byName.set(row.name, list);
  }
  return {
    id: spawn.boss.id,
    slug: spawn.boss.slug,
    name: spawn.boss.name,
    kind: "boss",
    spawn_chance: Math.round(spawn.chancePct),
    locations: [...byName.entries()].map(([name, pts]) => ({
      name,
      chance: pts[0]?.chance ?? 0,
      positions: pts.map((point) => ({ x: point.x, y: point.y, z: point.z })),
    })),
  };
}

function SpawnMapModal({
  spawn,
  focus,
  onClose,
  onFocus,
}: {
  spawn: SpawnPick | null;
  focus: TarkovMapFocusRequest | null;
  onClose: () => void;
  onFocus: (point: HeatmapSpawnPoint) => void;
}) {
  const locations = spawn ? heatmapSpawnLocationOptions(spawn.points) : [];
  const countBlocks = spawn
    ? heatmapCellHoverBlocks(spawn.recipes, spawn.boss)
    : [];
  const activeName = focus
    ? locations.find((row) => row.x === focus.x && row.z === focus.z)?.name
    : locations[0]?.name;
  return (
    <Modal
      open={Boolean(spawn)}
      title={spawn ? `${spawn.boss.name} · ${spawn.mapName}` : ""}
      footer={null}
      destroyOnClose
      width={980}
      zIndex={1300}
      className={styles.spawnModal}
      onCancel={onClose}
      afterOpenChange={(open) => {
        if (!open || !spawn) return;
        window.dispatchEvent(new Event("resize"));
        const first = locations[0];
        if (first) onFocus(first);
      }}
    >
      {spawn ? (
        <div className={styles.spawnModalBody}>
          {locations.length ? (
            hoverUsesLocationCounts(countBlocks) ? (
              <div className={styles.spawnCountGroups}>
                {countBlocks.map((block, index) => {
                  const count = formatHoverSquadCount(
                    block.squadSizes,
                    block.showChance,
                  );
                  return (
                    <div
                      key={`${(block.locations || []).join("|")}-${index}`}
                      className={styles.spawnCountGroup}
                    >
                      {count ? (
                        <div className={styles.spawnCountHead}>出生数量：{count}</div>
                      ) : null}
                      <div className={styles.spawnLocs} role="list">
                        {(block.locations || []).map((name) => {
                          const row = locations.find((item) => item.name === name);
                          if (!row) return null;
                          return (
                            <button
                              key={`${row.name}-${row.x}-${row.z}`}
                              type="button"
                              className={`${styles.spawnLoc} ${
                                row.name === activeName ? styles.spawnLocOn : ""
                              }`}
                              onClick={() => onFocus(row)}
                            >
                              {tarkovMapLabel(row.name, spawn.mapSlug) || row.name}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className={styles.spawnLocs} role="list">
                {locations.map((row) => (
                  <button
                    key={`${row.name}-${row.x}-${row.z}`}
                    type="button"
                    className={`${styles.spawnLoc} ${
                      row.name === activeName ? styles.spawnLocOn : ""
                    }`}
                    onClick={() => onFocus(row)}
                  >
                    {tarkovMapLabel(row.name, spawn.mapSlug) || row.name}
                  </button>
                ))}
              </div>
            )
          ) : (
            <div className={styles.spawnEmpty}>这份数据没有坐标，仍可看底图</div>
          )}
          <div className={styles.spawnMap}>
            <Suspense fallback={<PanelFallback tip="加载地图…" />}>
              <TarkovMapViewer
                slug={spawn.mapSlug}
                parentSlug={heatmapMapParentSlug(spawn.mapSlug) || undefined}
                bosses={[overlayBoss(spawn)]}
                extracts={[]}
                spawns={[]}
                overlayMode="boss-spawns"
                layerChrome="floors"
                focusRequest={focus}
                suppressLocalFix
                fill
              />
            </Suspense>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function EscortHoverTip({
  blocks,
  portraits,
  mapSlug,
}: {
  blocks: readonly HeatmapHoverBlock[];
  portraits: ReadonlyMap<string, string>;
  mapSlug: string;
}) {
  const landOnce = sharedHoverLand(blocks);
  const schemes = hoverEscortSchemes(blocks);
  const byLocation = hoverUsesLocationCounts(blocks);
  return (
    <div className={styles.tipBody}>
      {landOnce ? (
        <div className={styles.tipHead}>出生时间：{landOnce}</div>
      ) : null}
      {byLocation ? (
        <div className={styles.tipLocs}>
          {blocks.map((block, index) => (
            <div
              key={`${(block.locations || []).join("|")}-${index}`}
              className={styles.tipLoc}
            >
              {block.squadSizes.length ? (
                <div className={styles.tipHead}>
                  出生数量：{formatHoverSquadCount(block.squadSizes, block.showChance)}
                </div>
              ) : null}
              {(block.locations || []).map((name) => (
                <div key={name} className={styles.tipLocName}>
                  {tarkovMapLabel(name, mapSlug) || name}
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : schemes ? (
        <>
          {blocks.map((block, index) => (
            <SquadSizeLines
              key={`size-${block.chance}-${block.land}-${index}`}
              block={block}
              landOnce={landOnce}
              hideLand
            />
          ))}
          <div className={styles.tipHead}>出生伴随：</div>
          {schemes.map((row) => (
            <SchemeLine key={row.index} row={row} portraits={portraits} landOnce={landOnce} />
          ))}
        </>
      ) : (
        blocks.map((block, index) => (
          <div key={`${block.chance}-${block.land}-${index}`} className={styles.tipBlock}>
            <SquadSizeLines block={block} landOnce={landOnce} />
            {block.showChance && block.chance && !block.squadSizes.length ? (
              <div className={styles.tipChance}>{block.chance}</div>
            ) : null}
            {block.escorts.length || !block.squadSizes.length ? (
              <>
                <div className={styles.tipHead}>出生伴随：</div>
                {block.escorts.length ? (
                  <ul className={styles.tipList}>
                    {block.escorts.map((row, rowIdx) => {
                      const portrait = lookupEscortPortrait(row, portraits);
                      return (
                        <li key={`${row.slug}-${row.count}-${rowIdx}`} className={styles.tipEscort}>
                          {portrait ? (
                            <img className={styles.tipAvatar} src={portrait} alt="" width={22} height={22} />
                          ) : (
                            <span className={styles.tipAvatar} />
                          )}
                          <span className={styles.tipName}>{row.name}</span>
                          <span className={styles.tipCount}>×{row.count}</span>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <div className={styles.tipEmpty}>无</div>
                )}
              </>
            ) : null}
          </div>
        ))
      )}
    </div>
  );
}

function SquadSizeLines({
  block,
  landOnce,
  hideLand = false,
}: {
  block: HeatmapHoverBlock;
  landOnce: string;
  hideLand?: boolean;
}) {
  return (
    <>
      {!hideLand && !landOnce && block.land ? (
        <div className={styles.tipHead}>出生时间：{block.land}</div>
      ) : null}
      {block.squadSizes.length > 1 ? (
        <>
          <div className={styles.tipHead}>出生数量：</div>
          {block.squadSizes.map((row, index) => (
            <div key={`${row.size}-${row.chance}`} className={styles.tipScheme}>
              <span className={styles.tipSchemeMark}>组合{index + 1}：</span>
              <span>
                {row.size}人
                {block.showChance ? `（${row.chance}）` : ""}
              </span>
            </div>
          ))}
        </>
      ) : block.squadSizes.length ? (
        <div className={styles.tipHead}>
          出生数量：{formatHoverSquadSizes(block.squadSizes, block.showChance)}
        </div>
      ) : null}
    </>
  );
}

function SchemeLine({
  row,
  portraits,
  landOnce,
}: {
  row: HoverEscortScheme;
  portraits: ReadonlyMap<string, string>;
  landOnce: string;
}) {
  const chance = row.showChance && row.chance ? `（${row.chance}）` : "";
  const land = !landOnce && row.land ? ` · ${row.land}` : "";
  const portrait =
    row.escorts.length === 1 ? lookupEscortPortrait(row.escorts[0]!, portraits) : "";
  return (
    <div className={styles.tipScheme}>
      <span className={styles.tipSchemeMark}>
        组合{row.index}
        {chance}：
      </span>
      {portrait ? (
        <img className={styles.tipAvatar} src={portrait} alt="" width={22} height={22} />
      ) : null}
      <span>
        {row.line}
        {land}
      </span>
    </div>
  );
}
