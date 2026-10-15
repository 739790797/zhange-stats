import type { components } from "@/api/generated/schema";
import { client } from "@/api/http";

export type Ror2Catalog = components["schemas"]["Ror2CatalogOut"];
export type Ror2Item = components["schemas"]["Ror2ItemOut"];
export type Ror2Survivor = components["schemas"]["Ror2SurvivorOut"];
export type Ror2Stat = components["schemas"]["Ror2StatOut"];

export async function fetchRor2Catalog() {
  const { data } = await client.get<Ror2Catalog>("/guides/ror2/catalog", {
    timeout: 60_000,
  });
  return data;
}
