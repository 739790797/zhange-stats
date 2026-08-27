/**
 * 选中高度层时地面底图透明度。
 * tarkov.dev 用 0.2；本站地图底是 #101010，过低会看起来像整片黑，略提高以便仍能看清道路和轮廓。
 */
export const MAP_OFF_LEVEL_OPACITY = 0.4;

export type SvgFloorGroupLike = {
  id: string;
  keepWithGroup?: string;
};

export type SvgFloorGroupClasses = {
  "base-layer": boolean;
  "overlay-layer": boolean;
  "hidden-layer": boolean;
};

export function isSvgBaseFloorGroup(
  group: SvgFloorGroupLike,
  baseId: string,
): boolean {
  if (!group.id || !baseId) return false;
  return group.id === baseId || group.keepWithGroup === baseId;
}

/**
 * 选中高度层时是否压暗地面。
 * `keepBaseOpaque` 对应 maps.json 的 `show: true`（如立交桥 2 层）：tarkov.dev 此时不降地面透明度。
 */
export function mapBaseOffLevel(
  selectedFloorId: string,
  keepBaseOpaque = false,
): boolean {
  return Boolean(selectedFloorId) && !keepBaseOpaque;
}

/**
 * SVG 分组 class：地面始终可见；其它楼层仅在被选中时显示。
 * 隐藏只作用在 overlay，避免地面被 `display:none` 掏成黑底。
 */
export function svgFloorGroupClasses(
  group: SvgFloorGroupLike,
  baseId: string,
  selectedFloorId: string,
): SvgFloorGroupClasses {
  if (isSvgBaseFloorGroup(group, baseId)) {
    return {
      "base-layer": true,
      "overlay-layer": false,
      "hidden-layer": false,
    };
  }
  return {
    "base-layer": false,
    "overlay-layer": true,
    "hidden-layer": group.id !== selectedFloorId,
  };
}
