import { describe, expect, it } from "vitest";
import {
  bitcoinMsToProduce,
  bitcoinPerDay,
  DEFAULT_BITCOIN_DURATION_SEC,
} from "./tarkovBitcoinFarm";

describe("bitcoinMsToProduce", () => {
  it("uses the 1-GPU baseline without scaling", () => {
    expect(bitcoinMsToProduce(1, 1000)).toBe(1_000_000);
    expect(bitcoinMsToProduce(1)).toBe(DEFAULT_BITCOIN_DURATION_SEC * 1000);
  });

  it("shortens the interval as GPUs increase", () => {
    const one = bitcoinMsToProduce(1, 1000);
    const two = bitcoinMsToProduce(2, 1000);
    expect(two).toBeLessThan(one);
    expect(bitcoinPerDay(50, 1000)).toBeGreaterThan(bitcoinPerDay(1, 1000));
  });
});
