import { describe, expect, it } from "vitest";
import {
  DEFAULT_ARTICLE_CATEGORY_CHIP,
  articleCategoryChipColor,
  articleCategoryChipHex,
  articleCategoryOptionLabel,
  selectableArticleCategories,
} from "./articleCategory";

describe("articleCategory", () => {
  it("uses custom hex or the default chip token", () => {
    expect(articleCategoryChipHex({ chip_color: "  #c41d7f  " })).toBe(
      "#c41d7f",
    );
    expect(articleCategoryChipHex({ chip_color: "" })).toBeUndefined();
    expect(articleCategoryChipColor({ chip_color: null })).toBe(
      DEFAULT_ARTICLE_CATEGORY_CHIP,
    );
    expect(articleCategoryChipColor({ chip_color: "#1677ff" })).toBe("#1677ff");
  });

  it("hides admin-only categories from authors", () => {
    const cats = [
      { id: 1, name: "站点公告", admin_only: true },
      { id: 2, name: "游戏攻略", admin_only: false },
    ];
    expect(selectableArticleCategories(cats, false).map((row) => row.id)).toEqual(
      [2],
    );
    expect(selectableArticleCategories(cats, true)).toEqual(cats);
  });

  it("marks admin-only options", () => {
    expect(articleCategoryOptionLabel({ name: "站点公告", admin_only: true })).toBe(
      "站点公告（仅管理员）",
    );
    expect(articleCategoryOptionLabel({ name: "游戏攻略" })).toBe("游戏攻略");
  });
});
