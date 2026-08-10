import { client } from "./http";
import type { components } from "./generated/schema";

export type RuntimeHealthResult = components["schemas"]["RuntimeHealthOut"];
export type RuntimeHealthService = components["schemas"]["RuntimeHealthServiceOut"];

export async function fetchRuntimeHealth() {
  const { data } = await client.get<RuntimeHealthResult>("/settings/runtime-health");
  return data;
}
