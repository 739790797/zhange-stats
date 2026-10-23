import { describe, expect, it } from "vitest";
import { escapeHtml } from "./escapeHtml";

describe("escapeHtml", () => {
  it("neutralizes tags, attribute quotes and entities", () => {
    expect(escapeHtml(`<img src=x onerror=alert(1)>`)).toBe(
      "&lt;img src=x onerror=alert(1)&gt;",
    );
    expect(escapeHtml(`a"b'c&d`)).toBe("a&quot;b&#39;c&amp;d");
    expect(escapeHtml("&lt;")).toBe("&amp;lt;");
  });

  it("keeps plain text and tolerates empty input", () => {
    expect(escapeHtml("队友 · 集合点")).toBe("队友 · 集合点");
    expect(escapeHtml("")).toBe("");
    expect(escapeHtml(null)).toBe("");
    expect(escapeHtml(undefined)).toBe("");
  });
});
