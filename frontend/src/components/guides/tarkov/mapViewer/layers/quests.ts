/** 任务标点与标签：气泡、聚类标签、点位菜单弹窗。 */

import { escapeHtml } from "@/lib/escapeHtml";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import { pos } from "@/lib/tarkovMapCrs";
import {
  pickTooltipVerticalSide,
  TARKOV_MAP_TIP_QUEST,
  tooltipOffsetForSide,
} from "@/lib/tarkovMapTooltip";
import {
  clusterRaidPrepOverlayLabels,
  colorForTaskId,
  colorForUserId,
  formatRaidPrepOverlayKeyLabel,
  mapLayerFloorBands,
  overlayVisibleOnFloor,
  RAID_PREP_LABEL_CLUSTER_PX,
  RAID_PREP_QUEST_HELP_HINT,
  RAID_PREP_QUEST_HELP_LABEL,
  raidPrepQuestPaintColor,
  RAID_PREP_QUEST_POINT_ACTION_LABELS,
  RAID_PREP_QUEST_POINT_MENU_HINT,
  raidPrepParticipants,
  type RaidPrepHeightSpan,
  type RaidPrepMapParticipant,
  type RaidPrepOverlayLabelItem,
  type RaidPrepOverlayStep,
  type RaidPrepPoint,
  type RaidPrepQuestPointAction,
  type TarkovRaidPrepOverlay,
} from "@/lib/tarkovRaidPrep";
import { traderIconUrl, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import { fallbackImgHtml } from "@/lib/tarkovMapImgFallback";
import { RAID_ROOM_OTHER_FLOOR_OPACITY } from "@/lib/tarkovRaidRooms";
import styles from "../../TarkovMapViewer.module.css";

type QuestBubbleRow = {
  taskId?: string;
  objectiveId?: string;
  title: string;
  subtitle: string;
  steps?: RaidPrepOverlayStep[];
  color: string;
  traderSlug: string;
  keyNames?: string[];
  showNoKey?: boolean;
  optional?: boolean;
  kind?: "zone" | "spawn";
  height?: RaidPrepHeightSpan | null;
  at?: RaidPrepPoint;
  participants?: readonly RaidPrepMapParticipant[];
  done?: boolean;
};

function questParticipantChipsHtml(
  people: readonly RaidPrepMapParticipant[] | undefined,
  help = false,
): string {
  const list = raidPrepParticipants(people);
  if (!list.length) return "";
  const chips = list
    .map((person) => {
      const color =
        person.userId != null
          ? colorForUserId(person.userId)
          : colorForTaskId(person.name);
      return `<span class="${styles.questTipChip}"><span class="${styles.questTipDot}" style="background:${escapeHtml(color)}"></span>${escapeHtml(person.name)}</span>`;
    })
    .join("");
  const lead = help
    ? `<span class="${styles.questTipPeopleLead}">还需</span>`
    : "";
  return `<span class="${styles.questTipPeople}">${lead}${chips}</span>`;
}

function overlayBubbleStepsHtml(row: QuestBubbleRow): string {
  const steps =
    row.steps && row.steps.length
      ? row.steps
      : row.subtitle
        ? [{ text: row.subtitle, active: true }]
        : row.kind === "spawn"
          ? [{ text: "可能刷新点", active: true }]
          : row.kind === "zone"
            ? [{ text: "目标区域", active: true }]
            : [];
  if (!steps.length) return "";
  return `<span class="${styles.questTipSteps}">${steps
    .map((step) => {
      const on = step.active ? ` ${styles.questTipStepOn}` : "";
      const color = step.active
        ? ` style="color:${escapeHtml(raidPrepQuestPaintColor(row.color, row.done))}"`
        : "";
      return `<span class="${styles.questTipStep}${on}"${color}>${escapeHtml(step.text)}</span>`;
    })
    .join("")}</span>`;
}

export function overlayBubbleHtml(
  row: QuestBubbleRow,
  extras?: { hint?: string; actions?: readonly RaidPrepQuestPointAction[] },
): string {
  const keys = (row.keyNames || [])
    .filter(Boolean)
    .map(
      (name) =>
        `<span class="${styles.questTipKey}">${escapeHtml(name)}</span>`,
    )
    .join("");
  const keyRow = keys
    ? `<span class="${styles.questTipKeys}"><span class="${styles.questTipKeyLabel}">所需钥匙</span>${keys}</span>`
    : "";
  const hint = extras?.hint
    ? `<span class="${styles.questTipHint}">${escapeHtml(extras.hint)}</span>`
    : "";
  const help = row.done
    ? `<span class="${styles.questTipHelp}">${escapeHtml(RAID_PREP_QUEST_HELP_HINT)}</span>`
    : "";
  const actions = extras?.actions?.length
    ? `<span class="${styles.questTipActions}">${extras.actions
        .map(
          (id) =>
            `<button type="button" class="${styles.questTipAction}" data-quest-action="${escapeHtml(id)}">${escapeHtml(RAID_PREP_QUEST_POINT_ACTION_LABELS[id])}</button>`,
        )
        .join("")}</span>`
    : "";
  const paint = raidPrepQuestPaintColor(row.color, row.done);
  return `<span class="${styles.questTip}"><span class="${styles.questTipRow}">${questTraderImgHtml(row.traderSlug)}<span class="${styles.questTipName}" style="color:${paint}">${escapeHtml(row.title)}</span></span>${overlayBubbleStepsHtml(row)}${keyRow}${help}${questParticipantChipsHtml(row.participants, Boolean(row.done))}${hint}${actions}</span>`;
}

function traderSlugForIcon(slug: string): string {
  return slug.trim().toLowerCase().replace(/[^a-z0-9-]/g, "");
}

function questTraderImgHtml(slug: string): string {
  const safe = traderSlugForIcon(slug);
  if (!safe) return "";
  return fallbackImgHtml({
    className: styles.questTrader,
    src: traderIconUrl(safe),
    fallbackSrc: traderPortraitUrl(safe),
    size: 20,
  });
}

function questLabelLineHtml(
  item: RaidPrepOverlayLabelItem,
  offFloor = false,
  done = false,
): string {
  const title = item.optional ? `${item.title}（可选）` : item.title;
  const keyMark = item.keyNames.length
    ? `<span class="${styles.questLabelKey}">${escapeHtml(formatRaidPrepOverlayKeyLabel(item.keyNames, item.showNoKey) || "钥匙")}</span>`
    : "";
  const help = done
    ? `<span class="${styles.questLabelHelp}">${escapeHtml(RAID_PREP_QUEST_HELP_LABEL)}</span>`
    : "";
  const paint = raidPrepQuestPaintColor(item.color, done);
  const dim = offFloor ? ` ${styles.questLabelOff}` : "";
  return `<span class="${styles.questLabelRow}${dim}" data-task-id="${escapeHtml(item.taskId)}">${questTraderImgHtml(item.traderSlug)}<span class="${styles.questName}" style="color:${paint}">${escapeHtml(title)}</span>${help}${keyMark}</span>`;
}

export function applyQuestLabelHighlight(
  root: HTMLElement | undefined,
  highlightTaskId: string,
) {
  if (!root) return;
  const on = (highlightTaskId || "").trim();
  for (const node of root.querySelectorAll<HTMLElement>("[data-task-id]")) {
    const id = node.getAttribute("data-task-id") || "";
    if (on && id === on) node.setAttribute("data-on", "true");
    else node.removeAttribute("data-on");
  }
}

function overlayByLabelItem(
  overlays: TarkovRaidPrepOverlay[],
): Map<string, TarkovRaidPrepOverlay> {
  const map = new Map<string, TarkovRaidPrepOverlay>();
  for (const row of overlays) {
    const key = `${row.taskId}\0${row.optional ? "1" : "0"}\0${row.title}`;
    if (!map.has(key)) map.set(key, row);
  }
  return map;
}

type QuestClickTarget = {
  row: QuestBubbleRow;
  latlng: L.LatLng;
  layer: L.Layer;
};

export type QuestClickHandler = (target: QuestClickTarget) => boolean | void;

export function leafletLayerMap(layer: L.Layer): L.Map | undefined {
  return (layer as L.Layer & { _map?: L.Map })._map;
}

export function bindQuestActionPopup(
  map: L.Map,
  latlng: L.LatLng,
  html: string,
  onAction: (action: RaidPrepQuestPointAction) => void,
) {
  const popup = L.popup({
    className: TARKOV_MAP_TIP_QUEST,
    closeButton: true,
    autoPan: true,
    maxWidth: 360,
    offset: L.point(0, -8),
  })
    .setLatLng(latlng)
    .setContent(html);
  popup.openOn(map);
  const root = popup.getElement();
  if (!root) return;
  L.DomEvent.disableClickPropagation(root);
  L.DomEvent.disableScrollPropagation(root);
  const onClick = (event: Event) => {
    const btn = (event.target as HTMLElement | null)?.closest(
      "[data-quest-action]",
    );
    if (!btn) return;
    L.DomEvent.stop(event);
    const action = btn.getAttribute("data-quest-action");
    if (
      action !== "guide" &&
      action !== "complete" &&
      action !== "uncomplete"
    ) {
      return;
    }
    map.closePopup(popup);
    onAction(action);
  };
  root.addEventListener("click", onClick);
  popup.once("remove", () => root.removeEventListener("click", onClick));
}

function bindQuestBubble(
  layer: L.Layer,
  row: QuestBubbleRow,
  onClick?: QuestClickHandler,
  menuHint = false,
) {
  const html = overlayBubbleHtml(
    row,
    menuHint ? { hint: RAID_PREP_QUEST_POINT_MENU_HINT } : undefined,
  );
  layer.bindTooltip(html, {
    direction: "top",
    opacity: 1,
    sticky: true,
    className: `${styles.questTooltip} ${TARKOV_MAP_TIP_QUEST}`,
  });
  layer.on("tooltipopen", (event: L.TooltipEvent) => {
    const map = leafletLayerMap(layer);
    const tip = event.tooltip;
    if (!map || !tip) return;
    const place = () => {
      const latlng = tip.getLatLng();
      if (!latlng) return;
      const height = tip.getElement()?.offsetHeight || 96;
      const point = map.latLngToContainerPoint(latlng);
      const side = pickTooltipVerticalSide({
        pointY: point.y,
        mapHeight: map.getSize().y,
        tooltipHeight: height,
      });
      tip.options.direction = side;
      const [ox, oy] = tooltipOffsetForSide(side, 12);
      tip.options.offset = L.point(ox, oy);
      tip.update();
    };
    place();
    window.requestAnimationFrame(place);
  });
  const taskId = (row.taskId || "").trim();
  if (!onClick || !taskId) return;
  layer.on("click", (event: L.LeafletMouseEvent) => {
    const handled = onClick({
      row,
      latlng: event.latlng,
      layer,
    });
    if (handled === false) return;
    L.DomEvent.stopPropagation(event);
  });
}

function overlayFloorAt(
  row: { points?: RaidPrepPoint[]; outline?: RaidPrepPoint[] } | null | undefined,
): RaidPrepPoint | undefined {
  return row?.points?.[0] || row?.outline?.[0];
}

function questBubbleFromOverlay(
  row: TarkovRaidPrepOverlay,
  namesByTask?: ReadonlyMap<string, readonly RaidPrepMapParticipant[]>,
): QuestBubbleRow {
  return {
    taskId: row.taskId,
    objectiveId: row.objectiveId,
    title: row.title,
    subtitle: row.subtitle,
    steps: row.steps,
    color: row.color,
    traderSlug: row.traderSlug,
    keyNames: row.keyNames,
    showNoKey: row.showNoKey,
    optional: row.optional,
    kind: row.kind,
    height: row.height,
    at: overlayFloorAt(row),
    participants: row.neededBy
      ? raidPrepParticipants(row.neededBy)
      : raidPrepParticipants(namesByTask?.get(row.taskId)),
    done: Boolean(row.done),
  };
}

export function addQuestOverlays(
  group: L.LayerGroup,
  overlays: TarkovRaidPrepOverlay[],
  namesByTask: ReadonlyMap<string, readonly RaidPrepMapParticipant[]> | undefined,
  onClick: QuestClickHandler | undefined,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  menuHint = false,
) {
  group.clearLayers();
  for (const row of overlays) {
    const bubble = questBubbleFromOverlay(row, namesByTask);
    const onFloor = overlayVisibleOnFloor(
      row.height,
      floor,
      floorBands,
      overlayFloorAt(row),
    );
    const fade = onFloor ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY;
    const dashed = row.optional || row.done;
    const paint = raidPrepQuestPaintColor(row.color, row.done);
    if (row.outline.length >= 3) {
      const polygon = L.polygon(
        row.outline.map((point) => pos({ x: point.x, z: point.z })),
        {
          color: paint,
          weight: 2,
          dashArray: dashed ? "5 4" : undefined,
          fillColor: paint,
          opacity: fade,
          fillOpacity: (row.optional ? 0.1 : 0.18) * fade,
          className: styles.questHit,
        },
      );
      bindQuestBubble(polygon, bubble, onClick, menuHint);
      polygon.addTo(group);
    }
    for (const point of row.points) {
      const marker = L.circleMarker(pos({ x: point.x, z: point.z }), {
        radius: row.kind === "spawn" ? 5 : 7,
        color: "#111",
        weight: 1,
        dashArray: dashed ? "3 2" : undefined,
        fillColor: paint,
        opacity: fade,
        fillOpacity: (row.optional ? 0.55 : 0.92) * fade,
        className: styles.questHit,
      });
      bindQuestBubble(marker, bubble, onClick, menuHint);
      marker.addTo(group);
    }
  }
}

/** Leaflet 在首次 setView/fitBounds 前调用 latLngToLayerPoint 会抛错。 */
export function isLeafletViewReady(map: L.Map): boolean {
  return Boolean((map as unknown as { _loaded?: boolean })._loaded);
}

function questLabelProject(map: L.Map) {
  return (point: { x: number; z: number }) => {
    const layer = map.latLngToLayerPoint(L.latLng(pos(point)));
    return { x: layer.x, z: layer.y };
  };
}

export function addQuestLabels(
  group: L.LayerGroup,
  overlays: TarkovRaidPrepOverlay[],
  map: L.Map,
  onLabelClick: QuestClickHandler | undefined,
  namesByTask: ReadonlyMap<string, readonly RaidPrepMapParticipant[]> | undefined,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  menuHint = false,
) {
  group.clearLayers();
  /* 抽象图 SVG 异步加载期间 map 已创建但尚未 fitBounds，此时投影会白屏 */
  if (!isLeafletViewReady(map)) return;
  const labels = clusterRaidPrepOverlayLabels(overlays, {
    gap: RAID_PREP_LABEL_CLUSTER_PX,
    project: questLabelProject(map),
  });
  const byItem = overlayByLabelItem(overlays);
  const lineH = 22;
  for (const label of labels) {
    label.items.forEach((item, index) => {
      const source = byItem.get(
        `${item.taskId}\0${item.optional ? "1" : "0"}\0${item.title}`,
      );
      const at = overlayFloorAt(source) || { x: label.x, z: label.z };
      const offFloor = !overlayVisibleOnFloor(
        item.height,
        floor,
        floorBands,
        at,
      );
      const marker = L.marker(pos({ x: label.x, z: label.z }), {
        icon: L.divIcon({
          className: styles.questIcon,
          html: `<span class="${styles.questLabelStack}">${questLabelLineHtml(item, offFloor, Boolean(item.done || source?.done))}</span>`,
          iconSize: [1, 1],
          iconAnchor: [0, -index * lineH],
        }),
        interactive: true,
        keyboard: false,
        bubblingMouseEvents: false,
      });
      bindQuestBubble(
        marker,
        {
          taskId: item.taskId,
          objectiveId: source?.objectiveId,
          title: item.title,
          subtitle: source?.subtitle || item.subtitle,
          steps: source?.steps,
          color: item.color,
          traderSlug: item.traderSlug,
          keyNames: item.keyNames,
          showNoKey: item.showNoKey,
          optional: item.optional,
          height: item.height,
          at,
          participants: raidPrepParticipants(
            source?.neededBy ?? namesByTask?.get(item.taskId),
          ),
          done: Boolean(source?.done ?? item.done),
        },
        onLabelClick,
        menuHint,
      );
      marker.addTo(group);
    });
  }
}
