import { describe, expect, it } from "vitest";
import {
  fullscreenElementIncludesMap,
  resolveMapOverlayContainer,
} from "./tarkovMapFullscreen";

describe("resolveMapOverlayContainer", () => {
  it("keeps overlays on the page until the map is fullscreen", () => {
    const root = {} as HTMLElement;
    expect(resolveMapOverlayContainer(root, false)).toBeUndefined();
    expect(resolveMapOverlayContainer(null, true)).toBeUndefined();
    expect(resolveMapOverlayContainer(root, true)).toBe(root);
  });
});

describe("fullscreenElementIncludesMap", () => {
  it("treats the map and a parent workspace as the same fullscreen", () => {
    const wrap = {};
    const workspace = { contains: (node: unknown) => node === wrap };
    expect(fullscreenElementIncludesMap(null, wrap as Element)).toBe(false);
    expect(fullscreenElementIncludesMap(workspace as Element, null)).toBe(false);
    expect(fullscreenElementIncludesMap(wrap as Element, wrap as Element)).toBe(true);
    expect(
      fullscreenElementIncludesMap(workspace as Element, wrap as Element),
    ).toBe(true);
    expect(
      fullscreenElementIncludesMap(
        { contains: () => false } as unknown as Element,
        wrap as Element,
      ),
    ).toBe(false);
  });
});
