import type { components } from "@/shared/api/generated/schema";
import { client } from "@/shared/api/http";

export type Ror2TextOut = components["schemas"]["Ror2TextOut"];
export type Ror2ApiCatalog = components["schemas"]["Ror2CatalogResponse"];
export type Ror2ApiItem = components["schemas"]["Ror2ItemResponse"];
export type Ror2ApiSurvivor = components["schemas"]["Ror2SurvivorResponse"];
export type Ror2Item = Omit<
  FlattenTextFields<Ror2ApiItem, "name" | "rarity" | "quote" | "description" | "unlock" | "lore">,
  "stats"
> & { stats: Ror2Stat[] };
export type Ror2Survivor = FlattenTextFields<
  Ror2ApiSurvivor,
  "name" | "umbra" | "description" | "unlock" | "phrase_escape" | "phrase_vanish"
>;
export type Ror2Monster = FlattenTextFields<components["schemas"]["Ror2MonsterResponse"], "name" | "boss_name">;
export type Ror2Drone = FlattenTextFields<components["schemas"]["Ror2DroneResponse"], "name" | "quote" | "description">;
export type Ror2Environment = FlattenTextFields<
  components["schemas"]["Ror2EnvironmentResponse"],
  "name" | "subtitle" | "description"
>;
export type Ror2Challenge = Omit<
  FlattenTextFields<components["schemas"]["Ror2ChallengeResponse"], "name" | "description">,
  "unlock"
> & {
  unlock: string[];
  unlock_zh: string[];
  localizedText: { name: Ror2TextOut; description: Ror2TextOut; unlock: Ror2TextOut[] };
};
export type Ror2Interactable = FlattenTextFields<
  components["schemas"]["Ror2InteractableResponse"],
  "name" | "effect"
>;
export type Ror2Artifact = FlattenTextFields<
  components["schemas"]["Ror2ArtifactResponse"],
  "name" | "description" | "unlock"
>;
export type Ror2Catalog = Omit<
  Ror2ApiCatalog,
  "items" | "equipment" | "survivors" | "monsters" | "drones" | "environments" | "challenges" | "interactables" | "artifacts"
> & {
  items: Ror2Item[];
  equipment: Ror2Item[];
  survivors: Ror2Survivor[];
  monsters: Ror2Monster[];
  drones: Ror2Drone[];
  environments: Ror2Environment[];
  challenges: Ror2Challenge[];
  interactables: Ror2Interactable[];
  artifacts: Ror2Artifact[];
};
export type Ror2SurvivorDetail = components["schemas"]["Ror2SurvivorDetailResponse"];
export type Ror2WikiBlock = components["schemas"]["Ror2WikiBlockResponse"];
export type Ror2WikiItem = components["schemas"]["Ror2WikiItemResponse"];
export type Ror2WikiArticle = components["schemas"]["Ror2WikiArticleOut"];
export type Ror2GalleryImage = components["schemas"]["Ror2GalleryImageResponse"];
export type Ror2Stat = FlattenTextFields<components["schemas"]["Ror2StatResponse"], "stack">;

type FlatTextMeta<K extends string> = {
  localizedText: Record<K, Ror2TextOut>;
  name_zh?: string;
  rarity_zh?: string;
  stack_zh?: string;
  quote_zh?: string;
  description_zh?: string;
  lore_zh?: string;
  unlock_zh?: string;
  umbra_zh?: string;
  subtitle_zh?: string;
  effect_zh?: string;
  boss_name_zh?: string;
  phrase_escape_zh?: string;
  phrase_vanish_zh?: string;
};
type FlattenTextFields<T, K extends keyof T & string> = Omit<T, K> & Record<K, string> & FlatTextMeta<K>;

function flattenTextFields<T extends Record<K, Ror2TextOut>, K extends string>(
  row: T,
  keys: readonly K[],
): FlattenTextFields<T, K> {
  const result: Record<string, unknown> = { ...row, localizedText: {} };
  const localizedText: Record<string, Ror2TextOut> = {};
  for (const key of keys) {
    const value = row[key];
    result[key] = value.original;
    result[`${key}_zh`] = value.text;
    localizedText[key] = value;
  }
  result.localizedText = localizedText;
  return result as FlattenTextFields<T, K>;
}

function adaptItem(row: Ror2ApiItem): Ror2Item {
  const base = flattenTextFields(row, ["name", "rarity", "quote", "description", "unlock", "lore"] as const);
  return {
    ...base,
    stats: (row.stats ?? []).map((stat) => flattenTextFields(stat, ["stack"] as const)),
  } as Ror2Item;
}

function flattenChallenge(row: components["schemas"]["Ror2ChallengeResponse"]): Ror2Challenge {
  const base = flattenTextFields(row, ["name", "description"] as const);
  const unlock = row.unlock ?? [];
  return {
    ...base,
    unlock: unlock.map((value) => value.original),
    unlock_zh: unlock.map((value) => value.text),
    localizedText: { ...base.localizedText, unlock },
  } as Ror2Challenge;
}

function adaptCatalog(catalog: Ror2ApiCatalog): Ror2Catalog {
  return {
    ...catalog,
    items: catalog.items.map(adaptItem),
    equipment: catalog.equipment.map(adaptItem),
    survivors: catalog.survivors.map((row) =>
      flattenTextFields(row, ["name", "umbra", "description", "unlock", "phrase_escape", "phrase_vanish"] as const),
    ),
    monsters: (catalog.monsters ?? []).map((row) => flattenTextFields(row, ["name", "boss_name"] as const)),
    drones: (catalog.drones ?? []).map((row) => flattenTextFields(row, ["name", "quote", "description"] as const)),
    environments: (catalog.environments ?? []).map((row) =>
      flattenTextFields(row, ["name", "subtitle", "description"] as const),
    ),
    challenges: (catalog.challenges ?? []).map(flattenChallenge),
    interactables: (catalog.interactables ?? []).map((row) => flattenTextFields(row, ["name", "effect"] as const)),
    artifacts: (catalog.artifacts ?? []).map((row) => flattenTextFields(row, ["name", "description", "unlock"] as const)),
  };
}

export async function fetchRor2Catalog() {
  const { data } = await client.get<Ror2ApiCatalog>("/guides/ror2/catalog", {
    timeout: 60_000,
  });
  return adaptCatalog(data);
}

export async function fetchRor2Survivor(name: string) {
  const { data } = await client.get<Ror2SurvivorDetail>(
    `/guides/ror2/survivors/${encodeURIComponent(name)}`,
    { timeout: 60_000 },
  );
  return data;
}
