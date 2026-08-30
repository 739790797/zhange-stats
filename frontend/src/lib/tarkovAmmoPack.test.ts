import { describe, expect, it } from "vitest";
import { ammoPackDisplayUrls } from "./tarkovAmmoPack";

describe("ammoPackDisplayUrls", () => {
  it("prefers the linked ammo pack image", () => {
    expect(
      ammoPackDisplayUrls({
        pack_icon_link: "https://assets.tarkov.dev/pack-icon.webp",
      }),
    ).toEqual({
      thumb: "https://assets.tarkov.dev/pack-base-image.webp",
      hd: "https://assets.tarkov.dev/pack-512.webp",
    });
  });

  it("stays empty when the round has no ammo pack", () => {
    expect(
      ammoPackDisplayUrls({
        pack_icon_link: "",
      }),
    ).toEqual({ thumb: "", hd: "" });
  });
});
