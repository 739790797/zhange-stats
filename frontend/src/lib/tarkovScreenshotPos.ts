/** 游戏内截图文件名里的战局坐标（Print Screen，不是系统截图）。 */

export type TarkovScreenshotPos = {
  x: number;
  y: number;
  z: number;
  yaw: number | null;
};

const HEAD_RE = /^(\d{4}-\d{2}-\d{2})\[(\d{1,2}-\d{2})\]_(.+)$/;
const NUM_RE = /-?\d+(?:\.\d+)?/g;

function parseNumberList(part: string): number[] {
  const matches = part.match(NUM_RE) || [];
  return matches.map((raw) => Number(raw)).filter((value) => Number.isFinite(value));
}

/**
 * Unity 四元数 → 水平朝向（度）。
 * 与 TarkovMonitor `QuarternionsToYaw` / Unity euler Y 一致：0 约等于 +Z。
 */
export function quaternionToYawDeg(
  x: number,
  y: number,
  z: number,
  w: number,
): number {
  const siny = 2 * (w * y + x * z);
  const cosy = 1 - 2 * (y * y + z * z);
  return (Math.atan2(siny, cosy) * 180) / Math.PI;
}

export function normalizeHeadingDeg(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

/** Unity 水平朝向：0 = +Z，正角转向 +X。 */
export function gameForwardXZ(yawDeg: number): { x: number; z: number } {
  const rad = (yawDeg * Math.PI) / 180;
  return { x: Math.sin(rad), z: Math.cos(rad) };
}

/**
 * 截图朝向经 CRS 投影后的屏幕角。
 * 0 朝上、顺时针为正。scaleY 与 `getCRS` 一样取负。
 */
export function gameYawToCssDeg(yaw: number, coordinateRotation = 0): number {
  const { x: gx, z: gz } = gameForwardXZ(yaw);
  const rot = ((coordinateRotation || 0) * Math.PI) / 180;
  const cos = Math.cos(rot);
  const sin = Math.sin(rot);
  const newLat = gx * sin + gz * cos;
  const newLng = gx * cos - gz * sin;
  return (Math.atan2(newLng, newLat) * 180) / Math.PI;
}

/** 屏幕两点 → 箭头角（Leaflet 层坐标：+x 右、+y 下）。 */
export function screenDeltaToCssDeg(dx: number, dy: number): number {
  return (Math.atan2(dx, -dy) * 180) / Math.PI;
}

/**
 * 截图朝向 → 地图箭头角度。与 tarkov.dev 一致，不按图再翻。
 */
export function screenshotYawToMapDeg(
  yaw: number,
  coordinateRotation = 0,
): number {
  return gameYawToCssDeg(yaw, coordinateRotation);
}

/** 尖头多边形，尖端就是朝向；不依赖 CSS `rotate`。 */
export function headingArrowPoints(
  cssDeg: number,
  cx = 16,
  cy = 16,
  len = 13,
  half = 6,
): string {
  const rad = (cssDeg * Math.PI) / 180;
  const ux = Math.sin(rad);
  const uy = -Math.cos(rad);
  const px = -uy;
  const py = ux;
  const tipX = cx + ux * len;
  const tipY = cy + uy * len;
  const leftX = cx - ux * 5 + px * half;
  const leftY = cy - uy * 5 + py * half;
  const rightX = cx - ux * 5 - px * half;
  const rightY = cy - uy * 5 - py * half;
  const fmt = (n: number) => n.toFixed(1);
  return `${fmt(tipX)},${fmt(tipY)} ${fmt(leftX)},${fmt(leftY)} ${fmt(rightX)},${fmt(rightY)}`;
}

/**
 * `2025-03-30[21-04]_175.30, 1.37, 150.68_-0.01, 0.98, -0.14, -0.10_9.53 (0).png`
 * 菜单/大厅截图通常只有时间，没有坐标。
 */
export function parseTarkovScreenshotName(
  fileName: string,
): TarkovScreenshotPos | null {
  const base = (fileName || "").replace(/\.(png|jpe?g|bmp|webp)$/i, "").trim();
  const head = HEAD_RE.exec(base);
  if (!head) return null;
  const rest = (head[3] || "").replace(/\s*\(\d+\)\s*$/, "");
  let xyz: number[] | null = null;
  let quat: number[] | null = null;
  for (const part of rest.split("_")) {
    const nums = parseNumberList(part);
    if (!xyz && nums.length >= 3) {
      xyz = nums.slice(0, 3);
      continue;
    }
    if (!quat && nums.length >= 4) {
      quat = nums.slice(0, 4);
    }
  }
  if (!xyz) return null;
  const [x, y, z] = xyz;
  return {
    x,
    y,
    z,
    yaw: quat
      ? quaternionToYawDeg(quat[0]!, quat[1]!, quat[2]!, quat[3]!)
      : null,
  };
}
