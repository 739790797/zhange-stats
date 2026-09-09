import { describe, expect, it } from "vitest";
import type { RuntimeHealthService } from "@/api/runtimeHealthApi";
import {
  healthHint,
  healthMeta,
  pickHealthServices,
  RUNTIME_NOTE_IDS,
  RUNTIME_STATUS_IDS,
  runtimeNoteLabel,
} from "./runtimeHealth";

function item(
  id: string,
  extra: Partial<RuntimeHealthService> = {},
): RuntimeHealthService {
  return {
    id,
    name: id,
    status: "ok",
    detail: "",
    ...extra,
  };
}

describe("pickHealthServices", () => {
  it("keeps requested order and skips missing ids", () => {
    const services = [item("smtp"), item("mysql"), item("app")];
    expect(
      pickHealthServices(services, ["mysql", "redis", "smtp"]).map((s) => s.id),
    ).toEqual(["mysql", "smtp"]);
  });

  it("returns empty when the snapshot has no services", () => {
    expect(pickHealthServices(undefined, RUNTIME_STATUS_IDS)).toEqual([]);
    expect(pickHealthServices([], RUNTIME_STATUS_IDS)).toEqual([]);
  });
});

describe("healthMeta / healthHint", () => {
  it("maps known statuses and falls back for unknown", () => {
    expect(healthMeta("ok").label).toBe("正常");
    expect(healthMeta("skipped").label).toBe("未启用");
    expect(healthMeta("weird").label).toBe("weird");
  });

  it("joins detail and rounded latency", () => {
    expect(healthHint({ detail: "SELECT 1 ok", latency_ms: 1.4 })).toBe(
      "SELECT 1 ok · 1ms",
    );
    expect(healthHint({ detail: "未配置 SMTP" })).toBe("未配置 SMTP");
    expect(healthHint({ detail: "", latency_ms: null })).toBe("");
  });
});

describe("runtime notes", () => {
  it("does not treat env / XFF as status chips", () => {
    expect(RUNTIME_STATUS_IDS).not.toContain("app_env");
    expect(RUNTIME_STATUS_IDS).not.toContain("xff");
    expect(RUNTIME_STATUS_IDS).not.toContain("app");
    expect([...RUNTIME_NOTE_IDS]).toEqual(["app_env", "xff"]);
  });

  it("uses plain labels for env and visitor IP", () => {
    expect(runtimeNoteLabel(item("app_env", { name: "运行环境" }))).toBe(
      "运行环境",
    );
    expect(runtimeNoteLabel(item("xff", { name: "X-Forwarded-For" }))).toBe(
      "访客 IP",
    );
  });
});
