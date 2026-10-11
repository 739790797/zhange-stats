import { client } from "./http";
import type { components } from "./generated/schema";

export type SetupStatus = components["schemas"]["SetupStatusOut"];
export type SetupAdminResult = components["schemas"]["SetupAdminResponse"];
export type SetupAdminRequest = components["schemas"]["SetupAdminRequest"];
export type SetupDatabaseRequest = {
  engine: "sqlite" | "mysql";
  url?: string;
};
export type SetupDatabaseResult = components["schemas"]["SetupDatabaseResponse"];

export async function fetchSetupStatus() {
  const { data } = await client.get<SetupStatus>("/setup/status");
  return data;
}

const SETUP_TOKEN_HEADER = "X-Setup-Token";

function setupTokenHeaders(token: string) {
  const value = token.trim();
  return value ? { [SETUP_TOKEN_HEADER]: value } : {};
}

export async function completeSetupDatabase(
  payload: SetupDatabaseRequest,
  token: string,
) {
  const { data } = await client.post<SetupDatabaseResult>(
    "/setup/database",
    payload,
    { headers: setupTokenHeaders(token) },
  );
  return data;
}

export async function completeSetupAdmin(payload: SetupAdminRequest, token: string) {
  const { data } = await client.post<SetupAdminResult>("/setup/admin", payload, {
    headers: setupTokenHeaders(token),
  });
  return data;
}
