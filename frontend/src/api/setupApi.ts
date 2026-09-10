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

export async function completeSetupDatabase(payload: SetupDatabaseRequest) {
  const { data } = await client.post<SetupDatabaseResult>(
    "/setup/database",
    payload,
  );
  return data;
}

export async function completeSetupAdmin(payload: SetupAdminRequest) {
  const { data } = await client.post<SetupAdminResult>("/setup/admin", payload);
  return data;
}
