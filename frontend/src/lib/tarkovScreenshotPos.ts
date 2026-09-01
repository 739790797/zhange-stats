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

/** Unity 四元数在 XZ 平面上的朝向（度，0 约等于 +Z）。 */
export function quaternionToYawDeg(
  x: number,
  y: number,
  z: number,
  w: number,
): number {
  const fx = 2 * (x * z + w * y);
  const fz = 1 - 2 * (x * x + y * y);
  return (Math.atan2(fx, fz) * 180) / Math.PI;
}

/**
 * 截图朝向 → 地图箭头 CSS 角度。`rotate(0)` 朝上、顺时针为正。
 * `coordinateRotation` 跟 CRS 一致；再加 180°：Y 轴翻转后箭头默认朝上会和战局相反。
 * 90°/270° 图因此也和 tarkov.dev 的补角一致。
 */
export function screenshotYawToMapDeg(
  yaw: number,
  coordinateRotation = 0,
): number {
  return yaw + (coordinateRotation || 0) + 180;
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
