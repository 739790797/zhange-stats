import { client } from "./http";

export interface SetupStatus {
  needs_setup: boolean;
  min_password_length: number;
}

export interface SetupAdminResult {
  message: string;
  access_token: string;
  token_type: string;
}

export async function fetchSetupStatus() {
  const { data } = await client.get<SetupStatus>("/setup/status");
  return data;
}

export async function completeSetupAdmin(payload: {
  email: string;
  display_name: string;
  password: string;
}) {
  const { data } = await client.post<SetupAdminResult>("/setup/admin", payload);
  return data;
}
