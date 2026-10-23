import { describe, expect, it } from "vitest";
import { isProductionEnv, runtimeEnvRiskNotes, type RuntimeEnvFlags } from "./runtimeEnvRisks";

const DEV: RuntimeEnvFlags = {
  app_env: "development",
  csp_enforce: false,
  trust_x_forwarded_for: false,
  rate_limit_enabled: true,
};

describe("isProductionEnv", () => {
  it("accepts the backend's production aliases", () => {
    expect(isProductionEnv("production")).toBe(true);
    expect(isProductionEnv(" Prod ")).toBe(true);
    expect(isProductionEnv("development")).toBe(false);
    expect(isProductionEnv(undefined)).toBe(false);
  });
});

describe("runtimeEnvRiskNotes", () => {
  it("needs no confirmation when nothing risky is switched on", () => {
    expect(runtimeEnvRiskNotes(DEV, { ...DEV })).toEqual([]);
    expect(runtimeEnvRiskNotes(DEV, {})).toEqual([]);
  });

  it("warns once per risky switch", () => {
    const notes = runtimeEnvRiskNotes(DEV, {
      app_env: "production",
      csp_enforce: true,
      trust_x_forwarded_for: true,
      rate_limit_enabled: false,
    });
    expect(notes).toHaveLength(4);
    expect(notes[0]).toContain("production");
    expect(notes[1]).toContain("CSP");
    expect(notes[2]).toContain("X-Forwarded-For");
    expect(notes[3]).toContain("限流");
  });

  it("ignores settings that were already in the risky state", () => {
    const prod: RuntimeEnvFlags = {
      app_env: "prod",
      csp_enforce: true,
      trust_x_forwarded_for: true,
      rate_limit_enabled: false,
    };
    expect(
      runtimeEnvRiskNotes(prod, {
        app_env: "production",
        csp_enforce: true,
        trust_x_forwarded_for: true,
        rate_limit_enabled: false,
      }),
    ).toEqual([]);
  });

  it("skips fields left out of the payload (environment-locked)", () => {
    expect(runtimeEnvRiskNotes(DEV, { csp_enforce: false })).toEqual([]);
  });
});
