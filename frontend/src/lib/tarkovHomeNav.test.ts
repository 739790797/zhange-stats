import { describe, expect, it } from "vitest";
import { ITEMS_BASE_PATH } from "./tarkovItemTypes";
import {
  TARKOV_BOSSES,
  TARKOV_HOME_BOSSES,
  TARKOV_HOME_ITEMS,
  TARKOV_HOME_ITEM_GROUPS,
  TARKOV_HOME_TRADERS,
  TARKOV_ITEM_MENU_GROUPS,
  TARKOV_MAPS,
  TARKOV_PROGRESSION,
  TARKOV_RAID_PREP_NAV,
  TARKOV_TOOLS,
  TARKOV_TOP_NAV,
  TARKOV_TRADERS,
  bossPortraitUrl,
  traderIconUrl,
  traderPortraitUrl,
  buildHomeSearchIndex,
  buildSiteSearchSections,
  filterHomeSearch,
  isTarkovTopNavActive,
  tarkovPageTitle,
  textMatchesQuery,
} from "./tarkovHomeNav";

describe("filterHomeSearch", () => {
  const index = buildHomeSearchIndex();

  it("returns empty when query is blank", () => {
    expect(filterHomeSearch("  ", index)).toEqual([]);
  });

  it("finds ammo chart and handbook ammo", () => {
    const hits = filterHomeSearch("弹药", index);
    expect(hits.some((h) => h.id === "ammo-chart")).toBe(true);
    expect(hits.some((h) => h.label === "弹药图表筛选器")).toBe(true);
    expect(hits.some((h) => h.id === "ammo" || h.id === "handbook-ammo")).toBe(
      true,
    );
  });

  it("finds customs by chinese or english", () => {
    expect(filterHomeSearch("海关", index).some((h) => h.id === "customs")).toBe(
      true,
    );
    expect(
      filterHomeSearch("customs", index).some((h) => h.id === "customs"),
    ).toBe(true);
  });

  it("finds streets as 塔科夫街区 and ground zero as 中心区", () => {
    expect(
      filterHomeSearch("塔科夫街区", index).some((h) => h.id === "streets"),
    ).toBe(true);
    expect(
      filterHomeSearch("streets", index).some((h) => h.id === "streets"),
    ).toBe(true);
    expect(
      filterHomeSearch("中心区", index).some((h) => h.id === "ground-zero"),
    ).toBe(true);
    expect(
      filterHomeSearch("ground zero", index).some((h) => h.id === "ground-zero"),
    ).toBe(true);
  });

  it("finds bosses by chinese nicknames", () => {
    expect(filterHomeSearch("沙拉", index).some((h) => h.id === "reshala")).toBe(
      true,
    );
    expect(filterHomeSearch("三兄弟", index).some((h) => h.id === "goons")).toBe(
      true,
    );
  });

  it("finds ground zero without spaces", () => {
    expect(
      filterHomeSearch("groundzero", index).some((h) => h.id === "ground-zero"),
    ).toBe(true);
  });

  it("finds raid prep from the home search index", () => {
    expect(filterHomeSearch("战局", index).some((h) => h.id === "raid-prep")).toBe(
      true,
    );
  });
});

describe("textMatchesQuery", () => {
  it("matches hyphenated quest names against spaced titles", () => {
    expect(textMatchesQuery("医疗隐私-1", "医疗隐私 - Part 1")).toBe(true);
    expect(
      textMatchesQuery("医疗隐私-1", "Health Care Privacy - Part 1"),
    ).toBe(false);
  });
});

describe("buildSiteSearchSections", () => {
  const index = buildHomeSearchIndex();

  it("groups tasks first and keeps maps in 栏目", () => {
    const sections = buildSiteSearchSections(
      "医疗隐私-1",
      {
        q: "医疗隐私-1",
        items: [],
        tasks: [
          {
            id: "task-1",
            name: "医疗隐私-1",
            extra: "Therapist（大妈）",
          },
        ],
        traders: [],
        bosses: [],
        item_count: 0,
        task_count: 1,
        trader_count: 0,
        boss_count: 0,
      },
      index,
    );
    expect(sections.map((s) => s.id)).toEqual(["tasks"]);
    expect(sections[0].hits[0]).toMatchObject({
      href: "/guides/tarkov/tasks/task-1",
      label: "医疗隐私-1",
    });
  });

  it("keeps handbook ammo in 栏目 when searching 弹药", () => {
    const sections = buildSiteSearchSections("弹药", undefined, index);
    const nav = sections.find((s) => s.id === "nav");
    expect(nav?.hits.some((h) => h.label.includes("弹药"))).toBe(true);
    expect(sections.some((s) => s.id === "traders" || s.id === "bosses")).toBe(
      false,
    );
  });
});

describe("TARKOV_BOSSES", () => {
  it("uses tarkov.dev PvP spawn rates and includes Kollontay", () => {
    const byId = Object.fromEntries(TARKOV_BOSSES.map((b) => [b.id, b]));
    expect(byId.reshala).toMatchObject({
      map: "海关",
      spawn: "45%",
      guards: "×4",
      nickname: "沙拉",
      status: "ready",
    });
    expect(byId.killa).toMatchObject({ map: "立交桥", spawn: "45%", guards: "—" });
    expect(byId.glukhar).toMatchObject({
      map: "储备站",
      spawn: "30%",
      guards: "×6",
      nickname: "火车头",
    });
    expect(byId.shturman).toMatchObject({
      map: "森林",
      spawn: "45%",
      guards: "×2–3",
    });
    expect(byId.sanitar).toMatchObject({ map: "海岸线", spawn: "45%", guards: "×3" });
    expect(byId.tagilla).toMatchObject({
      map: "工厂",
      spawn: "30%",
      guards: "—",
      nickname: "锤哥",
    });
    expect(byId.kaban).toMatchObject({ map: "塔科夫街区", spawn: "45%", guards: "×6" });
    expect(byId.kollontay).toMatchObject({
      map: "塔科夫街区",
      spawn: "45%",
      guards: "×4",
    });
    expect(byId.zryachiy).toMatchObject({ map: "灯塔", spawn: "100%", guards: "×2" });
    expect(byId.goons).toMatchObject({
      map: "游荡",
      spawn: "15%",
      guards: "×2",
      nickname: "三兄弟",
    });
    expect(byId.cultists).toMatchObject({
      map: "海关/森林",
      spawn: "10%",
      guards: "×4",
    });
    expect(byId.partisan).toMatchObject({ map: "游荡", spawn: "10%", guards: "—" });
    expect(TARKOV_HOME_BOSSES.map((b) => b.id)).toContain("kollontay");
    expect(TARKOV_HOME_BOSSES.map((b) => b.id)).toContain("partisan");
    expect(bossPortraitUrl("goons")).toContain("knight-portrait");
    expect(bossPortraitUrl("cultists")).toContain("cultist-priest");
    expect(byId.goons.href).toBe("/guides/tarkov/bosses/knight");
    expect(byId.cultists.href).toBe("/guides/tarkov/bosses/cultist-priest");
    expect(byId.reshala.href).toBe("/guides/tarkov/bosses/reshala");
  });
});

describe("trader image urls", () => {
  it("uses tarkov.dev icon and portrait paths", () => {
    expect(traderIconUrl("prapor")).toBe(
      "https://tarkov.dev/images/traders/prapor-icon.jpg",
    );
    expect(traderPortraitUrl("prapor")).toBe(
      "https://tarkov.dev/images/traders/prapor-portrait.png",
    );
  });
});

describe("TARKOV_MAPS", () => {
  it("matches tarkov.dev compact grid labels, icons, and order", () => {
    expect(TARKOV_MAPS.map((m) => m.label)).toEqual([
      "储备站",
      "灯塔",
      "工厂",
      "海岸线",
      "海关",
      "立交桥",
      "码头",
      "迷宫",
      "破冰船",
      "森林",
      "实验室",
      "塔科夫街区",
      "中心区",
      "开放世界",
      "转移点",
    ]);
    expect(TARKOV_MAPS.every((m) => m.icon.length > 20)).toBe(true);
    expect(TARKOV_MAPS.find((m) => m.id === "streets")).toMatchObject({
      english: "Streets of Tarkov",
    });
    expect(TARKOV_MAPS.find((m) => m.id === "ground-zero")).toMatchObject({
      label: "中心区",
      english: "Ground Zero",
    });
    expect(TARKOV_MAPS.find((m) => m.id === "customs")).toMatchObject({
      href: "/guides/tarkov/maps/customs",
      status: "ready",
    });
    expect(TARKOV_MAPS.find((m) => m.id === "lab")).toMatchObject({
      href: "/guides/tarkov/maps/lab",
      status: "ready",
    });
    expect(TARKOV_MAPS.filter((m) => m.comingSoon).map((m) => m.id)).toEqual([
      "openworld",
      "transits",
    ]);
    expect(
      TARKOV_MAPS.filter((m) => !m.comingSoon).every((m) => m.status === "ready"),
    ).toBe(true);
  });
});

describe("TARKOV_HOME_ITEMS", () => {
  it("mirrors top-nav item columns as three home rows", () => {
    expect(TARKOV_HOME_ITEM_GROUPS.map((g) => g.id)).toEqual([
      "gear",
      "weaponry",
      "tools",
    ]);
    expect(TARKOV_HOME_ITEM_GROUPS.map((g) => g.items.map((i) => i.id))).toEqual([
      ["headsets", "helmets", "glasses", "armors", "rigs", "backpacks", "meds"],
      ["ammo", "guns", "mods", "pistol-grips", "suppressors"],
      ["grenades", "containers", "barter-items", "keys", "provisions"],
    ]);
    expect(TARKOV_HOME_ITEMS.map((i) => i.id)).toEqual(
      TARKOV_HOME_ITEM_GROUPS.flatMap((g) => g.items.map((i) => i.id)),
    );
  });

  it("uses compact-grid SVG path icons", () => {
    expect(TARKOV_HOME_ITEMS.every((item) => item.icon.length > 20)).toBe(true);
  });
});

describe("isTarkovTopNavActive", () => {
  it("highlights items for ammo and guns subpaths", () => {
    expect(isTarkovTopNavActive(ITEMS_BASE_PATH, `${ITEMS_BASE_PATH}/ammo`)).toBe(
      true,
    );
    expect(isTarkovTopNavActive(ITEMS_BASE_PATH, `${ITEMS_BASE_PATH}/guns`)).toBe(
      true,
    );
    expect(isTarkovTopNavActive(ITEMS_BASE_PATH, "/guides/tarkov/maps")).toBe(
      false,
    );
  });

  it("highlights progression when on the tasks page", () => {
    expect(
      isTarkovTopNavActive("/guides/tarkov/tasks", "/guides/tarkov/tasks"),
    ).toBe(true);
    expect(
      isTarkovTopNavActive("/guides/tarkov/tasks", "/guides/tarkov/progression", [
        "/guides/tarkov/progression",
      ]),
    ).toBe(true);
  });
});

describe("TARKOV_TOP_NAV", () => {
  it("nests tasks under progression instead of a top-level item", () => {
    expect(TARKOV_TOP_NAV.map((i) => i.id)).not.toContain("tasks");
    expect(TARKOV_TOP_NAV.find((i) => i.id === "progression")?.href).toBe(
      "/guides/tarkov/tasks",
    );
    expect(TARKOV_PROGRESSION[0]).toMatchObject({
      id: "tasks",
      label: "任务",
      href: "/guides/tarkov/tasks",
      status: "ready",
    });
    expect(TARKOV_PROGRESSION.find((p) => p.id === "hideout")).toMatchObject({
      href: "/guides/tarkov/hideout",
      status: "ready",
    });
    expect(TARKOV_PROGRESSION.find((p) => p.id === "raid-prep")).toBeUndefined();
    expect(TARKOV_PROGRESSION.find((p) => p.id === "loot-tiers")).toMatchObject({
      href: "/guides/tarkov/loot-tiers",
      status: "ready",
    });
  });
});

describe("TARKOV_TRADERS", () => {
  it("links every trader to a ready detail page", () => {
    expect(TARKOV_TRADERS.map((t) => t.id)).toEqual([
      "prapor",
      "therapist",
      "fence",
      "skier",
      "peacekeeper",
      "mechanic",
      "ragman",
      "jaeger",
      "lightkeeper",
      "ref",
      "btr-driver",
    ]);
    expect(TARKOV_TRADERS.every((t) => t.status === "ready")).toBe(true);
    expect(TARKOV_TRADERS[0]).toMatchObject({
      href: "/guides/tarkov/traders/prapor",
      english: "Prapor",
      chinese: "俄商",
    });
    expect(TARKOV_TRADERS.find((t) => t.id === "ref")).toMatchObject({
      chinese: "竞技场裁判",
      label: "Ref（竞技场裁判）",
    });
  });
});

describe("TARKOV_HOME_TRADERS", () => {
  it("shows the same traders as the hub, including Lightkeeper and BTR", () => {
    expect(TARKOV_HOME_TRADERS.map((t) => t.id)).toEqual(
      TARKOV_TRADERS.map((t) => t.id),
    );
    expect(TARKOV_HOME_TRADERS.map((t) => t.id)).toContain("lightkeeper");
    expect(TARKOV_HOME_TRADERS.map((t) => t.id)).toContain("btr-driver");
  });
});

describe("TARKOV_TOOLS", () => {
  it("keeps ammo chart first after raid prep moved to the home column", () => {
    expect(TARKOV_TOOLS.map((item) => item.id)).not.toContain("raid-prep");
    expect(TARKOV_RAID_PREP_NAV).toMatchObject({
      id: "raid-prep",
      label: "战局准备",
      href: "/guides/tarkov/raid-prep",
      status: "ready",
    });
    expect(TARKOV_TOOLS[0]).toMatchObject({
      id: "ammo-chart",
      label: "弹药图表筛选器",
      href: `${ITEMS_BASE_PATH}/ammo`,
      status: "ready",
    });
  });

  it("opens barter, craft, loot, hideout cost, wipe, and bitcoin tools", () => {
    const byId = Object.fromEntries(TARKOV_TOOLS.map((t) => [t.id, t]));
    expect(byId["barter-profit"]).toMatchObject({
      href: "/guides/tarkov/barters",
      status: "ready",
    });
    expect(byId["craft-profit"]).toMatchObject({
      href: "/guides/tarkov/crafts",
      status: "ready",
    });
    expect(byId["loot-tier-rank"]).toMatchObject({
      href: "/guides/tarkov/loot-tiers",
      status: "ready",
    });
    expect(byId["hideout-cost"]).toMatchObject({
      href: "/guides/tarkov/hideout-cost",
      status: "ready",
    });
    expect(byId["wipe-length"]).toMatchObject({
      href: "/guides/tarkov/wipe-length",
      status: "ready",
    });
    expect(byId["btc-farm"]).toMatchObject({
      href: "/guides/tarkov/bitcoin-farm",
      status: "ready",
    });
  });
});

describe("tarkovPageTitle", () => {
  it("uses handbook labels on item type paths", () => {
    expect(tarkovPageTitle("/guides/tarkov")).toBe("逃离塔科夫");
    expect(tarkovPageTitle("/guides/tarkov/items")).toBe("物品");
    expect(tarkovPageTitle("/guides/tarkov/items/meds")).toBe("医疗物品");
    expect(tarkovPageTitle("/guides/tarkov/tasks/abc")).toBe("任务");
    expect(tarkovPageTitle("/guides/tarkov/raid-prep")).toBe("战局准备");
    expect(tarkovPageTitle("/guides/tarkov/maps/customs")).toBe("地图");
    expect(tarkovPageTitle("/guides/tarkov/hideout")).toBe("藏身处");
    expect(tarkovPageTitle("/guides/tarkov/barters")).toBe("商人交易利润");
    expect(tarkovPageTitle("/guides/tarkov/hideout-cost")).toBe(
      "藏身处建造成本",
    );
  });
});

describe("TARKOV_ITEM_MENU_GROUPS", () => {
  it("gives every top-nav item a unique ready href", () => {
    const links = TARKOV_ITEM_MENU_GROUPS.flatMap((g) => g.items);
    expect(links.every((l) => l.status === "ready")).toBe(true);
    const hrefs = links.map((l) => l.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});
