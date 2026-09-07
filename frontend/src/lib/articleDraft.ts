import { articleToEditorHtml } from "./articleComposer";

export const ARTICLE_AUTOSAVE_MS = 4000;
export const UNTITLED_DRAFT_TITLE = "未命名";

export const EMPTY_ARTICLE_FORM = {
  title: "",
  slug: "",
  summary: "",
  body: "",
  body_format: "html" as const,
  status: "draft" as "draft" | "published",
  category_ids: [] as number[],
  tag_ids: [] as number[],
  cover_url: "",
};

export function articleEditorFormValues(initial: {
  title?: string | null;
  slug?: string | null;
  summary?: string | null;
  body?: string | null;
  body_format?: string | null;
  status?: string | null;
  cover_url?: string | null;
  categories?: { id: number }[] | null;
  tags?: { id: number }[] | null;
  category_ids?: number[] | null;
  tag_ids?: number[] | null;
}): typeof EMPTY_ARTICLE_FORM {
  return {
    title: initial.title || "",
    slug: initial.slug || "",
    summary: initial.summary || "",
    body: articleToEditorHtml(
      initial.body || "",
      initial.body_format === "markdown" ? "markdown" : "html",
    ),
    body_format: "html",
    status: initial.status === "published" ? "published" : "draft",
    category_ids:
      initial.category_ids ?? (initial.categories || []).map((row) => row.id),
    tag_ids: initial.tag_ids ?? (initial.tags || []).map((row) => row.id),
    cover_url: initial.cover_url || "",
  };
}

export type ArticleDraftSnapshot = {
  title: string;
  slug: string;
  summary: string;
  body: string;
  body_format: string;
  category_ids: number[];
  tag_ids: number[];
  cover_url: string;
};

export function articleDraftSnapshot(input: {
  title?: string | null;
  slug?: string | null;
  summary?: string | null;
  body?: string | null;
  body_format?: string | null;
  category_ids?: number[] | null;
  tag_ids?: number[] | null;
  cover_url?: string | null;
  categories?: { id: number }[] | null;
  tags?: { id: number }[] | null;
}): ArticleDraftSnapshot {
  const categoryIds =
    input.category_ids ?? (input.categories || []).map((row) => row.id);
  const tagIds = input.tag_ids ?? (input.tags || []).map((row) => row.id);
  return {
    title: (input.title || "").trim(),
    slug: (input.slug || "").trim(),
    summary: input.summary || "",
    body: input.body || "",
    body_format: input.body_format || "html",
    category_ids: [...categoryIds].sort((a, b) => a - b),
    tag_ids: [...tagIds].sort((a, b) => a - b),
    cover_url: input.cover_url || "",
  };
}

export function articleDraftsEqual(
  left: ArticleDraftSnapshot,
  right: ArticleDraftSnapshot,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function canAutosaveDraft(snap: ArticleDraftSnapshot): boolean {
  return Boolean(snap.title || snap.body.trim());
}

export function articleDraftIsDirty(
  current: ArticleDraftSnapshot,
  saved: ArticleDraftSnapshot | null,
): boolean {
  if (!canAutosaveDraft(current)) return false;
  if (!saved) return true;
  return !articleDraftsEqual(current, saved);
}

export function autosaveTitle(title: string): string {
  return title.trim() || UNTITLED_DRAFT_TITLE;
}

export function autosaveWriteStatus(
  current: string | null | undefined,
): "draft" | "published" {
  return current === "published" ? "published" : "draft";
}
