import { client } from "./http";
import type { components } from "./generated/schema";

export type TarkovAmmoCatalog = components["schemas"]["TarkovAmmoCatalogOut"];
export type TarkovAmmoItem = components["schemas"]["TarkovAmmoItemOut"];
export type TarkovAmmoSyncResult = components["schemas"]["TarkovAmmoSyncOut"];
export type TarkovGunCatalog = components["schemas"]["TarkovGunCatalogOut"];
export type TarkovGunItem = components["schemas"]["TarkovGunItemOut"];
export type TarkovGunSyncResult = components["schemas"]["TarkovGunSyncOut"];
export type TarkovItemsSyncResult = components["schemas"]["TarkovItemsSyncOut"];

export async function syncTarkovItems() {
  const { data } = await client.post<TarkovItemsSyncResult>(
    "/guides/tarkov/items/sync",
    {},
    { timeout: 120_000 },
  );
  return data;
}

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

export async function fetchTarkovGuns() {
  const { data } = await client.get<TarkovGunCatalog>("/guides/tarkov/guns", {
    timeout: 120_000,
  });
  return data;
}

export async function syncTarkovGuns() {
  const { data } = await client.post<TarkovGunSyncResult>(
    "/guides/tarkov/guns/sync",
    {},
    { timeout: 120_000 },
  );
  return data;
}
