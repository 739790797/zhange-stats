import { describe, expect, it } from "vitest";
import {
  isStaleTarkovDevMapThumb,
  tarkovMapThumbUrl,
} from "./tarkovMapThumbs";

describe("tarkovMapThumbUrl", () => {
  it("rejects SPA-swallowed tarkov.dev thumbs", () => {
    expect(
      isStaleTarkovDevMapThumb("https://tarkov.dev/maps/factory_thumb.jpg"),
    ).toBe(true);
    expect(
      isStaleTarkovDevMapThumb(
        "https://assets.tarkov.dev/maps/svg/Factory.svg",
      ),
    ).toBe(false);
  });

  it("maps hub slugs to assets.tarkov.dev", () => {
    expect(tarkovMapThumbUrl("factory")).toBe(
      "https://assets.tarkov.dev/maps/svg/Factory.svg",
    );
    expect(tarkovMapThumbUrl("lab")).toContain("labs_v4");
    expect(tarkovMapThumbUrl("streets")).toContain("StreetsOfTarkov.svg");
    expect(tarkovMapThumbUrl("night-factory")).toContain("Factory.svg");
  });

  it("ignores stale API thumbs and keeps valid ones", () => {
    expect(
      tarkovMapThumbUrl("factory", "https://tarkov.dev/maps/factory_thumb.jpg"),
    ).toBe("https://assets.tarkov.dev/maps/svg/Factory.svg");
    expect(
      tarkovMapThumbUrl(
        "factory",
        "https://assets.tarkov.dev/maps/svg/Factory.svg",
      ),
    ).toBe("https://assets.tarkov.dev/maps/svg/Factory.svg");
  });
});
