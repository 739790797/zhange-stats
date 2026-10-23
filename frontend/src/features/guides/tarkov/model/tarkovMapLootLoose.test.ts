import { describe, expect, it } from "vitest";
import {
  LOOT_LOOSE_OTHER_KIND,
  lootItemFromChip,
  lootLooseKindFromItem,
  lootLooseKindLabel,
  lootLooseKindsOfRow,
  lootLooseKindsPresent,
  lootLooseMarkerIconUrl,
  lootLooseRowVisible,
  tarkovLootLooseTooltipHtml,
  tarkovLooseLootKindIconUrl,
} from "./tarkovMapLootLoose";

const VALUABLES = "5b47574386f77428ca22b2f1";
const MECHANICAL_KEYS = "5c518ec986f7743b68682ce2";
const KEYS_ROOT = "5b47574386f77428ca22b342";

describe("tarkov map loot loose kinds", () => {
  it("prefers handbook leaf over parent root, like tarkov.dev Loose Loot", () => {
    expect(
      lootLooseKindFromItem({
        handbook_ids: [KEYS_ROOT, MECHANICAL_KEYS],
      }),
    ).toBe(MECHANICAL_KEYS);
    expect(lootLooseKindLabel(MECHANICAL_KEYS)).toBe("机械钥匙");
    expect(lootLooseKindLabel(VALUABLES)).toBe("贵重物品");
  });

  it("falls back to other when handbook is missing", () => {
    expect(lootLooseKindFromItem({ handbook_ids: [] })).toBe(
      LOOT_LOOSE_OTHER_KIND,
    );
    expect(lootLooseKindLabel("unknown")).toBe("其他");
  });

  it("lists a pile on every item category it contains", () => {
    expect(
      lootLooseKindsOfRow({
        items: [
          { handbook_ids: [VALUABLES] },
          { handbook_ids: [MECHANICAL_KEYS] },
        ],
      }).sort(),
    ).toEqual([MECHANICAL_KEYS, VALUABLES].sort());
  });

  it("orders present kinds like the tarkov.dev legend", () => {
    expect(
      lootLooseKindsPresent([
        { items: [{ handbook_ids: [MECHANICAL_KEYS] }] },
        { items: [{ handbook_ids: [VALUABLES] }] },
      ]),
    ).toEqual([VALUABLES, MECHANICAL_KEYS]);
  });

  it("shows a mixed pile if any of its categories is on", () => {
    const row = {
      items: [
        { handbook_ids: [VALUABLES] },
        { handbook_ids: [MECHANICAL_KEYS] },
      ],
    };
    expect(lootLooseRowVisible(row, { [VALUABLES]: true })).toBe(true);
    expect(lootLooseRowVisible(row, { [MECHANICAL_KEYS]: false })).toBe(false);
  });

  it("uses tarkov.dev handbook category icons", () => {
    expect(tarkovLooseLootKindIconUrl(VALUABLES)).toBe(
      "https://assets.tarkov.dev/handbook-category-5b47574386f77428ca22b2f1-icon.webp",
    );
    expect(tarkovLooseLootKindIconUrl(MECHANICAL_KEYS)).toBe(
      "https://assets.tarkov.dev/handbook-category-5c518ec986f7743b68682ce2-icon.webp",
    );
    expect(tarkovLooseLootKindIconUrl(LOOT_LOOSE_OTHER_KIND)).toBe(
      "https://assets.tarkov.dev/handbook-category-5b47574386f77428ca22b2f4-icon.webp",
    );
    expect(tarkovLooseLootKindIconUrl("unknown")).toBe(
      "/tarkov/map-icons/loose_loot.png",
    );
  });

  it("uses handbook category icons on the map, including single items", () => {
    expect(
      lootLooseMarkerIconUrl({
        items: [
          {
            id: "544fb62a4bdc2dfb738b4568",
            icon_link: "https://assets.tarkov.dev/fuel-base-image.webp",
            handbook_ids: [VALUABLES],
          },
        ],
      }),
    ).toBe(
      "https://assets.tarkov.dev/handbook-category-5b47574386f77428ca22b2f1-icon.webp",
    );
    expect(
      lootLooseMarkerIconUrl({
        items: [
          { handbook_ids: [VALUABLES] },
          { handbook_ids: [VALUABLES] },
        ],
      }),
    ).toBe(
      "https://assets.tarkov.dev/handbook-category-5b47574386f77428ca22b2f1-icon.webp",
    );
    expect(
      lootLooseMarkerIconUrl({
        items: [
          { handbook_ids: [VALUABLES] },
          { handbook_ids: [MECHANICAL_KEYS] },
        ],
      }),
    ).toBe("/tarkov/map-icons/loose_loot.png");
  });
});

describe("tarkov loot loose tooltip html", () => {
  const classes = { tip: "lootTip", icon: "lootIcon", item: "lootItem", card: "lootCard" };

  it("renders item icons instead of a name list", () => {
    const html = tarkovLootLooseTooltipHtml(
      [
        {
          id: "544fb62a4bdc2dfb738b4568",
          name: "野营燃料桶",
          icon_link: "https://assets.tarkov.dev/fuel-base-image.webp",
          types: ["barter"],
        },
        {
          id: "57347c5b245977448d35f6e1",
          name: "尼龙绳索",
          count: 15,
        },
      ],
      classes,
    );
    expect(html).toContain('class="lootTip"');
    expect(html).toContain("https://assets.tarkov.dev/fuel-icon.webp");
    expect(html).toContain(
      "https://assets.tarkov.dev/57347c5b245977448d35f6e1-icon.webp",
    );
    expect(html).toContain('data-tarkov-loot-item="544fb62a4bdc2dfb738b4568"');
    expect(html).toContain('data-tarkov-loot-chip="1"');
    expect(html).toContain('data-tarkov-loot-types="barter"');
    expect(html).toContain('class="lootCard"');
    expect(html).toContain("野营燃料桶");
    expect(html).toContain("尼龙绳索");
    expect(html).toContain("×15");
    expect(html).not.toContain("title=");
    expect(html).not.toContain("野营燃料桶、尼龙绳索");
    expect(html.match(/<img /g)?.length).toBe(4);
  });

  it("falls back to the generic loot icon when the pile is empty", () => {
    const html = tarkovLootLooseTooltipHtml([], classes);
    expect(html).toContain("/tarkov/map-icons/loose_loot.png");
    expect(html).toContain("散落物");
    expect(html).not.toContain("data-tarkov-loot-item=");
    expect(html.match(/<img /g)?.length).toBe(2);
  });

  it("reads an item chip for map navigation", () => {
    expect(
      lootItemFromChip({
        getAttribute: (name) =>
          name === "data-tarkov-loot-item"
            ? "544fb62a4bdc2dfb738b4568"
            : name === "data-tarkov-loot-types"
              ? "barter,keys"
              : null,
      }),
    ).toEqual({
      id: "544fb62a4bdc2dfb738b4568",
      types: ["barter", "keys"],
    });
    expect(
      lootItemFromChip({
        getAttribute: () => "",
      }),
    ).toBeNull();
  });
});
