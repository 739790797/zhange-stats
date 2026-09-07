import { describe, expect, it } from "vitest";
import { adminContentShell } from "./adminContentShell";

describe("adminContentShell", () => {
  it("leaves non-admin pages unconstrained", () => {
    expect(adminContentShell("/profile")).toBeNull();
    expect(adminContentShell("/steam")).toBeNull();
    expect(adminContentShell("/daily")).toBeNull();
  });

  it("uses form width for 系统管理 settings", () => {
    expect(adminContentShell("/settings/auth")).toBe("form");
    expect(adminContentShell("/settings/integrations")).toBe("form");
    expect(adminContentShell("/settings/email")).toBe("form");
    expect(adminContentShell("/settings/system")).toBe("form");
  });

  it("uses wide width for tables and task pages", () => {
    expect(adminContentShell("/settings")).toBe("wide");
    expect(adminContentShell("/settings/users")).toBe("wide");
    expect(adminContentShell("/settings/jobs")).toBe("wide");
    expect(adminContentShell("/settings/task-config")).toBe("wide");
    expect(adminContentShell("/settings/logs")).toBe("wide");
  });

  it("uses wide width for Minecraft guide", () => {
    expect(adminContentShell("/guides/minecraft")).toBe("wide");
    expect(adminContentShell("/guides/minecraft/extra")).toBe("wide");
  });

  it("uses flush shell for tavern feed and posts", () => {
    expect(adminContentShell("/tavern")).toBe("flush");
    expect(adminContentShell("/tavern/welcome")).toBe("flush");
  });

  it("uses wide width for tavern admin and default card for editor", () => {
    expect(adminContentShell("/tavern/admin")).toBe("wide");
    expect(adminContentShell("/tavern/write")).toBeNull();
    expect(adminContentShell("/tavern/write/3")).toBeNull();
  });
});
