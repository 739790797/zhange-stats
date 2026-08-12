import { client } from "./http";
import type { components } from "./generated/schema";

export type TarkovAmmoCatalog = components["schemas"]["TarkovAmmoCatalogOut"];
export type TarkovAmmoItem = components["schemas"]["TarkovAmmoItemOut"];
export type TarkovAmmoSyncResult = components["schemas"]["TarkovAmmoSyncOut"];

export async function fetchTarkovAmmo() {
  const { data } = await client.get<TarkovAmmoCatalog>("/guides/tarkov/ammo", {
    timeout: 120_000,
  });
  return data;
}

export async function syncTarkovAmmo() {
  const { data } = await client.post<TarkovAmmoSyncResult>(
    "/guides/tarkov/ammo/sync",
    {},
    { timeout: 120_000 },
  );
  return data;
}
