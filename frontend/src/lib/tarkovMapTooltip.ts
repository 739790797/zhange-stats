/** 地图 hover 气泡：视口上下翻转，并避开已打开的任务气泡。 */

export const TARKOV_MAP_TIP_QUEST = "tarkov-map-tip-quest";
export const TARKOV_MAP_TIP_SPAWN = "tarkov-map-tip-spawn";
/** 从标点挪到气泡上的间隙：延迟关掉，避免一离开图标就收起。 */
export const CANVAS_TOOLTIP_HIDE_MS = 200;

export type TarkovMapTooltipSide = "top" | "bottom";

export type TarkovMapTooltipBox = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

export function pickTooltipVerticalSide(input: {
  pointY: number;
  mapHeight: number;
  tooltipHeight: number;
  margin?: number;
  prefer?: TarkovMapTooltipSide;
}): TarkovMapTooltipSide {
  const margin = input.margin ?? 8;
  const prefer = input.prefer ?? "top";
  if (input.mapHeight <= 0) return prefer;
  const height = Math.max(1, input.tooltipHeight);
  const above = input.pointY - margin;
  const below = input.mapHeight - input.pointY - margin;
  const topFits = above >= height;
  const bottomFits = below >= height;
  if (prefer === "top") {
    if (topFits) return "top";
    if (bottomFits) return "bottom";
  } else {
    if (bottomFits) return "bottom";
    if (topFits) return "top";
  }
  return above >= below ? "top" : "bottom";
}

export function tooltipOffsetForSide(
  side: TarkovMapTooltipSide,
  pad: number,
): [number, number] {
  const y = Math.abs(pad) || 12;
  return side === "top" ? [0, -y] : [0, y];
}

export function oppositeTooltipSide(
  side: TarkovMapTooltipSide,
): TarkovMapTooltipSide {
  return side === "top" ? "bottom" : "top";
}

export function tooltipSideFromClassName(
  className: string,
): TarkovMapTooltipSide | null {
  if (/\bleaflet-tooltip-bottom\b/.test(className)) return "bottom";
  if (/\bleaflet-tooltip-top\b/.test(className)) return "top";
  return null;
}

export function estimatedCanvasTooltipHeight(html: string): number {
  const text = html || "";
  if (text.includes("lootLooseTip")) return 56;
  if (text.includes("lockTip")) return 52;
  return 48;
}

export function lootDetailCardOverflowFlip(
  card: TarkovMapTooltipBox,
  wrap: TarkovMapTooltipBox,
): { flipX: boolean; flipY: boolean } {
  return {
    flipX: card.right > wrap.right + 1,
    flipY: card.top < wrap.top - 1,
  };
}

export function tooltipBoxesOverlap(
  a: TarkovMapTooltipBox,
  b: TarkovMapTooltipBox,
): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

export type TarkovMapSiblingTooltip = {
  box: TarkovMapTooltipBox;
  side: TarkovMapTooltipSide | null;
  isQuest: boolean;
};

export function spawnTooltipSideAfterLayout(input: {
  current: TarkovMapTooltipSide;
  self: TarkovMapTooltipBox;
  others: readonly TarkovMapSiblingTooltip[];
  pointY: number;
  mapHeight: number;
  tooltipHeight: number;
}): TarkovMapTooltipSide {
  const quest = input.others.find(
    (row) => row.isQuest && tooltipBoxesOverlap(input.self, row.box),
  );
  if (!quest) return input.current;
  return pickTooltipVerticalSide({
    pointY: input.pointY,
    mapHeight: input.mapHeight,
    tooltipHeight: input.tooltipHeight,
    prefer: oppositeTooltipSide(quest.side ?? "top"),
  });
}

export function siblingMapTooltips(
  pane: Element | undefined | null,
  self: Element,
): TarkovMapSiblingTooltip[] {
  if (!pane) return [];
  const rows: TarkovMapSiblingTooltip[] = [];
  for (const node of pane.querySelectorAll(".leaflet-tooltip")) {
    if (node === self || !(node instanceof HTMLElement) || !node.offsetWidth) {
      continue;
    }
    const rect = node.getBoundingClientRect();
    rows.push({
      box: {
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
      },
      side: tooltipSideFromClassName(node.className),
      isQuest: node.classList.contains(TARKOV_MAP_TIP_QUEST),
    });
  }
  return rows;
}
