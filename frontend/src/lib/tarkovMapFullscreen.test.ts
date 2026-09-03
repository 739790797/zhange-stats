import { describe, expect, it } from "vitest";
import { resolveMapOverlayContainer } from "./tarkovMapFullscreen";

describe("resolveMapOverlayContainer", () => {
  it("keeps overlays on the page until the map is fullscreen", () => {
    const root = {} as HTMLElement;
    expect(resolveMapOverlayContainer(root, false)).toBeUndefined();
    expect(resolveMapOverlayContainer(null, true)).toBeUndefined();
    expect(resolveMapOverlayContainer(root, true)).toBe(root);
  });
});
