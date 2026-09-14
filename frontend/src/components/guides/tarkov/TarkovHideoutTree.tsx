import { Button } from "antd";
import { useMemo, useState } from "react";
import {
  canSetHideoutLevel,
  hideoutDefaultLevel,
  type HideoutStationSpec,
} from "@/lib/tarkovHideoutProgress";
import {
  HIDEOUT_TREE_NODE_H,
  HIDEOUT_TREE_NODE_W,
  buildHideoutTreeLayout,
  hideoutTreeActiveKey,
  hideoutTreeClickedKey,
  hideoutTreeFocus,
  hideoutTreeNodeKey,
  hideoutTreeNodeKind,
  hideoutTreeWires,
  type HideoutTreeNode,
} from "@/lib/tarkovHideoutTree";
import styles from "./TarkovHideoutTree.module.css";

type Station = HideoutStationSpec & {
  id?: string;
  slug?: string;
  name?: string;
  image_link?: string;
};

function relatedNodeKey(target: EventTarget | null): string {
  if (!(target instanceof Element)) return "";
  const pin = target.closest("[data-hideout-node]");
  return pin instanceof HTMLElement ? (pin.dataset.hideoutNode || "").trim() : "";
}

export function TarkovHideoutTree({
  stations,
  levels,
  byId,
  stashFloor,
  selectedId,
  selectedLevel,
  pending,
  wiki = false,
  onSelect,
  onChangeLevel,
}: {
  stations: Station[];
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
  stashFloor: number;
  selectedId?: string;
  selectedLevel?: number;
  pending: boolean;
  wiki?: boolean;
  onSelect: (slug: string, level?: number) => void;
  onChangeLevel?: (station: HideoutStationSpec, delta: 1 | -1) => void;
}) {
  const layout = useMemo(() => buildHideoutTreeLayout(stations), [stations]);
  const stationById = useMemo(() => {
    const out = new Map<string, Station>();
    for (const row of stations) {
      const ident = (row.id || "").trim();
      if (ident) out.set(ident, row);
    }
    return out;
  }, [stations]);
  const [hoverKey, setHoverKey] = useState("");
  const selectedKey =
    selectedId && selectedLevel
      ? hideoutTreeNodeKey(selectedId, selectedLevel)
      : "";
  const activeKey = hideoutTreeActiveKey(selectedKey, hoverKey);
  const focus = useMemo(
    () => hideoutTreeFocus(activeKey, layout.edges),
    [activeKey, layout.edges],
  );
  const focusWires = useMemo(
    () => hideoutTreeWires(layout.nodes, layout.edges, focus.edges),
    [focus.edges, layout.edges, layout.nodes],
  );

  const clearHoverUnlessNode = (relatedTarget: EventTarget | null) => {
    if (relatedNodeKey(relatedTarget)) return;
    setHoverKey("");
  };

  return (
    <div className={styles.wrap}>
      <div
        className={styles.board}
        onMouseLeave={() => setHoverKey("")}
      >
        <div
          className={styles.canvas}
          style={{ width: layout.width, height: layout.height }}
        >
          <svg
            className={styles.edges}
            width={layout.width}
            height={layout.height}
            aria-hidden="true"
          >
            {layout.wires.map((wire) => (
              <path
                key={wire.key}
                className={styles.edge}
                d={wire.path}
                strokeWidth={2}
              />
            ))}
            {focusWires.map((wire) => (
              <path
                key={`on:${wire.key}`}
                className={`${styles.edge} ${styles.edgeOn}`}
                d={wire.path}
                strokeWidth={2.5}
              />
            ))}
          </svg>
          {layout.nodes.map((node) => {
            const station = stationById.get(node.stationId);
            if (!station) return null;
            const chosen = node.key === selectedKey;
            const active = node.key === activeKey;
            const prereq = !active && focus.nodes.has(node.key);
            return (
              <TreeNode
                key={node.key}
                node={node}
                station={station}
                current={
                  levels[node.stationId] ??
                  hideoutDefaultLevel(station, stashFloor)
                }
                levels={levels}
                byId={byId}
                stashFloor={stashFloor}
                chosen={chosen}
                active={active}
                prereq={prereq}
                pending={pending}
                wiki={wiki}
                onHover={setHoverKey}
                onLeave={clearHoverUnlessNode}
                onSelect={() => {
                  const next = hideoutTreeClickedKey(selectedKey, node.key);
                  if (!next) onSelect("");
                  else onSelect(station.slug || node.stationId, node.level);
                }}
                onChangeLevel={onChangeLevel}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

function TreeNode({
  node,
  station,
  current,
  levels,
  byId,
  stashFloor,
  chosen,
  active,
  prereq,
  pending,
  wiki,
  onHover,
  onLeave,
  onSelect,
  onChangeLevel,
}: {
  node: HideoutTreeNode;
  station: Station;
  current: number;
  levels: Record<string, number>;
  byId: Map<string, HideoutStationSpec>;
  stashFloor: number;
  chosen: boolean;
  active: boolean;
  prereq: boolean;
  pending: boolean;
  wiki?: boolean;
  onHover: (key: string) => void;
  onLeave: (relatedTarget: EventTarget | null) => void;
  onSelect: () => void;
  onChangeLevel?: (station: HideoutStationSpec, delta: 1 | -1) => void;
}) {
  const ready =
    Boolean(onChangeLevel) &&
    current + 1 === node.level &&
    canSetHideoutLevel(station, node.level, levels, byId, stashFloor);
  const kind = hideoutTreeNodeKind({ current, level: node.level, ready });
  const canDown =
    Boolean(onChangeLevel) &&
    node.level === current &&
    current > hideoutDefaultLevel(station, stashFloor);
  const kindClass =
    wiki || active || prereq
      ? ""
      : kind === "locked"
        ? styles.nodeLocked
        : "";
  return (
    <span
      className={`${styles.pin}${
        active || prereq ? ` ${styles.pinOn}` : ""
      }`}
      data-hideout-node={node.key}
      style={{
        left: node.x,
        top: node.y,
        width: HIDEOUT_TREE_NODE_W,
        height: HIDEOUT_TREE_NODE_H,
      }}
      onMouseEnter={() => onHover(node.key)}
      onMouseLeave={(event) => onLeave(event.relatedTarget)}
    >
      <div
        className={`${styles.node} ${kindClass}${
          active ? ` ${styles.nodeOn}` : prereq ? ` ${styles.nodePrereq}` : ""
        }`}
        role="button"
        tabIndex={0}
        aria-label={`${node.stationName} ${node.roman}`}
        aria-current={chosen ? "true" : undefined}
        aria-pressed={chosen}
        onFocus={() => onHover(node.key)}
        onBlur={(event) => onLeave(event.relatedTarget)}
        onClick={onSelect}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelect();
          }
        }}
      >
        {node.imageLink ? (
          <img className={styles.icon} src={node.imageLink} alt="" />
        ) : null}
        <span className={styles.body}>
          <span className={styles.name}>{node.stationName}</span>
          <span className={styles.roman}>{node.roman}</span>
        </span>
        {onChangeLevel && (ready || canDown) ? (
          <span className={styles.actions}>
            {ready ? (
              <Button
                type="link"
                size="small"
                disabled={pending}
                onClick={(event) => {
                  event.stopPropagation();
                  onChangeLevel(station, 1);
                }}
              >
                建造
              </Button>
            ) : null}
            {canDown ? (
              <Button
                type="link"
                size="small"
                disabled={pending}
                onClick={(event) => {
                  event.stopPropagation();
                  onChangeLevel(station, -1);
                }}
              >
                取消
              </Button>
            ) : null}
          </span>
        ) : null}
      </div>
    </span>
  );
}
