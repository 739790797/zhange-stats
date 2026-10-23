import type { Ror2TextOut, Ror2WikiArticle } from "@/features/guides/ror2/api/ror2Api";

export const ROR2_BASE_EXPANSION_LABEL = "雨中冒险2";

/** 玩家提供的官方简中译名；Wiki 英文标题仍由同步原文提供。 */
export const ROR2_EXPANSION_NAMES_ZH = {
  SotV: "虚空幸存者",
  SotS: "风暴探寻者",
  AC: "合金意念",
  HC: "神圣观念",
} as const;

export type Ror2KnownExpansionId = keyof typeof ROR2_EXPANSION_NAMES_ZH;

export const ROR2_EXPANSION_WIKI_TITLES: Record<Ror2KnownExpansionId, string> = {
  SotV: "Survivors of the Void",
  SotS: "Seekers of the Storm",
  AC: "Alloyed Collective",
  HC: "Hallowed Concepts",
};

/** Wiki internal/unfinished markers are not purchasable DLC sources. */
export const ROR2_INTERNAL_EXPANSION_IDS: ReadonlySet<string> = new Set(["Junk", "RoR2.Junk"]);

export function ror2ExpansionId(expansion?: string): string {
  return (expansion || "").trim() || "base";
}

export function isRor2KnownExpansion(id: string): id is Ror2KnownExpansionId {
  return Object.prototype.hasOwnProperty.call(ROR2_EXPANSION_NAMES_ZH, id);
}

export function ror2ExpansionName(id: string, fallback = ""): string {
  if (!id || id === "base") return ROR2_BASE_EXPANSION_LABEL;
  return ROR2_EXPANSION_NAMES_ZH[id as Ror2KnownExpansionId] ?? fallback;
}

export function ror2ExpansionWikiTitle(
  articles: readonly Ror2WikiArticle[] | undefined,
  id: string,
): Ror2TextOut | undefined {
  if (!isRor2KnownExpansion(id)) return undefined;
  return articles?.find((article) => article.id === `expansion:${id}`)?.title;
}
