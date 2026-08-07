import { client } from "./http";
import type { components } from "./generated/schema";

export type SetupStatus = components["schemas"]["SetupStatusOut"];
export type SetupAdminResult = components["schemas"]["SetupAdminResponse"];
export type SetupAdminRequest = components["schemas"]["SetupAdminRequest"];

export async function fetchSetupStatus() {
  const { data } = await client.get<SetupStatus>("/setup/status");
  return data;
}

export async function completeSetupAdmin(payload: SetupAdminRequest) {
  const { data } = await client.post<SetupAdminResult>("/setup/admin", payload);
  return data;
}
