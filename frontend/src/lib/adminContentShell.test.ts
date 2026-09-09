import { describe, expect, it } from "vitest";
import { adminContentShell } from "./adminContentShell";

describe("adminContentShell", () => {
  it("leaves non-admin pages unconstrained", () => {
    expect(adminContentShell("/profile")).toBeNull();
    expect(adminContentShell("/steam")).toBeNull();
    expect(adminContentShell("/daily")).toBeNull();
  });

  it("uses wide width for all /settings pages", () => {
    expect(adminContentShell("/settings")).toBe("wide");
    expect(adminContentShell("/settings/auth")).toBe("wide");
    expect(adminContentShell("/settings/integrations")).toBe("wide");
    expect(adminContentShell("/settings/email")).toBe("wide");
    expect(adminContentShell("/settings/ocr")).toBe("wide");
    expect(adminContentShell("/settings/users")).toBe("wide");
    expect(adminContentShell("/settings/runtime")).toBe("wide");
    expect(adminContentShell("/settings/system")).toBe("wide");
    expect(adminContentShell("/settings/jobs")).toBe("wide");
    expect(adminContentShell("/settings/task-config")).toBe("wide");
    expect(adminContentShell("/settings/logs")).toBe("wide");
    expect(adminContentShell("/settings/files")).toBe("wide");
  });

  it("uses wide width for Minecraft guide", () => {
    expect(adminContentShell("/guides/minecraft")).toBe("wide");
    expect(adminContentShell("/guides/minecraft/extra")).toBe("wide");
  });

  it("uses flush shell for tavern feed, posts, and editor", () => {
    expect(adminContentShell("/")).toBe("flush");
    expect(adminContentShell("/tavern")).toBe("flush");
    expect(adminContentShell("/tavern/welcome")).toBe("flush");
    expect(adminContentShell("/tavern/write")).toBe("flush");
    expect(adminContentShell("/tavern/write/3")).toBe("flush");
  });

  it("uses wide width for tavern admin", () => {
    expect(adminContentShell("/tavern/admin")).toBe("wide");
  });
});
