import { describe, expect, it } from "vitest";
import { readPrefersReducedMotion } from "./prefersReducedMotion";

describe("readPrefersReducedMotion", () => {
  it("is false without matchMedia", () => {
    expect(readPrefersReducedMotion()).toBe(false);
  });

  it("reads the reduce media query", () => {
    expect(readPrefersReducedMotion(() => ({ matches: true }))).toBe(true);
    expect(readPrefersReducedMotion(() => ({ matches: false }))).toBe(false);
  });

  it("is false when matchMedia throws", () => {
    expect(
      readPrefersReducedMotion(() => {
        throw new Error("no mq");
      }),
    ).toBe(false);
  });
});
