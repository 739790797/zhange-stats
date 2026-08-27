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
  relativeMinecraftPathWithin,
  configRelPath,
  isMinecraftPinnableFile,
  modPresetStatusMessage,
  pingBadge,
  minecraftUploadJobLabel,
  minecraftUploadProgressPercent,
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
    expect(isMinecraftPathWithin("/", "/plugins/Chunky/config.yml")).toBe(true);
    expect(parentMinecraftPathWithin("/", "/config")).toBe("/");
  });

  it("turns a picked path into a config-relative filename", () => {
    expect(
      relativeMinecraftPathWithin(
        "/config/chunky",
        "/config/chunky/tasks/config.json",
      ),
    ).toBe("tasks/config.json");
    expect(configRelPath("/config/chunky", "config.json")).toBe("config.json");
    expect(configRelPath("/config/chunky", "/config/chunky/core.conf")).toBe(
      "core.conf",
    );
    expect(configRelPath("/config/chunky", "../server.properties")).toBe("");
  });

  it("labels key-preset status", () => {
    expect(modPresetStatusMessage({ status: "missing_files" })).toBe(
      "还没有指定配置目录，请先在「编辑配置」里选择。",
    );
    expect(
      modPresetStatusMessage({
        status: "missing_files",
        directories: ["/config/chunky"],
      }),
    ).toBe("未找到配置文件");
    expect(
      modPresetStatusMessage({
        status: "mismatch",
        directories: ["/config/chunky"],
        diffs: [{ key: "a" }, { key: "b" }],
      }),
    ).toBe("2 项与预设不一致");
    expect(isMinecraftPinnableFile("core.conf")).toBe(true);
    expect(isMinecraftPinnableFile("mod.jar")).toBe(false);
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

describe("minecraft upload progress copy", () => {
  it("labels each phase", () => {
    expect(minecraftUploadJobLabel("uploading", 42)).toBe("上传中 42%");
    expect(minecraftUploadJobLabel("uploading", null)).toBe("上传中…");
    expect(minecraftUploadJobLabel("writing", 100)).toBe("正在写入服务器…");
    expect(minecraftUploadJobLabel("done", 100)).toBe("已上传");
    expect(minecraftUploadJobLabel("error", 30)).toBe("上传失败");
  });

  it("falls back progress bar percent when total is unknown", () => {
    expect(minecraftUploadProgressPercent("uploading", null)).toBe(0);
    expect(minecraftUploadProgressPercent("writing", null)).toBe(100);
    expect(minecraftUploadProgressPercent("uploading", 18)).toBe(18);
  });
});
