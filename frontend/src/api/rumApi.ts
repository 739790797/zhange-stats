import { client } from "./http";
import type { components } from "./generated/schema";

export type RumSummary = components["schemas"]["RumSummaryOut"];
export type RumSummaryRow = components["schemas"]["RumSummaryRowOut"];
export type RumBizSummary = components["schemas"]["RumBizSummaryOut"];

export async function fetchRumSummary(hours: number) {
  const { data } = await client.get<RumSummary>("/settings/rum", {
    params: { hours },
  });
  return data;
}
