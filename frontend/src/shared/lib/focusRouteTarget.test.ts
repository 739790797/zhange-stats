/** @vitest-environment happy-dom */
import { afterEach, describe, expect, it, vi } from "vitest";
import { focusWithoutVisibleRing, ROUTE_FOCUS_CLASS } from "./focusRouteTarget";

describe("focusWithoutVisibleRing", () => {
  let el: HTMLDivElement;

  afterEach(() => {
    el?.remove();
  });

  it("noops on null", () => {
    expect(() => focusWithoutVisibleRing(null)).not.toThrow();
  });

  it("focuses without a visible ring and clears the mark on blur", () => {
    el = document.createElement("div");
    el.tabIndex = -1;
    document.body.appendChild(el);
    const focus = vi.spyOn(el, "focus");

    focusWithoutVisibleRing(el);

    expect(el.classList.contains(ROUTE_FOCUS_CLASS)).toBe(true);
    expect(focus).toHaveBeenCalledWith(
      expect.objectContaining({ preventScroll: true, focusVisible: false }),
    );

    el.dispatchEvent(new FocusEvent("blur"));
    expect(el.classList.contains(ROUTE_FOCUS_CLASS)).toBe(false);
  });
});
