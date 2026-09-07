import { describe, expect, it } from "vitest";
import type { TarkovItemDropSource } from "./tarkovItemSources";
import {
  buildItemFleaQuote,
  dropSourceHref,
  dropSourcePortrait,
  dropSourceSectionLabel,
  hasFleaQuote,
  itemDropSection,
  itemHasSources,
  itemHasUses,
  questKindChip,
  questRewardKindLabel,
  requiredItemCount,
  splitItemDropSources,
} from "./tarkovItemSources";

function drop(
  row: Pick<TarkovItemDropSource, "id"> & Partial<TarkovItemDropSource>,
): TarkovItemDropSource {
  return {
    slug: "",
    name: "",
    kind: "boss",
    maps_label: "",
    portrait_link: "",
    ...row,
  };
}

describe("tarkovItemSources", () => {
  it("hasFleaQuote needs lastLow or avg24", () => {
    expect(hasFleaQuote(undefined)).toBe(false);
    expect(hasFleaQuote({ lastLow: null, avg24: null })).toBe(false);
    expect(hasFleaQuote({ lastLow: 0, avg24: 0 })).toBe(false);
    expect(hasFleaQuote({ lastLow: 1200, avg24: null })).toBe(true);
    expect(hasFleaQuote({ lastLow: null, avg24: 800 })).toBe(true);
  });

  it("buildItemFleaQuote hides noFlea and falls back to vendor price", () => {
    expect(
      buildItemFleaQuote({ types: ["noFlea"], lastLowPrice: 9000 }),
    ).toBeNull();
    expect(
      buildItemFleaQuote(
        { lastLowPrice: 0, avg24hPrice: null },
        {
          fallbackOffers: [
            {
              vendor: "flea-market",
              vendorName: "Flea",
              price: 1500,
              currency: "RUB",
              priceRub: 1500,
              minLevel: null,
            },
          ],
        },
      ),
    ).toEqual({
      lastLow: 1500,
      avg24: null,
      change48: null,
      change48p: null,
    });
  });

  it("itemHasSources is false when empty", () => {
    expect(itemHasSources(undefined)).toBe(false);
    expect(itemHasSources({ barters: [], crafts: [], quest_rewards: [] })).toBe(
      false,
    );
  });

  it("itemHasSources is true when any bucket has rows", () => {
    expect(
      itemHasSources({
        barters: [],
        crafts: [{ id: "c1" } as never],
        quest_rewards: [],
      }),
    ).toBe(true);
    expect(
      itemHasSources({
        barters: [],
        crafts: [],
        quest_rewards: [],
        drops: [drop({ id: "bossKilla", slug: "killa", name: "Killa" })],
      }),
    ).toBe(true);
  });

  it("itemHasUses is true for hideout or tasks", () => {
    expect(itemHasUses(undefined)).toBe(false);
    expect(
      itemHasUses({ barters: [], crafts: [], hideout: [], tasks: [] }),
    ).toBe(false);
    expect(
      itemHasUses({
        barters: [],
        crafts: [],
        hideout: [{ station_slug: "workbench" } as never],
        tasks: [],
      }),
    ).toBe(true);
  });

  it("labels quest reward kinds", () => {
    expect(questRewardKindLabel("start")).toBe("接取奖励");
    expect(questRewardKindLabel("finish")).toBe("完成奖励");
    expect(questRewardKindLabel("")).toBe("任务奖励");
    expect(questKindChip("start")).toBe("接取");
    expect(questKindChip("finish")).toBe("完成");
    expect(questKindChip("require")).toBe("需求");
    expect(questKindChip("build")).toBe("建造");
  });

  it("sums required count for this item", () => {
    expect(
      requiredItemCount(
        [
          { id: "bolt", count: 2 },
          { id: "other", count: 9 },
          { id: "bolt", count: 1 },
        ],
        "bolt",
      ),
    ).toBe(3);
    expect(requiredItemCount([], "bolt")).toBe(0);
  });

  it("splits drops into Boss vs 非 Boss", () => {
    const groups = splitItemDropSources([
      drop({ id: "bossKilla", slug: "killa", name: "Killa", kind: "boss" }),
      drop({
        id: "followerBigPipe",
        slug: "big-pipe",
        name: "Big Pipe",
        kind: "boss",
        parent_ids: ["bossKnight"],
      }),
      drop({ id: "pmcBot", slug: "raider", name: "Raider", kind: "elite" }),
      drop({ id: "assault", slug: "scav", name: "Scav", kind: "soldier" }),
    ]);
    expect(groups.boss.map((row) => row.slug)).toEqual(["killa", "big-pipe"]);
    expect(groups.other.map((row) => row.slug)).toEqual(["raider", "scav"]);
    expect(itemDropSection({ id: "bossKilla" })).toBe("boss");
    expect(itemDropSection({ id: "pmcBot" })).toBe("other");
    expect(dropSourceSectionLabel("other")).toBe("非 Boss");
    expect(dropSourceHref(drop({ id: "bossKilla", slug: "killa" }))).toBe(
      "/guides/tarkov/bosses/killa",
    );
    expect(
      dropSourcePortrait(
        drop({
          id: "bossKilla",
          slug: "killa",
          portrait_link: "https://cdn.example/killa.png",
        }),
      ),
    ).toBe("https://cdn.example/killa.png");
  });
});
