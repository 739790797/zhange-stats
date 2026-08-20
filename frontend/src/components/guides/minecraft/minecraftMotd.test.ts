import { describe, expect, it } from "vitest";
import { motdColorOnLight, motdPlainText, parseMotdLines } from "./minecraftMotd";

describe("parseMotdLines", () => {
  it("splits color and format codes", () => {
    const lines = parseMotdLines("§aHello §lWorld");
    expect(lines).toHaveLength(1);
    expect(lines[0][0]).toMatchObject({ text: "Hello ", color: "#55ff55" });
    expect(lines[0][1]).toMatchObject({
      text: "World",
      color: "#55ff55",
      bold: true,
    });
    expect(motdPlainText("§aHello §lWorld")).toBe("Hello World");
  });

  it("keeps two MOTD lines", () => {
    const lines = parseMotdLines("§eLine 1\n§7Line 2");
    expect(lines).toHaveLength(2);
    expect(lines[0][0].text).toBe("Line 1");
    expect(lines[1][0]).toMatchObject({ text: "Line 2", color: "#aaaaaa" });
  });

  it("parses §x hex colors", () => {
    const lines = parseMotdLines("§x§5§5§f§f§5§5Hi");
    expect(lines[0][0]).toMatchObject({ text: "Hi", color: "#55ff55" });
  });

  it("returns empty for blank motd", () => {
    expect(parseMotdLines("")).toEqual([]);
    expect(motdPlainText("")).toBe("");
  });

  it("darkens light motd colors for pale cards", () => {
    expect(motdColorOnLight("#ffffff")).toBe("rgba(0, 0, 0, 0.88)");
    expect(motdColorOnLight("#55ff55")).toBe("#389e0d");
    expect(motdColorOnLight("#0000aa")).toBe("#0000aa");
  });
});
