import { client } from "./http";
import type { components } from "./generated/schema";

export type RuntimeLogLine = components["schemas"]["RuntimeLogLineOut"];
export type RuntimeLogsResult = components["schemas"]["RuntimeLogsOut"];
export type RuntimeLogsClearResult = components["schemas"]["RuntimeLogsClearOut"];

export type FetchRuntimeLogsParams = {
  limit?: number;
  level?: string | null;
  logger?: string | null;
  q?: string | null;
  after_id?: number;
};

export async function fetchRuntimeLogs(params: FetchRuntimeLogsParams = {}) {
  const { data } = await client.get<RuntimeLogsResult>("/settings/runtime-logs", {
    params: {
      limit: params.limit ?? 300,
      level: params.level || undefined,
      logger: params.logger || undefined,
      q: params.q || undefined,
      after_id: params.after_id ?? 0,
    },
  });
  return data;
}

export async function clearRuntimeLogs() {
  const { data } = await client.post<RuntimeLogsClearResult>(
    "/settings/runtime-logs/clear",
  );
  return data;
}
