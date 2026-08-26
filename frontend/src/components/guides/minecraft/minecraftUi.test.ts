import { describe, expect, it } from "vitest";
import {
  displayJoinHost,
  displayModName,
  formatPropertyValue,
  isMinecraftArchive,
  isMinecraftTextFile,
  joinHints,
  joinMinecraftPath,
  loaderLabel,
  minecraftHeadUrl,
  normalizeMinecraftPath,
  occupancyPercent,
  overviewModTitle,
  parentMinecraftPath,
  parentMinecraftPathWithin,
  isMinecraftPathWithin,
  pingBadge,
} from "@/components/guides/minecraft/minecraftUi";

describe("minecraft file paths", () => {
  it("joins and walks up directories", () => {
    expect(joinMinecraftPath("/", "eula.txt")).toBe("/eula.txt");
    expect(joinMinecraftPath("/mods", "a.jar")).toBe("/mods/a.jar");
    expect(parentMinecraftPath("/mods/config")).toBe("/mods");
    expect(parentMinecraftPath("/mods")).toBe("/");
    expect(parentMinecraftPath("/")).toBe("/");
  });

  it("keeps relative paths inside a config root", () => {
    expect(normalizeMinecraftPath("/config/chunky/../chunky")).toBe(
      "/config/chunky",
    );
    expect(isMinecraftPathWithin("/config/chunky", "/config/chunky/config.yml")).toBe(
      true,
    );
    expect(isMinecraftPathWithin("/config/chunky", "/config/other.yml")).toBe(
      false,
    );
    expect(parentMinecraftPathWithin("/config/chunky", "/config/chunky/tasks")).toBe(
      "/config/chunky",
    );
    expect(parentMinecraftPathWithin("/config/chunky", "/config/chunky")).toBe(
      "/config/chunky",
    );
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

  it("labels loaders including paper-family aliases", () => {
    expect(loaderLabel("neoforge")).toBe("NeoForge");
    expect(loaderLabel("paper")).toBe("Paper");
    expect(loaderLabel("")).toBe("—");
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
