import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export type IntegrationsSettings = components["schemas"]["IntegrationsOut"];

export type IntegrationsUpdate = components["schemas"]["IntegrationsUpdate"];

export type IntegrationsStatus = components["schemas"]["IntegrationsStatusOut"];

export type PelicanTestRequest = components["schemas"]["PelicanTestRequest"];

export type PelicanTestResponse = components["schemas"]["PelicanTestResponse"];

export type MinecraftRconTestRequest =
  components["schemas"]["MinecraftRconTestRequest"];

export type MinecraftRconTestResponse =
  components["schemas"]["MinecraftRconTestResponse"];

export async function fetchIntegrationsSettings() {
  const { data } = await client.get<IntegrationsSettings>(
    "/settings/integrations",
  );
  return data;
}

export async function fetchIntegrationsStatus() {
  const { data } = await client.get<IntegrationsStatus>(
    "/settings/integrations/status",
  );
  return data;
}

export async function updateIntegrationsSettings(
  payload: IntegrationsUpdate,
) {
  const { data } = await client.put<IntegrationsSettings>(
    "/settings/integrations",
    payload,
  );
  return data;
}

export async function testPelicanConnection(payload: PelicanTestRequest) {
  const { data } = await client.post<PelicanTestResponse>(
    "/settings/integrations/pelican-test",
    payload,
    { timeout: 15_000 },
  );
  return data;
}

export async function testMinecraftRconConnection(
  payload: MinecraftRconTestRequest,
) {
  const { data } = await client.post<MinecraftRconTestResponse>(
    "/settings/integrations/minecraft-rcon-test",
    payload,
    { timeout: 10_000 },
  );
  return data;
}
