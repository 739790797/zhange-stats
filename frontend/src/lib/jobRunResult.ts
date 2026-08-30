import { formatBeijing, parseBeijing } from "./time";

/** 任务配置手动执行：轮询 job_runs 并展示结果。 */

export type JobRunLike = {
  id: number;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  message?: string | null;
  stats?: Record<string, unknown> | null;
};

export type JobRunWatch = {
  jobId: string;
  jobName: string;
  sinceRunId: number;
  acceptedAt: number;
  acceptedMessage?: string;
};

export const JOB_RUN_WATCH_TIMEOUT_MS = 10 * 60 * 1000;
export const JOB_RUN_WATCH_POLL_MS = 1000;

const DOMAIN_LABELS: Record<string, string> = {
  dump: "整站 dump",
  items: "物品",
  tasks: "任务",
  maps: "地图 / BOSS",
  guides: "藏身处",
  hideout: "藏身处",
  traders: "商人",
  locks: "门锁",
  extras: "补集",
  barters: "交换",
  crafts: "制作",
};

const STAT_LABELS: Record<string, string> = {
  ok: "成功",
  failed: "失败",
  skipped: "跳过",
  total: "合计",
  members: "成员",
  playing: "游戏中",
  online: "在线",
  offline: "离线",
  opened: "开局",
  continued: "续局",
  closed: "收局",
};

export type JobRunDomainRow = {
  id: string;
  label: string;
  ok: boolean;
  error?: string;
  source?: string;
  mode?: string;
  syncedAt?: string;
  upstreamAt?: string;
};

export type ParsedJobRunMessage =
  | { kind: "text"; text: string }
  | {
      kind: "domains";
      okCount: number;
      failedCount: number;
      domains: JobRunDomainRow[];
    }
  | { kind: "json"; value: unknown };

export function isJobRunFinished(status: string | null | undefined): boolean {
  return status === "ok" || status === "error";
}

export function jobRunStatusLabel(status: string | null | undefined): string {
  if (status === "ok") return "成功";
  if (status === "error") return "失败";
  if (status === "running") return "执行中";
  return status || "未知";
}

export function jobRunAlertType(
  status: string | null | undefined,
): "success" | "error" | "info" | "warning" {
  if (status === "ok") return "success";
  if (status === "error") return "error";
  if (status === "running") return "info";
  return "warning";
}

export function jobRunDomainLabel(id: string, mode?: string | null): string {
  const raw = (id || "").trim();
  if (!raw) return "未命名";
  let label: string;
  if (raw.startsWith("dump:")) {
    label = `dump · ${jobRunDomainLabel(raw.slice(5))}`;
  } else {
    const zh = raw.endsWith("_zh");
    const base = zh ? raw.slice(0, -3) : raw;
    label = DOMAIN_LABELS[base] || base;
    if (zh) label = `${label}（中文）`;
  }
  const modeKey = (mode || "").trim().toLowerCase();
  if (modeKey === "pve") return `${label} · PVE`;
  if (modeKey === "pvp" || modeKey === "regular") return `${label} · PVP`;
  return label;
}

export function formatJobRunClock(iso?: string | null): string {
  if (!iso) return "";
  const text = formatBeijing(iso, "YYYY-MM-DD HH:mm");
  return text === "—" ? iso : text;
}

export function jobRunAgeLabel(
  iso?: string | null,
  nowMs?: number,
): string {
  if (!iso) return "";
  const d = parseBeijing(iso);
  if (!d.isValid()) return "";
  const diffMin = Math.round(((nowMs ?? Date.now()) - d.valueOf()) / 60_000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const hours = Math.round(diffMin / 60);
  if (hours < 48) return `${hours} 小时前`;
  return `${Math.round(hours / 24)} 天前`;
}

export function jobRunFreshnessText(
  row: Pick<JobRunDomainRow, "syncedAt" | "upstreamAt">,
  nowMs?: number,
): string {
  const parts: string[] = [];
  if (row.upstreamAt) {
    const age = jobRunAgeLabel(row.upstreamAt, nowMs);
    parts.push(
      age
        ? `上游 ${formatJobRunClock(row.upstreamAt)}（${age}）`
        : `上游 ${formatJobRunClock(row.upstreamAt)}`,
    );
  }
  if (row.syncedAt) {
    parts.push(`落库 ${formatJobRunClock(row.syncedAt)}`);
  }
  return parts.join(" · ");
}

export function jobRunFreshnessSummary(
  domains: JobRunDomainRow[],
  nowMs?: number,
): string | null {
  const stamps = domains
    .map((row) => row.upstreamAt)
    .filter((value): value is string => Boolean(value))
    .map((value) => ({ value, ms: parseBeijing(value).valueOf() }))
    .filter((row) => Number.isFinite(row.ms));
  if (!stamps.length) return null;
  const oldest = stamps.reduce((a, b) => (a.ms <= b.ms ? a : b));
  const newest = stamps.reduce((a, b) => (a.ms >= b.ms ? a : b));
  const age = jobRunAgeLabel(oldest.value, nowMs);
  if (oldest.ms === newest.ms) {
    return age
      ? `上游数据 ${formatJobRunClock(oldest.value)}（${age}）`
      : `上游数据 ${formatJobRunClock(oldest.value)}`;
  }
  return `上游 ${formatJobRunClock(oldest.value)} ～ ${formatJobRunClock(newest.value)}${age ? `（最早 ${age}）` : ""}`;
}

export function pickWatchedJobRun(
  items: JobRunLike[] | null | undefined,
  sinceRunId: number,
  acceptedAt?: number,
): JobRunLike | null {
  if (!items?.length) return null;
  return (
    items.find((row) => {
      if (row.id <= sinceRunId) return false;
      if (sinceRunId <= 0 && acceptedAt && row.started_at) {
        const started = Date.parse(row.started_at);
        if (!Number.isNaN(started) && started + 8000 < acceptedAt) return false;
      }
      return true;
    }) ?? null
  );
}

export function jobRunWatchPollMs(args: {
  run: JobRunLike | null;
  startedAt: number;
  now?: number;
  timeoutMs?: number;
}): number | false {
  if (args.run && isJobRunFinished(args.run.status)) return false;
  const now = args.now ?? Date.now();
  const timeout = args.timeoutMs ?? JOB_RUN_WATCH_TIMEOUT_MS;
  if (now - args.startedAt >= timeout) return false;
  return JOB_RUN_WATCH_POLL_MS;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function parseDomainRow(value: unknown): JobRunDomainRow | null {
  const row = asRecord(value);
  if (!row) return null;
  const id = String(row.id || "").trim();
  if (!id) return null;
  const error = row.error == null ? undefined : String(row.error);
  const source = row.source == null ? undefined : String(row.source);
  const mode = row.mode == null ? undefined : String(row.mode);
  const syncedAt = row.synced_at == null ? undefined : String(row.synced_at);
  const upstreamAt =
    row.upstream_at == null ? undefined : String(row.upstream_at);
  return {
    id,
    label: jobRunDomainLabel(id, mode),
    ok: row.ok === true,
    error,
    source,
    mode,
    syncedAt,
    upstreamAt,
  };
}

export function parseJobRunMessage(
  message: string | null | undefined,
): ParsedJobRunMessage | null {
  const raw = (message || "").trim();
  if (!raw) return null;
  if (raw.startsWith("{") || raw.startsWith("[")) {
    try {
      const value: unknown = JSON.parse(raw);
      const obj = asRecord(value);
      const domainsRaw = obj?.domains;
      if (obj && Array.isArray(domainsRaw)) {
        const domains = domainsRaw
          .map(parseDomainRow)
          .filter((row): row is JobRunDomainRow => Boolean(row));
        return {
          kind: "domains",
          okCount: Number(obj.ok_count ?? 0),
          failedCount: Number(obj.failed_count ?? 0),
          domains,
        };
      }
      return { kind: "json", value };
    } catch {
      return { kind: "text", text: raw };
    }
  }
  return { kind: "text", text: raw };
}

export function jobRunSummaryText(
  run: JobRunLike | null,
  acceptedMessage?: string,
): string {
  if (!run || run.status === "running") {
    return acceptedMessage || "已提交执行，正在运行…";
  }
  const parsed = parseJobRunMessage(run.message);
  if (parsed?.kind === "text") return parsed.text;
  if (parsed?.kind === "domains") {
    if (parsed.failedCount === 0) return `完成：成功 ${parsed.okCount} 项`;
    return `完成：成功 ${parsed.okCount} / 失败 ${parsed.failedCount}`;
  }
  if (run.message) return run.message;
  return run.status === "ok" ? "执行完成" : "执行失败";
}

export function jobRunStatEntries(
  stats: Record<string, unknown> | null | undefined,
): Array<{ key: string; label: string; value: string }> {
  if (!stats) return [];
  return Object.entries(stats)
    .filter(([, value]) => value != null && typeof value !== "object")
    .map(([key, value]) => ({
      key,
      label: STAT_LABELS[key] || key,
      value: String(value),
    }));
}
