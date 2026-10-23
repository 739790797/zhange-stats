import { describe, expect, it } from "vitest";
import { oauthFailureMessage } from "./oauthReturnReason";

describe("oauthFailureMessage", () => {
  it("maps known reason codes to fixed copy per flow", () => {
    expect(oauthFailureMessage("steam_bind", "already_bound")).toBe(
      "Steam 绑定失败：该 Steam 账号已绑定在其他成员上",
    );
    expect(oauthFailureMessage("qq_bind", "already_bound")).toBe(
      "QQ 绑定失败：该 QQ 账号已绑定在其他成员上",
    );
    expect(oauthFailureMessage("qq_login", "upstream_error")).toBe(
      "QQ 登录失败：QQ 接口暂时不可用，请稍后重试",
    );
    expect(oauthFailureMessage("steam_bind", "steam_private")).toContain("公开个人资料");
  });

  it("treats cancel as a neutral notice", () => {
    expect(oauthFailureMessage("qq_login", "cancelled")).toBe("已取消 QQ 登录");
    expect(oauthFailureMessage("steam_bind", "cancelled")).toBe("已取消 Steam 绑定");
  });

  it("falls back to generic copy for missing or unknown codes", () => {
    expect(oauthFailureMessage("qq_login", null)).toBe("QQ 登录失败，请重试");
    expect(oauthFailureMessage("qq_bind", "")).toBe("绑定失败，请重试");
    expect(oauthFailureMessage("steam_bind", "bind_failed")).toBe("绑定失败，请重试");
  });

  it("never echoes the raw parameter text", () => {
    const injected = "<img src=x onerror=alert(1)> 请联系 evil.example";
    expect(oauthFailureMessage("steam_bind", injected)).toBe("绑定失败，请重试");
    expect(oauthFailureMessage("qq_login", injected)).not.toContain("evil");
  });
});
