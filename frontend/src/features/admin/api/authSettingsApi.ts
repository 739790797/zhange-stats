import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export type AuthSettings = components["schemas"]["AuthSettingsOut"];

export type AuthSettingsUpdate = components["schemas"]["AuthSettingsUpdate"];

export type AuthAdminBrief = components["schemas"]["AuthAdminBrief"];

export async function fetchAuthSettings(params?: { check_weak?: boolean }) {
  const { data } = await client.get<AuthSettings>("/settings/auth", {
    params: params?.check_weak ? { check_weak: true } : undefined,
  });
  return data;
}

export async function updateAuthSettings(payload: AuthSettingsUpdate) {
  const { data } = await client.put<AuthSettings>("/settings/auth", payload);
  return data;
}
