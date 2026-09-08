/** 钥匙箱识别 NDJSON：解析进度行，不负责画 UI。 */

export type KeyOcrProgress = {
  message: string;
  percent: number;
  phase?: string;
};

export type KeyOcrStreamEvent =
  | { event: "progress"; message: string; percent: number; phase?: string }
  | { event: "done"; result: Record<string, unknown> }
  | { event: "error"; status_code: number; detail: string };

export function parseKeyOcrNdjsonLine(line: string): KeyOcrStreamEvent | null {
  const raw = line.trim();
  if (!raw) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object") return null;
  const row = parsed as Record<string, unknown>;
  if (row.event === "progress") {
    return {
      event: "progress",
      message:
        typeof row.message === "string" && row.message.trim()
          ? row.message.trim()
          : "识别中…",
      percent: clampPercent(row.percent),
      phase: typeof row.phase === "string" ? row.phase : undefined,
    };
  }
  if (row.event === "done" && row.result && typeof row.result === "object") {
    return { event: "done", result: row.result as Record<string, unknown> };
  }
  if (row.event === "error") {
    const detail =
      typeof row.detail === "string" && row.detail.trim()
        ? row.detail.trim()
        : "识别失败，请重试";
    const status =
      typeof row.status_code === "number" && Number.isFinite(row.status_code)
        ? Math.round(row.status_code)
        : 500;
    return { event: "error", status_code: status, detail };
  }
  return null;
}

function clampPercent(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}
