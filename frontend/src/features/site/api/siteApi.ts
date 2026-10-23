import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export type SiteSettings = components["schemas"]["SiteSettingsOut"];

export type SiteSettingsUpdate = components["schemas"]["SiteSettingsUpdate"];

export async function fetchSitePublic() {
  const { data } = await client.get<SiteSettings>("/settings/site/public");
  return data;
}

export async function fetchSiteSettings() {
  const { data } = await client.get<SiteSettings>("/settings/site");
  return data;
}

export async function updateSiteSettings(payload: SiteSettingsUpdate) {
  const { data } = await client.put<SiteSettings>("/settings/site", payload);
  return data;
}
