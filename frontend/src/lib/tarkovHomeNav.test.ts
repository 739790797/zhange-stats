import { describe, expect, it } from "vitest";
import { ITEMS_BASE_PATH } from "./tarkovItemTypes";
import {
  TARKOV_BOSSES,
  TARKOV_OTHER_MOBS,
  TARKOV_HOME_BOSSES,
  buildTarkovBossNavGroups,
  TARKOV_HOME_ITEMS,
  TARKOV_HOME_ITEM_GROUPS,
  TARKOV_HOME_TRADERS,
  TARKOV_ITEM_MENU_GROUPS,
  TARKOV_MAPS,
  TARKOV_PROGRESSION,
  TARKOV_ME_NAV,
  TARKOV_RAID_PREP_NAV,
  TARKOV_TOOLS,
  resolveTarkovMeTab,
  tarkovMeHref,
  tarkovHideoutHref,
  tarkovKeyPackHref,
  tarkovWorkbenchHref,
  TARKOV_HOME_PATH,
  TARKOV_ADMIN_NAV,
  TARKOV_TOP_NAV,
  isTarkovAdminPath,
  parseTarkovMaintainMode,
  tarkovMapMaintainHref,
  tarkovMapsMaintainHref,
  tarkovRaidPulseDemoHref,
  TARKOV_TRADERS,
  isTarkovHomePath,
  bossPortraitUrl,
  traderIconUrl,
  traderPortraitUrl,
  buildHomeSearchIndex,
  buildSiteSearchSections,
  filterHomeSearch,
  isTarkovTopNavActive,
  tarkovMapMarkByName,
  tarkovPageTitle,
  tarkovGuideShellFills,
  textMatchesQuery,
  traderDisplayName,
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

  it("finds gunsmith workbench", () => {
    expect(filterHomeSearch("改枪", index).some((h) => h.id === "workbench")).toBe(
      true,
    );
    expect(
      filterHomeSearch("gunsmith", index).some((h) => h.id === "workbench"),
    ).toBe(true);
  });

  it("finds bullets, ammo packs and melee on handbook ammo/guns", () => {
    expect(filterHomeSearch("子弹", index).some((h) => h.id === "ammo")).toBe(
      true,
    );
    expect(
      filterHomeSearch("弹药包", index).some((h) => h.id === "ammo"),
    ).toBe(true);
    expect(filterHomeSearch("近战", index).some((h) => h.id === "guns")).toBe(
      true,
    );
  });

  it("sends pistol grips and suppressors to weapon mods", () => {
    expect(
      filterHomeSearch("手枪式握把", index).some((h) => h.id === "weapon-mods"),
    ).toBe(true);
    expect(
      filterHomeSearch("消音器", index).some((h) => h.id === "weapon-mods"),
    ).toBe(true);
    expect(
      filterHomeSearch("suppressor", index).some((h) => h.id === "weapon-mods"),
    ).toBe(true);
    expect(filterHomeSearch("消音器", index).some((h) => h.id === "suppressors")).toBe(
      false,
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

  it("finds traders by old nicknames but labels stay english", () => {
    expect(filterHomeSearch("大妈", index).some((h) => h.id === "therapist")).toBe(
      true,
    );
    expect(TARKOV_TRADERS.find((row) => row.id === "therapist")?.label).toBe(
      "Therapist",
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
    expect(
      filterHomeSearch("联机大厅", index).some((h) => h.id === "raid-prep"),
    ).toBe(true);
  });

  it("finds task tree inside 个人中心", () => {
    expect(
      filterHomeSearch("任务树", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("任务管理", index).some((h) => h.id === "me"),
    ).toBe(true);
  });

  it("finds key packs inside 个人中心", () => {
    expect(
      filterHomeSearch("钥匙分类", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("钥匙用途", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(filterHomeSearch("打包", index).some((h) => h.id === "me")).toBe(
      true,
    );
  });

  it("finds game logs inside 个人中心", () => {
    expect(
      filterHomeSearch("游戏日志", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("目录绑定", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("application", index).some((h) => h.id === "me"),
    ).toBe(true);
  });

  it("finds hideout inside 个人中心", () => {
    expect(
      filterHomeSearch("藏身处", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("hideout", index).some((h) => h.id === "me"),
    ).toBe(true);
  });

  it("finds 3x4 collection inside 个人中心", () => {
    expect(
      filterHomeSearch("3×4收集", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("收集者", index).some((h) => h.id === "me"),
    ).toBe(true);
    expect(
      filterHomeSearch("收藏家", index).some((h) => h.id === "me"),
    ).toBe(true);
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
            extra: "Therapist",
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

describe("buildTarkovBossNavGroups", () => {
  it("keeps a 非 Boss column in the static fallback and from catalog rows", () => {
    const fallback = buildTarkovBossNavGroups();
    expect(fallback.map((row) => row.id)).toEqual(["boss", "other"]);
    expect(fallback[1]?.items.map((row) => row.id)).toContain("exusecfree");
    const live = buildTarkovBossNavGroups([
      { id: "bossKilla", slug: "killa", name: "Killa" },
      { id: "exUsecFree", slug: "exusecfree", name: "游荡者", maps_label: "灯塔" },
      { id: "ExUsec", slug: "rogue", name: "游荡者", maps_label: "破冰者" },
      { id: "vsRF", slug: "vs-rf", name: "俄军" },
      { id: "followerBigPipe", slug: "big-pipe", name: "Big Pipe", parent_ids: ["bossKnight"] },
    ]);
    expect(live.map((row) => row.id)).toEqual(["boss", "other"]);
    expect(live[0]?.items.map((row) => row.id)).toEqual(["bossKilla"]);
    expect(live[1]?.items.map((row) => row.label)).toEqual([
      "游荡者（灯塔）",
      "游荡者（破冰者）",
      "俄军",
    ]);
  });
});

describe("TARKOV_BOSSES", () => {
  it("uses tarkov.dev PvP spawn rates and includes Kollontay", () => {
    const byId = Object.fromEntries(TARKOV_BOSSES.map((b) => [b.id, b]));
    expect(byId.reshala).toMatchObject({
      map: "海关",
      spawn: "45%",
      guards: "×4",
      status: "ready",
    });
    expect(byId.killa).toMatchObject({ map: "立交桥", spawn: "45%", guards: "—" });
    expect(byId.glukhar).toMatchObject({
      map: "储备站",
      spawn: "30%",
      guards: "×6",
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
    expect(traderPortraitUrl("54cb50c76803fa8b248b4571")).toBe(
      "https://tarkov.dev/images/traders/prapor-portrait.png",
    );
    expect(traderPortraitUrl("Prapor")).toBe(
      "https://tarkov.dev/images/traders/prapor-portrait.png",
    );
    expect(traderPortraitUrl("aaaaaaaaaaaaaaaaaaaaaaaa")).toBe("");
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

describe("tarkovMapMarkByName", () => {
  it("resolves home labels and variant names to the same icons", () => {
    expect(tarkovMapMarkByName("海关")).toMatchObject({
      id: "customs",
      label: "海关",
    });
    expect(tarkovMapMarkByName("夜间工厂")?.id).toBe("night-factory");
    expect(tarkovMapMarkByName("夜间工厂")?.icon).toBe(
      TARKOV_MAPS.find((row) => row.id === "factory")?.icon,
    );
    expect(tarkovMapMarkByName("实验室 (Dark)")).toMatchObject({
      id: "lab",
      label: "实验室 (Dark)",
    });
    expect(tarkovMapMarkByName("中心区 21+")?.id).toBe("ground-zero");
    expect(tarkovMapMarkByName("未知地点")).toEqual({
      id: "",
      label: "未知地点",
      icon: "",
    });
    expect(tarkovMapMarkByName("")).toBeNull();
  });
});

describe("TARKOV_HOME_ITEMS", () => {
  it("uses handbook roots on the home grid and top-nav", () => {
    expect(TARKOV_HOME_ITEM_GROUPS.map((g) => g.id)).toEqual(["handbook"]);
    expect(TARKOV_HOME_ITEMS.map((i) => i.id)).toEqual([
      "battle-pass",
      "quest-items",
      "money",
      "maps",
      "special-equipment",
      "info-items",
      "keys",
      "meds",
      "provisions",
      "ammo",
      "guns",
      "weapon-mods",
      "gear",
      "barter",
    ]);
    expect(TARKOV_ITEM_MENU_GROUPS.flatMap((g) => g.items.map((i) => i.id))).toEqual(
      TARKOV_HOME_ITEMS.map((i) => i.id),
    );
  });

  it("uses handbook category icons", () => {
    expect(TARKOV_HOME_ITEMS.every((item) => item.icon.includes("handbook-category-"))).toBe(
      true,
    );
  });
});

describe("isTarkovHomePath", () => {
  it("matches the tarkov home route including a trailing slash", () => {
    expect(isTarkovHomePath(TARKOV_HOME_PATH)).toBe(true);
    expect(isTarkovHomePath(`${TARKOV_HOME_PATH}/`)).toBe(true);
    expect(isTarkovHomePath(`${TARKOV_HOME_PATH}/maps`)).toBe(false);
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

describe("TARKOV_ADMIN_NAV", () => {
  it("keeps maintain links out of the public top nav", () => {
    expect(TARKOV_TOP_NAV.map((item) => item.id)).not.toContain("admin");
    expect(TARKOV_ADMIN_NAV).toMatchObject({
      id: "admin",
      label: "管理",
    });
    expect(TARKOV_ADMIN_NAV.groups?.[0]?.items.map((item) => item.id)).toEqual([
      "info",
      "pulse-demo",
    ]);
    expect(tarkovMapsMaintainHref()).toBe("/guides/tarkov/maps?maintain=info");
    expect(tarkovMapMaintainHref("customs", "info")).toBe(
      "/guides/tarkov/maps/customs?maintain=info",
    );
    expect(parseTarkovMaintainMode("info")).toBe("info");
    expect(parseTarkovMaintainMode("places")).toBe("info");
    expect(parseTarkovMaintainMode("nope")).toBe("");
    expect(isTarkovAdminPath("/guides/tarkov/maps", "maintain=info")).toBe(true);
    expect(
      isTarkovAdminPath("/guides/tarkov/maps/customs", "maintain=places"),
    ).toBe(true);
    expect(isTarkovAdminPath("/guides/tarkov/maps")).toBe(false);
    expect(isTarkovAdminPath(tarkovRaidPulseDemoHref())).toBe(true);
    const index = buildHomeSearchIndex();
    expect(index.some((hit) => hit.label === "地图信息")).toBe(false);
    expect(index.some((hit) => hit.id === "pulse-demo")).toBe(false);
  });
});

describe("TARKOV_TOP_NAV", () => {
  it("nests tasks under progression instead of a top-level item", () => {
    expect(TARKOV_TOP_NAV.map((i) => i.id)).not.toContain("tasks");
    expect(TARKOV_TOP_NAV.map((i) => i.id)).not.toContain("workbench");
    expect(TARKOV_TOP_NAV.find((i) => i.id === "progression")?.href).toBe(
      "/guides/tarkov/tasks",
    );
    expect(TARKOV_PROGRESSION[0]).toMatchObject({
      id: "tasks",
      label: "任务",
      href: "/guides/tarkov/tasks",
      status: "ready",
    });
    expect(TARKOV_PROGRESSION.find((p) => p.id === "hideout")).toBeUndefined();
    expect(TARKOV_PROGRESSION.find((p) => p.id === "raid-prep")).toBeUndefined();
    expect(TARKOV_TOP_NAV.find((i) => i.id === "bosses")?.groups?.map((g) => g.id)).toEqual(
      ["boss", "other"],
    );
    expect(TARKOV_OTHER_MOBS.map((row) => row.id)).toEqual([
      "rogue",
      "exusecfree",
      "raider",
    ]);
    expect(TARKOV_PROGRESSION.find((p) => p.id === "loot-tiers")).toBeUndefined();
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
      chinese: "",
      label: "Prapor",
    });
    expect(TARKOV_TRADERS.find((t) => t.id === "ref")).toMatchObject({
      chinese: "",
      label: "Ref",
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

describe("traderDisplayName", () => {
  it("uses english cards and strips leftover nicknames", () => {
    expect(traderDisplayName("prapor", "ignored")).toBe("Prapor");
    expect(traderDisplayName("unknown", "Skier（走私客）")).toBe("Skier");
    expect(traderDisplayName("", "Therapist（大妈）")).toBe("Therapist");
  });
});

describe("TARKOV_TOOLS", () => {
  it("keeps ammo first after raid prep and 个人中心 left the rail", () => {
    expect(TARKOV_TOOLS.map((item) => item.id)).not.toContain("raid-prep");
    expect(TARKOV_TOOLS.map((item) => item.id)).not.toContain("me");
    expect(TARKOV_RAID_PREP_NAV).toMatchObject({
      id: "raid-prep",
      label: "联机大厅",
      href: "/guides/tarkov",
      status: "ready",
    });
    expect(TARKOV_TOOLS.map((item) => item.id)).not.toContain("key-packs");
    expect(TARKOV_TOOLS.map((item) => item.id)).not.toContain("game-logs");
    expect(TARKOV_TOOLS[0]).toMatchObject({
      id: "ammo-chart",
      label: "弹药图表筛选器",
      href: `${ITEMS_BASE_PATH}/ammo`,
      status: "ready",
    });
    expect(TARKOV_ME_NAV).toMatchObject({
      id: "me",
      href: "/guides/tarkov/me?tab=tasks",
      status: "ready",
    });
    expect(TARKOV_TOOLS[1]).toMatchObject({
      id: "workbench",
      label: "枪械工作台",
      href: "/guides/tarkov/workbench",
      status: "ready",
    });
    expect(TARKOV_TOOLS.map((item) => item.id)).toEqual([
      "ammo-chart",
      "workbench",
    ]);
  });
});

describe("tarkovPageTitle", () => {
  it("uses handbook labels on item type paths", () => {
    expect(tarkovPageTitle("/guides/tarkov")).toBe("逃离塔科夫");
    expect(tarkovPageTitle("/guides/tarkov/items")).toBe("物品");
    expect(tarkovPageTitle("/guides/tarkov/items/meds")).toBe("医疗物品");
    expect(tarkovPageTitle("/guides/tarkov/tasks/abc")).toBe("任务");
    expect(tarkovPageTitle("/guides/tarkov/raid-prep")).toBe("联机大厅");
    expect(tarkovPageTitle("/guides/tarkov/raid-prep/pulse-demo")).toBe(
      "测试房间",
    );
    expect(tarkovPageTitle("/guides/tarkov/maps", "maintain=info")).toBe(
      "地图信息",
    );
    expect(tarkovPageTitle("/guides/tarkov/maps/customs", "maintain=nav")).toBe(
      "地图信息",
    );
    expect(tarkovPageTitle("/guides/tarkov/maps/customs")).toBe("地图");
    expect(tarkovPageTitle("/guides/tarkov/hideout")).toBe("个人中心");
    expect(tarkovPageTitle("/guides/tarkov/workbench")).toBe("枪械工作台");
    expect(tarkovPageTitle("/guides/tarkov/workbench/abc")).toBe("枪械工作台");
    expect(tarkovPageTitle("/guides/tarkov/me")).toBe("个人中心");
    expect(tarkovPageTitle("/guides/tarkov/key-packs")).toBe("个人中心");
    expect(tarkovPageTitle("/guides/tarkov/game-logs")).toBe("个人中心");
    expect(tarkovPageTitle("/guides/tarkov/collection")).toBe("个人中心");
  });
});

describe("tarkovGuideShellFills", () => {
  it("fills raid-prep rooms so the map has a definite height", () => {
    expect(tarkovGuideShellFills("/guides/tarkov/raid-prep")).toBe(true);
    expect(
      tarkovGuideShellFills("/guides/tarkov/raid-prep/rooms/cv4i6efn"),
    ).toBe(true);
    expect(tarkovGuideShellFills("/guides/tarkov/raid-prep/pulse-demo")).toBe(
      true,
    );
    expect(tarkovGuideShellFills("/guides/tarkov/workbench")).toBe(true);
    expect(tarkovGuideShellFills("/guides/tarkov/workbench/ak74")).toBe(true);
    expect(tarkovGuideShellFills("/guides/tarkov/me", "collection")).toBe(true);
    expect(tarkovGuideShellFills("/guides/tarkov/me", "tasks")).toBe(false);
    expect(tarkovGuideShellFills("/guides/tarkov/maps")).toBe(false);
    expect(tarkovGuideShellFills("/guides/tarkov/maps/customs")).toBe(true);
  });
});

describe("tarkovWorkbenchHref", () => {
  it("builds workbench hrefs with optional gunsmith query", () => {
    expect(tarkovWorkbenchHref()).toBe("/guides/tarkov/workbench");
    expect(tarkovWorkbenchHref("ak74")).toBe("/guides/tarkov/workbench/ak74");
    expect(tarkovWorkbenchHref(undefined, { taskId: "gs" })).toBe(
      "/guides/tarkov/workbench?task=gs",
    );
    expect(
      tarkovWorkbenchHref("ak74", { taskId: "gs", objectiveId: "o1" }),
    ).toBe("/guides/tarkov/workbench/ak74?task=gs&obj=o1");
  });
});

describe("tarkov me tabs", () => {
  it("defaults unknown tabs to keys and builds hrefs", () => {
    expect(resolveTarkovMeTab(null)).toBe("tasks");
    expect(resolveTarkovMeTab("tasks")).toBe("tasks");
    expect(resolveTarkovMeTab("keys")).toBe("keys");
    expect(resolveTarkovMeTab("collection")).toBe("collection");
    expect(resolveTarkovMeTab("hideout")).toBe("hideout");
    expect(resolveTarkovMeTab("logs")).toBe("logs");
    expect(resolveTarkovMeTab("nope")).toBe("tasks");
    expect(tarkovMeHref("logs")).toBe("/guides/tarkov/me?tab=logs");
    expect(tarkovMeHref("collection")).toBe("/guides/tarkov/me?tab=collection");
    expect(tarkovMeHref("hideout")).toBe("/guides/tarkov/me?tab=hideout");
    expect(tarkovHideoutHref()).toBe("/guides/tarkov/me?tab=hideout");
    expect(tarkovHideoutHref("workbench")).toBe(
      "/guides/tarkov/me?tab=hideout&station=workbench",
    );
    expect(tarkovMeHref("keys")).toBe("/guides/tarkov/me?tab=keys");
    expect(tarkovMeHref()).toBe("/guides/tarkov/me?tab=tasks");
    expect(tarkovKeyPackHref({ q: "Dorm 114", map: "customs" })).toBe(
      "/guides/tarkov/me?tab=keys&map=customs&q=Dorm+114",
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
