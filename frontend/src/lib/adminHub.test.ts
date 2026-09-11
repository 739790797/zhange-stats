import { describe, expect, it } from "vitest";
import {
  ADMIN_HUBS,
  ADMIN_USERS_PATH,
  adminHubByPath,
  adminHubTabPath,
  adminMenuSelectedKey,
  adminOpsLandingPath,
  adminPageMotionKey,
} from "./adminHub";

describe("adminHubByPath", () => {
  it("maps site settings tabs", () => {
    expect(adminHubByPath("/settings/auth")?.id).toBe("site");
    expect(adminHubByPath("/settings/integrations")?.id).toBe("site");
    expect(adminHubByPath("/settings/email")?.id).toBe("site");
    expect(adminHubByPath("/settings/ocr")?.id).toBe("site");
  });

  it("maps ops and jobs tabs", () => {
    expect(adminHubByPath("/settings/runtime")?.id).toBe("ops");
    expect(adminHubByPath("/settings/rum")?.id).toBe("ops");
    expect(adminHubByPath("/settings/runtime-env")).toBeNull();
    expect(adminHubByPath("/settings/system")?.id).toBe("ops");
    expect(adminHubByPath("/settings/logs")?.id).toBe("ops");
    expect(adminHubByPath("/settings/files")?.id).toBe("ops");
    expect(adminHubByPath("/settings/task-config")?.id).toBe("jobs");
    expect(adminHubByPath("/settings/jobs")?.id).toBe("jobs");
  });

  it("maps users as a single-tab hub", () => {
    expect(adminHubByPath(ADMIN_USERS_PATH)?.id).toBe("users");
  });

  it("does not treat unknown paths as a hub", () => {
    expect(adminHubByPath("/settings")).toBeNull();
    expect(adminHubByPath("/profile")).toBeNull();
  });
});

describe("adminHubTabPath", () => {
  it("returns the matching tab path", () => {
    expect(adminHubTabPath("/settings/email")).toBe("/settings/email");
    expect(adminHubTabPath("/settings/files/extra")).toBe("/settings/files");
  });
});

describe("adminMenuSelectedKey", () => {
  it("selects hub menu keys", () => {
    expect(adminMenuSelectedKey("/settings/auth")).toBe("admin-site");
    expect(adminMenuSelectedKey("/settings/ocr")).toBe("admin-site");
    expect(adminMenuSelectedKey("/settings/runtime")).toBe("admin-ops");
    expect(adminMenuSelectedKey("/settings/system")).toBe("admin-ops");
    expect(adminMenuSelectedKey("/settings/task-config")).toBe("admin-jobs");
    expect(adminMenuSelectedKey("/settings/jobs")).toBe("admin-jobs");
  });

  it("selects users as a leaf", () => {
    expect(adminMenuSelectedKey(ADMIN_USERS_PATH)).toBe(ADMIN_USERS_PATH);
  });

  it("returns null outside admin pages", () => {
    expect(adminMenuSelectedKey("/daily")).toBeNull();
  });
});

describe("adminPageMotionKey", () => {
  it("stays on hub id when switching tabs", () => {
    expect(adminPageMotionKey("/settings/auth")).toBe("site");
    expect(adminPageMotionKey("/settings/ocr")).toBe("site");
    expect(adminPageMotionKey("/settings/runtime")).toBe("ops");
    expect(adminPageMotionKey("/settings/files")).toBe("ops");
    expect(adminPageMotionKey("/settings/jobs")).toBe("jobs");
    expect(adminPageMotionKey(ADMIN_USERS_PATH)).toBe("users");
  });

  it("uses pathname when not in a hub", () => {
    expect(adminPageMotionKey("/daily")).toBe("/daily");
  });
});

describe("adminOpsLandingPath", () => {
  it("opens system update when a release is waiting", () => {
    expect(adminOpsLandingPath(false)).toBe("/settings/runtime");
    expect(adminOpsLandingPath(true)).toBe("/settings/system");
  });
});

describe("ADMIN_HUBS", () => {
  it("keeps default paths as the first tab", () => {
    for (const hub of ADMIN_HUBS) {
      expect(hub.tabs[0]?.path).toBe(hub.path);
    }
  });

  it("names the ops hub 运行维护", () => {
    expect(ADMIN_HUBS.find((h) => h.id === "ops")?.label).toBe("运行维护");
    expect(ADMIN_HUBS.find((h) => h.id === "ops")?.tabs.map((t) => t.label)).toEqual([
      "运行环境",
      "用户等待",
      "系统更新",
      "平台日志",
      "文件管理",
    ]);
  });
});
