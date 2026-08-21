import { describe, expect, it } from "vitest";
import {
  classifyMcVersion,
  displayJoinHost,
  displayModName,
  eggMatchesLoader,
  eggOptionLabel,
  eggsForLoader,
  formatPropertyValue,
  groupMcVersions,
  inferEggLoader,
  inferSetupFromPlaybook,
  isMinecraftArchive,
  isMinecraftTextFile,
  joinHints,
  joinMinecraftPath,
  minecraftHeadUrl,
  modLoaderOfCore,
  occupancyPercent,
  overviewModTitle,
  parentMinecraftPath,
  pickSelectedEggId,
  pingBadge,
  setupSummary,
} from "@/components/guides/minecraft/minecraftUi";

describe("minecraft file paths", () => {
  it("joins and walks up directories", () => {
    expect(joinMinecraftPath("/", "eula.txt")).toBe("/eula.txt");
    expect(joinMinecraftPath("/mods", "a.jar")).toBe("/mods/a.jar");
    expect(parentMinecraftPath("/mods/config")).toBe("/mods");
    expect(parentMinecraftPath("/mods")).toBe("/");
    expect(parentMinecraftPath("/")).toBe("/");
  });

  it("detects editable text and archives", () => {
    expect(
      isMinecraftTextFile({
        name: "server.properties",
        is_file: true,
        size: 12,
        mimetype: "text/plain",
      }),
    ).toBe(true);
    expect(
      isMinecraftTextFile({
        name: "mod.jar",
        is_file: true,
        size: 10,
        mimetype: "application/java-archive",
      }),
    ).toBe(false);
    expect(isMinecraftArchive("world.tar.gz")).toBe(true);
    expect(isMinecraftArchive("eula.txt")).toBe(false);
  });
});

describe("overview helpers", () => {
  it("shows join host without port", () => {
    expect(displayJoinHost({ publicHost: "play.example.com" })).toBe(
      "play.example.com",
    );
    expect(displayJoinHost({ address: "mc.example:25565" })).toBe("mc.example");
    expect(displayJoinHost({ address: "[::1]:25565" })).toBe("::1");
    expect(displayJoinHost({ address: "play.example.com" })).toBe(
      "play.example.com",
    );
    expect(displayJoinHost({})).toBe("");
  });

  it("maps property values and occupancy", () => {
    expect(formatPropertyValue("difficulty", "hard")).toBe("困难");
    expect(formatPropertyValue("white-list", "true")).toBe("开");
    expect(formatPropertyValue("view-distance", "10")).toBe("10");
    expect(occupancyPercent(2, 20)).toBe(10);
    expect(occupancyPercent(0, 0)).toBe(0);
  });

  it("builds skin urls and ping badge", () => {
    expect(
      minecraftHeadUrl({
        name: "Steve",
        id: "f6792ad3-cbb4-4596-8296-749ee4158f97",
      }),
    ).toBe("https://mc-heads.net/avatar/f6792ad3cbb445968296749ee4158f97/32");
    expect(minecraftHeadUrl({ name: "Steve", id: "" })).toBe(
      "https://mc-heads.net/avatar/Steve/32",
    );
    expect(pingBadge(true, "stopped")).toEqual({
      kind: "online",
      text: "在线",
    });
    expect(pingBadge(false, "starting")).toEqual({
      kind: "busy",
      text: "启动中",
    });
    expect(pingBadge(false, "offline")).toEqual({
      kind: "offline",
      text: "离线",
    });
    expect(pingBadge(false, "running", true)).toEqual({
      kind: "online",
      text: "在线",
    });
  });

  it("formats mod names and join hints", () => {
    expect(displayModName({ filename: "lithium.jar", project_title: "Lithium" })).toBe(
      "Lithium",
    );
    expect(displayModName({ filename: "extra.jar" })).toBe("extra");
    expect(
      joinHints({
        versionName: "1.21.1",
        properties: { "online-mode": "true", "white-list": "true" },
      }),
    ).toEqual(["客户端请用 1.21.1", "需要正版账号", "需在白名单内"]);
  });

  it("prefers chinese title then official name", () => {
    expect(
      overviewModTitle({
        filename: "dh.jar",
        title: "Distant Horizons",
        title_zh: "视距地平线",
      }),
    ).toBe("视距地平线");
    expect(
      overviewModTitle({
        filename: "dh.jar",
        title: "Distant Horizons",
        title_zh: "DistantHorizons",
      }),
    ).toBe("Distant Horizons");
    expect(overviewModTitle({ filename: "extra.jar" })).toBe("extra");
  });
});

describe("minecraft version channels", () => {
  it("classifies release, snapshot, old and april fools", () => {
    expect(
      classifyMcVersion({ version: "1.21.1", stable: true, version_type: "release" }),
    ).toBe("release");
    expect(
      classifyMcVersion({
        version: "24w36a",
        stable: false,
        version_type: "snapshot",
      }),
    ).toBe("snapshot");
    expect(
      classifyMcVersion({
        version: "a1.1.2_01",
        version_type: "old_alpha",
      }),
    ).toBe("old");
    expect(
      classifyMcVersion({
        version: "24w14potato",
        version_type: "snapshot",
      }),
    ).toBe("fool");
    expect(classifyMcVersion({ version: "26.2", stable: true })).toBe("release");
  });

  it("picks latest release/snapshot after grouping", () => {
    const grouped = groupMcVersions([
      { version: "26.3-snapshot-9", version_type: "snapshot" },
      { version: "24w14potato", version_type: "snapshot" },
      { version: "26.2", version_type: "release" },
      { version: "1.21.1", version_type: "release" },
      { version: "b1.8.1", version_type: "old_beta" },
    ]);
    expect(grouped.latestRelease?.version).toBe("26.2");
    expect(grouped.latestSnapshot?.version).toBe("26.3-snapshot-9");
    expect(grouped.groups.fool.map((row) => row.version)).toEqual(["24w14potato"]);
    expect(grouped.groups.old.map((row) => row.version)).toEqual(["b1.8.1"]);
  });
});

describe("server setup kinds", () => {
  it("maps playbook loader to kind/core", () => {
    expect(inferSetupFromPlaybook("1.21.1", "fabric")).toEqual({
      mcVersion: "1.21.1",
      kind: "mod",
      core: "fabric",
    });
    expect(inferSetupFromPlaybook("1.20.1", "paper")).toEqual({
      mcVersion: "1.20.1",
      kind: "plugin",
      core: "paper",
    });
    expect(inferSetupFromPlaybook("1.20.1", "mohist")).toEqual({
      mcVersion: "1.20.1",
      kind: "hybrid",
      core: "mohist",
    });
    expect(inferSetupFromPlaybook("1.21.1", "")).toEqual({
      mcVersion: "1.21.1",
      kind: "",
      core: "",
    });
  });

  it("only fabric-family cores count as installed loaders", () => {
    expect(modLoaderOfCore("neoforge")).toBe("neoforge");
    expect(modLoaderOfCore("paper")).toBe("");
    expect(modLoaderOfCore("mohist")).toBe("");
    expect(setupSummary({ mcVersion: "1.21.1", kind: "mod", core: "fabric" })).toBe(
      "1.21.1 · 模组端 · Fabric",
    );
  });
});

describe("minecraft egg matching", () => {
  const fabric = { egg_id: 1, name: "Fabric", nest: "Minecraft", startup: "" };
  const forge = { egg_id: 2, name: "Forge", nest: "Minecraft", startup: "" };
  const neo = { egg_id: 3, name: "NeoForge", nest: "Minecraft", startup: "" };
  const generic = { egg_id: 4, name: "Vanilla", nest: "Minecraft", startup: "" };

  it("matches loader eggs and excludes neighbors", () => {
    expect(eggMatchesLoader(fabric, "fabric")).toBe(true);
    expect(eggMatchesLoader(forge, "fabric")).toBe(false);
    expect(eggMatchesLoader(forge, "forge")).toBe(true);
    expect(eggMatchesLoader(neo, "forge")).toBe(false);
    expect(eggMatchesLoader(neo, "neoforge")).toBe(true);
    expect(inferEggLoader(neo)).toBe("neoforge");
    expect(inferEggLoader(generic)).toBe("");
  });

  it("filters by loader and keeps the current egg visible", () => {
    const rows = eggsForLoader([fabric, forge, neo, generic], "forge", 4);
    expect(rows.map((row) => row.egg_id)).toEqual([4, 2]);
    expect(eggsForLoader([generic], "fabric").map((row) => row.egg_id)).toEqual([
      4,
    ]);
  });

  it("keeps a user pick, otherwise prefers current then recommended", () => {
    expect(
      pickSelectedEggId({
        availableIds: [1, 2, 3],
        currentId: 2,
        recommendedId: 3,
        prev: 1,
      }),
    ).toBe(1);
    expect(
      pickSelectedEggId({
        availableIds: [2, 3],
        currentId: 2,
        recommendedId: 3,
        prev: 1,
      }),
    ).toBe(2);
    expect(
      pickSelectedEggId({
        availableIds: [3],
        currentId: 2,
        recommendedId: 3,
      }),
    ).toBe(3);
  });

  it("labels current and recommended eggs", () => {
    expect(eggOptionLabel(fabric, { current: true, recommended: true })).toBe(
      "Minecraft / Fabric（当前 · 推荐）",
    );
  });
});
