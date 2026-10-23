import { describe, expect, it } from "vitest";
import { ror2ExpansionOrder, sortRor2Rows } from "./ror2List";

describe("ROR2 shared list rules", () => {
  it("keeps base and known DLCs in topbar order, then sorts unknown sources", () => {
    expect(
      ror2ExpansionOrder([
        { expansion: "ZZ" },
        { expansion: "HC" },
        { expansion: "Junk" },
        { expansion: "AC" },
        { expansion: "" },
        { expansion: "SotS" },
        { expansion: "AA" },
        { expansion: "SotV" },
      ]),
    ).toEqual(["base", "SotV", "SotS", "AC", "HC", "AA", "ZZ"]);
  });

  it("sorts by release source first, then approved Chinese pinyin", () => {
    const rows = [
      { name: "SotV", name_zh: "中层", expansion: "SotV" },
      { name: "Base B", name_zh: "白色", expansion: "" },
      { name: "HC", name_zh: "青色", expansion: "HC" },
      { name: "Base A", name_zh: "阿尔法", expansion: "" },
      { name: "Future Z", name_zh: "钟表", expansion: "ZZ" },
      { name: "SotS", name_zh: "胡萝卜", expansion: "SotS" },
      { name: "AC", name_zh: "大门", expansion: "AC" },
      { name: "Future A", name_zh: "八面体", expansion: "AA" },
    ];

    expect(sortRor2Rows(rows, "source-name").map((row) => row.name)).toEqual([
      "Base A",
      "Base B",
      "SotV",
      "SotS",
      "AC",
      "HC",
      "Future A",
      "Future Z",
    ]);
  });

  it("falls back to the source name and can sort names without inferring a DLC", () => {
    const rows = [
      { name: "Zulu", name_zh: " ", expansion: "SotV" },
      { name: "Alpha", name_zh: "阿尔法", expansion: "" },
    ];
    expect(sortRor2Rows(rows, "name").map((row) => row.name)).toEqual(["Alpha", "Zulu"]);
  });

  it("returns a copy without changing a canonical sequence", () => {
    const rows = [
      { name: "Second", name_zh: "阿", expansion: "SotS" },
      { name: "First", name_zh: "中", expansion: "" },
    ];
    const sorted = sortRor2Rows(rows, "canonical");
    expect(sorted).toEqual(rows);
    expect(sorted).not.toBe(rows);
    expect(rows.map((row) => row.name)).toEqual(["Second", "First"]);
  });
});
