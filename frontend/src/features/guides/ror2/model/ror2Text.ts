import type { Ror2TextOut } from "@/features/guides/ror2/api/ror2Api";

export type Ror2TextLike = Ror2TextOut | string | null | undefined;
export type Ror2ResolvedText = { text: string; original: string; token: string | null };

export function toRor2ResolvedText(value: Ror2TextLike): Ror2ResolvedText {
  if (typeof value === "string") return { text: value, original: value, token: null };
  if (!value) return { text: "", original: "", token: null };
  return { text: value.text, original: value.original, token: value.token || null };
}

export function ror2TextContent(value: Ror2TextLike): string {
  return toRor2ResolvedText(value).text;
}

/** Backward-compatible helper for local view-model fields. */
export function ror2ResolvedText(
  translation: Ror2TextLike,
  original?: string | null,
): string {
  if (typeof translation === "object" && translation !== null) return translation.text;
  return translation?.trim() ? translation : original ?? "";
}
