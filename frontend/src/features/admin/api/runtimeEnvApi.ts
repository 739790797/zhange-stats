import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export type RuntimeEnvSettings = components["schemas"]["RuntimeEnvOut"];

export type RuntimeEnvUpdate = components["schemas"]["RuntimeEnvUpdate"];

export type RuntimeConnTestResponse = components["schemas"]["RuntimeConnTestOut"];

export type RuntimeDatabaseTestRequest =
  components["schemas"]["RuntimeDatabaseTestIn"];

export type RuntimeRedisTestRequest = components["schemas"]["RuntimeRedisTestIn"];

export async function fetchRuntimeEnv() {
  const { data } = await client.get<RuntimeEnvSettings>("/settings/runtime-env");
  return data;
}

export async function updateRuntimeEnv(
  payload: Omit<RuntimeEnvUpdate, "clear_redis_url"> & {
    clear_redis_url?: boolean;
  },
) {
  const { data } = await client.put<RuntimeEnvSettings>("/settings/runtime-env", {
    clear_redis_url: false,
    ...payload,
  });
  return data;
}

export async function testRuntimeDatabase(payload: RuntimeDatabaseTestRequest) {
  const { data } = await client.post<RuntimeConnTestResponse>(
    "/settings/runtime-env/database-test",
    payload,
    { timeout: 15_000 },
  );
  return data;
}

export async function testRuntimeRedis(payload: RuntimeRedisTestRequest) {
  const { data } = await client.post<RuntimeConnTestResponse>(
    "/settings/runtime-env/redis-test",
    payload,
    { timeout: 10_000 },
  );
  return data;
}
