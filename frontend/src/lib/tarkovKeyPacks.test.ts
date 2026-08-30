import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  UNBOUND_PACK_SLUG,
  TARKOV_KEY_PACKS_STORAGE_KEY,
  COMMUNITY_KEY_HINT,
  buildKeyPackNav,
  filterPackKeys,
  firstPackSlugForQuery,
  formatKeyMetaTags,
  formatKeySourceTags,
  formatKeyTagLine,
  formatKeyUses,
  isCommunityKeyBind,
  keyMatchesQuery,
  loadOwnedIds,
  packOwnedCount,
  parseOwnedState,
  readOwnedFilter,
  resolvePackSlug,
  saveOwnedIds,
  markOwnsMigrated,
  takeLocalOwnsForMigrate,
  toggleOwnedId,
} from "./tarkovKeyPacks";

describe("parseOwnedState", () => {
  it("reads v1 owned list", () => {
    expect(parseOwnedState(JSON.stringify({ v: 1, owned: ["a", "", "b"] }))).toEqual(
      ["a", "b"],
    );
  });

  it("returns empty on junk", () => {
    expect(parseOwnedState("nope")).toEqual([]);
    expect(parseOwnedState(null)).toEqual([]);
  });
});

describe("owned storage", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        mem.set(key, value);
      },
      removeItem: (key: string) => {
        mem.delete(key);
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("round-trips ids", () => {
    saveOwnedIds(["k1", "k2"]);
    expect(mem.get(TARKOV_KEY_PACKS_STORAGE_KEY)).toContain("k1");
    expect(loadOwnedIds()).toEqual(["k1", "k2"]);
  });

  it("toggles membership", () => {
    expect(toggleOwnedId(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleOwnedId(["a", "b"], "a")).toEqual(["b"]);
    expect(toggleOwnedId(["a"], "  ")).toEqual(["a"]);
  });

  it("hands local owns until marked migrated", () => {
    saveOwnedIds(["k1"]);
    expect(takeLocalOwnsForMigrate()).toEqual(["k1"]);
    markOwnsMigrated(["k1"]);
    expect(takeLocalOwnsForMigrate()).toBeNull();
  });
});

describe("packOwnedCount / filter", () => {
  const keys = [
    { id: "a", name: "宿舍 114 钥匙", short_name: "114" },
    { id: "b", name: "海岸线别墅钥匙" },
  ];
  const owned = new Set(["a"]);

  it("counts owned in a pack", () => {
    expect(packOwnedCount(keys, owned)).toEqual({ have: 1, total: 2 });
  });

  it("matches name or short name", () => {
    expect(keyMatchesQuery(keys[0], "114")).toBe(true);
    expect(keyMatchesQuery(keys[1], "别墅")).toBe(true);
    expect(keyMatchesQuery(keys[1], "customs")).toBe(false);
  });

  it("filters by owned / missing / query", () => {
    expect(filterPackKeys(keys, "", "owned", owned).map((k) => k.id)).toEqual([
      "a",
    ]);
    expect(filterPackKeys(keys, "", "missing", owned).map((k) => k.id)).toEqual([
      "b",
    ]);
    expect(filterPackKeys(keys, "别墅", "all", owned).map((k) => k.id)).toEqual([
      "b",
    ]);
  });
});

describe("resolvePackSlug", () => {
  it("accepts short ids and canonical slugs", () => {
    const slugs = ["customs", "streets-of-tarkov", UNBOUND_PACK_SLUG];
    expect(resolvePackSlug("streets", slugs)).toBe("streets-of-tarkov");
    expect(resolvePackSlug("unbound", slugs)).toBe(UNBOUND_PACK_SLUG);
    expect(resolvePackSlug("nope", slugs)).toBe("customs");
    expect(resolvePackSlug("", slugs)).toBe("customs");
  });
});

describe("buildKeyPackNav", () => {
  it("keeps home map order and appends unbound", () => {
    const nav = buildKeyPackNav(
      [
        {
          slug: "customs",
          name: "海关",
          english: "Customs",
          keys: [{ id: "k1", name: "宿舍 114" }],
        },
      ],
      [{ id: "q1", name: "任务钥" }],
    );
    expect(nav[0].slug).toBe("reserve");
    const customs = nav.find((row) => row.slug === "customs");
    expect(customs?.name).toBe("海关");
    expect(customs?.keys).toEqual([{ id: "k1", name: "宿舍 114" }]);
    expect(nav[nav.length - 1]).toMatchObject({
      slug: UNBOUND_PACK_SLUG,
      name: "未绑定地图",
      keys: [{ id: "q1", name: "任务钥" }],
    });
    expect(nav.some((row) => row.slug === "openworld")).toBe(false);
  });

  it("keeps home Chinese label when api name is English", () => {
    const nav = buildKeyPackNav(
      [{ slug: "customs", name: "Customs", keys: [] }],
      [],
    );
    expect(nav.find((row) => row.slug === "customs")?.name).toBe("海关");
  });
});

describe("firstPackSlugForQuery", () => {
  it("jumps to the first pack that has the key", () => {
    expect(
      firstPackSlugForQuery(
        [
          { slug: "customs", name: "海关", english: "Customs", keys: [] },
          {
            slug: "shoreline",
            name: "海岸线",
            english: "Shoreline",
            keys: [{ id: "v", name: "别墅钥匙" }],
          },
        ],
        "别墅",
      ),
    ).toBe("shoreline");
    expect(firstPackSlugForQuery([], "x")).toBeNull();
  });
});

describe("community bind hint", () => {
  it("only flags community=true and keeps unofficial-source copy", () => {
    expect(isCommunityKeyBind({ community: true })).toBe(true);
    expect(isCommunityKeyBind({ community: false })).toBe(false);
    expect(isCommunityKeyBind({})).toBe(false);
    expect(COMMUNITY_KEY_HINT).toContain("非官方 API");
  });
});

describe("formatKeyUses / formatKeyMetaTags", () => {
  it("shows durability as a tag and omits door counts", () => {
    expect(formatKeyUses(40)).toBe("40");
    expect(formatKeyUses(0)).toBe("无限");
    expect(formatKeyUses(null)).toBe("");
    expect(formatKeyUses(-1)).toBe("");
    expect(formatKeyMetaTags({ id: "k", uses: 40, lock_count: 2 })).toEqual([
      { kind: "uses", label: "最大耐久", hint: "40" },
    ]);
    expect(formatKeyMetaTags({ id: "card", uses: 10, access: true })).toEqual([
      { kind: "uses", label: "最大耐久", hint: "10" },
      { kind: "access", label: "入场", hint: "" },
    ]);
    expect(
      formatKeyTagLine({ label: "最大耐久", hint: "40" }),
    ).toBe("最大耐久：40");
    expect(
      formatKeyTagLine({ label: "跳蚤市场", hint: "24,000 ₽" }),
    ).toBe("跳蚤市场：24,000 ₽");
    expect(formatKeyTagLine({ label: "入场", hint: "" })).toBe("入场");
    expect(formatKeyMetaTags({ id: "x", lock_count: 1 })).toEqual([]);
  });
});

describe("formatKeySourceTags", () => {
  it("emits one tag per available source without flea tiers", () => {
    const tags = formatKeySourceTags({
      id: "k1",
      name: "宿舍 114 钥匙",
      types: ["keys"],
      sources: {
        barters: [{ trader_name: "大妈", trader_slug: "therapist", min_trader_level: 1 }],
        crafts: [{ station_name: "情报中心", station_slug: "intelligence-center", level: 2 }],
        tasks: [{ id: "task-1", name: "验收" }],
        flea: { price: 88000 },
      },
    });
    expect(tags.map((row) => row.kind)).toEqual([
      "barter",
      "craft",
      "task",
      "flea",
    ]);
    expect(tags[0]).toMatchObject({ label: "以物易物", hint: "大妈 1级" });
    expect(tags[1].href).toContain("/hideout/intelligence-center");
    expect(tags[2].href).toContain("/tasks/task-1");
    expect(tags[3].hint).toContain("88,000");
    expect(tags[3].hint).not.toMatch(/级/);
  });

  it("omits missing sources", () => {
    expect(formatKeySourceTags({ id: "x" })).toEqual([]);
    expect(
      formatKeySourceTags({
        id: "x",
        sources: { barters: [], crafts: [], tasks: [], flea: null },
      }),
    ).toEqual([]);
  });

  it("hides unresolved task id placeholders", () => {
    const tags = formatKeySourceTags({
      id: "k1",
      sources: {
        tasks: [
          { id: "6745fcde0dfbbc74ca0f721d", name: "6745fcde0dfbbc74ca0f721d name" },
        ],
      },
    });
    expect(tags).toEqual([
      {
        kind: "task",
        label: "任务奖励",
        hint: "",
        href: "/guides/tarkov/tasks/6745fcde0dfbbc74ca0f721d",
      },
    ]);
  });
});

describe("readOwnedFilter", () => {
  it("only accepts owned / missing", () => {
    expect(readOwnedFilter("owned")).toBe("owned");
    expect(readOwnedFilter("missing")).toBe("missing");
    expect(readOwnedFilter("nope")).toBe("all");
  });
});
