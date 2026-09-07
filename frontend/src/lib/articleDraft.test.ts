import {
  ARTICLE_AUTOSAVE_MS,
  UNTITLED_DRAFT_TITLE,
  articleDraftIsDirty,
  articleDraftSnapshot,
  articleDraftsEqual,
  articleEditorFormValues,
  autosaveTitle,
  autosaveWriteStatus,
  canAutosaveDraft,
} from "./articleDraft";
import { describe, expect, it } from "vitest";

describe("articleDraft", () => {
  it("normalizes ids and blank fields", () => {
    const snap = articleDraftSnapshot({
      title: "  Hello  ",
      category_ids: [3, 1],
      tags: [{ id: 9 }],
      body_format: null,
    });
    expect(snap.title).toBe("Hello");
    expect(snap.category_ids).toEqual([1, 3]);
    expect(snap.tag_ids).toEqual([9]);
    expect(snap.body_format).toBe("html");
    expect(ARTICLE_AUTOSAVE_MS).toBeGreaterThan(0);
  });

  it("compares snapshots and emptiness", () => {
    const a = articleDraftSnapshot({ title: "A", body: "x", tag_ids: [2, 1] });
    const b = articleDraftSnapshot({ title: "A", body: "x", tag_ids: [1, 2] });
    const c = articleDraftSnapshot({ title: "A", body: "y" });
    expect(articleDraftsEqual(a, b)).toBe(true);
    expect(articleDraftsEqual(a, c)).toBe(false);
    expect(canAutosaveDraft(articleDraftSnapshot({}))).toBe(false);
    expect(canAutosaveDraft(articleDraftSnapshot({ body: "  hi  " }))).toBe(
      true,
    );
  });

  it("fills untitled drafts", () => {
    expect(autosaveTitle("  ")).toBe(UNTITLED_DRAFT_TITLE);
    expect(autosaveTitle("标题")).toBe("标题");
  });

  it("keeps published articles published", () => {
    expect(autosaveWriteStatus("published")).toBe("published");
    expect(autosaveWriteStatus("draft")).toBe("draft");
    expect(autosaveWriteStatus(undefined)).toBe("draft");
  });

  it("hydrates editor form from a saved article", () => {
    const values = articleEditorFormValues({
      title: "TEST",
      slug: "test",
      summary: "摘要",
      body: "一段 **正文**",
      body_format: "markdown",
      status: "draft",
      categories: [{ id: 2 }],
      tags: [{ id: 8 }],
      cover_url: "/uploads/articles/a.png",
    });
    expect(values.title).toBe("TEST");
    expect(values.body_format).toBe("html");
    expect(values.body).toContain("<strong>");
    expect(values.body).toContain("正文");
    expect(values.status).toBe("draft");
    expect(values.category_ids).toEqual([2]);
    expect(values.tag_ids).toEqual([8]);
  });

  it("treats empty drafts as not dirty", () => {
    expect(articleDraftIsDirty(articleDraftSnapshot({}), null)).toBe(false);
    expect(
      articleDraftIsDirty(articleDraftSnapshot({ body: "x" }), null),
    ).toBe(true);
    const saved = articleDraftSnapshot({ title: "A", body: "x" });
    expect(articleDraftIsDirty(saved, saved)).toBe(false);
  });
});
