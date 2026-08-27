import { describe, expect, it } from "vitest";
import {
  allPresentExtractKindsOn,
  anyPresentExtractKindOn,
  defaultExtractKindFlags,
  extractKindsPresent,
  isExtractKindVisible,
  TARKOV_EXTRACT_COLORS,
  TARKOV_EXTRACT_KIND_LABELS,
  tarkovExtractIconUrl,
  tarkovExtractKind,
  tarkovExtractStyle,
  withExtractKindsForPresent,
} from "./tarkovMapExtracts";

describe("tarkov map extract styles", () => {
  it("maps api faction labels to tarkov.dev kinds", () => {
    expect(tarkovExtractKind("PMC")).toBe("pmc");
    expect(tarkovExtractKind("pmc")).toBe("pmc");
    expect(tarkovExtractKind("Scav")).toBe("scav");
    expect(tarkovExtractKind("通用")).toBe("shared");
    expect(tarkovExtractKind("shared")).toBe("shared");
    expect(tarkovExtractKind("转图")).toBe("transit");
    expect(tarkovExtractKind("transit")).toBe("transit");
    expect(tarkovExtractKind("")).toBe("shared");
    expect(tarkovExtractKind("unknown")).toBe("shared");
  });

  it("uses tarkov.dev extract colors and wiki shield icons", () => {
    expect(tarkovExtractStyle("PMC").color).toBe(TARKOV_EXTRACT_COLORS.pmc);
    expect(tarkovExtractStyle("Scav").color).toBe("#ff7800");
    expect(tarkovExtractStyle("通用").color).toBe("#00e4e5");
    expect(tarkovExtractStyle("转图").color).toBe("#e53500");
    expect(tarkovExtractIconUrl("pmc")).toBe("/tarkov/map-icons/extract_pmc.png");
    expect(tarkovExtractStyle("pmc").iconUrl).toContain("extract_pmc.png");
    expect(tarkovExtractStyle("PMC").zIndex).toBeGreaterThan(
      tarkovExtractStyle("Scav").zIndex,
    );
    expect(TARKOV_EXTRACT_KIND_LABELS.shared).toBe("共享");
    expect(TARKOV_EXTRACT_KIND_LABELS.transit).toBe("转移点");
  });

  it("filters and toggles extract kinds like tarkov.dev layer groups", () => {
    const present = extractKindsPresent([
      { faction: "PMC" },
      { faction: "Scav" },
      { faction: "通用" },
      { faction: "PMC" },
    ]);
    expect(present).toEqual(["pmc", "scav", "shared"]);

    const flags = defaultExtractKindFlags(true);
    expect(isExtractKindVisible(flags, "Scav")).toBe(true);
    expect(allPresentExtractKindsOn(flags, present)).toBe(true);

    const offScav = { ...flags, scav: false };
    expect(isExtractKindVisible(offScav, "Scav")).toBe(false);
    expect(allPresentExtractKindsOn(offScav, present)).toBe(false);
    expect(anyPresentExtractKindOn(offScav, present)).toBe(true);

    expect(withExtractKindsForPresent(offScav, present, false)).toEqual({
      pmc: false,
      scav: false,
      shared: false,
      transit: true,
    });
  });
});
