import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export type PlatformFeatureNode = components["schemas"]["PlatformFeatureNodeOut"];

export type PlatformFeaturesResponse = components["schemas"]["PlatformFeaturesOut"];

export type PlatformFeaturesUpdate = components["schemas"]["PlatformFeaturesUpdate"];

export async function fetchPlatformFeaturesEffective() {
  const { data } = await client.get<Record<string, boolean>>(
    "/settings/platform-features/effective",
  );
  return data;
}

export async function fetchPlatformFeaturesAdmin() {
  const { data } = await client.get<PlatformFeaturesResponse>(
    "/settings/platform-features",
  );
  return data;
}

export async function updatePlatformFeatures(
  payload: PlatformFeaturesUpdate,
) {
  const { data } = await client.put<PlatformFeaturesResponse>(
    "/settings/platform-features",
    payload,
  );
  return data;
}
