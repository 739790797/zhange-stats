import { describe, expect, it } from "vitest";
import { pickTavernHighlights } from "./tavernHome";
import type { ArticleListItem } from "@/api/articlesApi";

function item(partial: Partial<ArticleListItem> & Pick<ArticleListItem, "id" | "slug" | "title">): ArticleListItem {
  return {
    summary: "",
    cover_url: null,
    status: "published",
    published_at: null,
    created_at: "2026-09-07T00:00:00",
    updated_at: "2026-09-07T00:00:00",
    comment_count: 0,
    author: { user_id: 1, display_name: "ann", avatar_url: null },
    categories: [],
    tags: [],
    ...partial,
  };
}

describe("pickTavernHighlights", () => {
  it("pins welcome then fills from latest without duplicates", () => {
    const welcome = item({ id: 1, slug: "welcome", title: "欢迎来到战鸽酒馆" });
    const a = item({ id: 2, slug: "a", title: "A" });
    const b = item({ id: 3, slug: "b", title: "B" });
    const picked = pickTavernHighlights([welcome, a, b], welcome, 2);
    expect(picked.map((row) => row.slug)).toEqual(["welcome", "a"]);
  });
});
