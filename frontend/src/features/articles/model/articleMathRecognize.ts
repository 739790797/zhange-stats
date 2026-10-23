export const MATH_RECOGNIZE_MAX_BYTES = 2 * 1024 * 1024;
export const MATH_RECOGNIZE_ACCEPT = "image/png,image/jpeg,image/webp,image/gif";

export function rejectMathRecognizeFile(file: { size: number; type?: string }): string | null {
  if (!file.size) return "文件为空";
  if (file.size > MATH_RECOGNIZE_MAX_BYTES) return "识别图片不能超过 2MB";
  const type = (file.type || "").toLowerCase();
  if (type && !type.startsWith("image/")) return "请上传公式图片";
  return null;
}

/** RGBA：近白当空白，灰色笔画算有内容。 */
export function isNearWhiteCanvas(
  data: ArrayLike<number>,
  whiteMin = 250,
): boolean {
  if (data.length < 4) return true;
  for (let i = 0; i < data.length; i += 4) {
    const alpha = data[i + 3] ?? 255;
    if (alpha < 8) continue;
    const red = data[i] ?? 255;
    const green = data[i + 1] ?? 255;
    const blue = data[i + 2] ?? 255;
    if (red < whiteMin || green < whiteMin || blue < whiteMin) return false;
  }
  return true;
}
