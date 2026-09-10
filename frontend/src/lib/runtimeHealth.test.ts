import { describe, expect, it } from "vitest";
import type { RuntimeHealthService } from "@/api/runtimeHealthApi";
import {
  healthById,
  healthHint,
  healthMeta,
  pickHealthServices,
  RUNTIME_STATUS_IDS,
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
    const services = [item("redis"), item("database"), item("smtp")];
    expect(
      pickHealthServices(services, ["database", "redis"]).map((s) => s.id),
    ).toEqual(["database", "redis"]);
  });

  it("returns empty when the snapshot has no services", () => {
    expect(pickHealthServices(undefined, RUNTIME_STATUS_IDS)).toEqual([]);
    expect(pickHealthServices([], RUNTIME_STATUS_IDS)).toEqual([]);
  });
});

describe("healthById", () => {
  it("finds a service by id", () => {
    expect(healthById([item("database"), item("redis")], "redis")?.id).toBe(
      "redis",
    );
    expect(healthById([item("database")], "smtp")).toBeUndefined();
    expect(healthById(undefined, "database")).toBeUndefined();
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
    expect(healthHint({ detail: "未配置 REDIS_URL" })).toBe("未配置 REDIS_URL");
    expect(healthHint({ detail: "", latency_ms: null })).toBe("");
  });
});

describe("runtime status ids", () => {
  it("only treats database and redis as local deps", () => {
    expect([...RUNTIME_STATUS_IDS]).toEqual(["database", "redis"]);
    expect(RUNTIME_STATUS_IDS).not.toContain("smtp");
    expect(RUNTIME_STATUS_IDS).not.toContain("scheduler");
    expect(RUNTIME_STATUS_IDS).not.toContain("app_env");
    expect(RUNTIME_STATUS_IDS).not.toContain("xff");
  });
});
