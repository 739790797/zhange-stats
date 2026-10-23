import { describe, expect, it } from "vitest";
import {
  bindTokenErrorMessage,
  checkinDialogTitle,
  hasCredentialRowError,
  isBindTokenBroken,
  isCredentialFailureMessage,
} from "./checkinStatus";

describe("checkinDialogTitle", () => {
  it("uses non-scolding copy for already signed", () => {
    expect(checkinDialogTitle("already")).toBe("今日已签到");
    expect(checkinDialogTitle("success")).toBe("签到成功");
  });
});

describe("isCredentialFailureMessage", () => {
  it("matches login expired copy", () => {
    expect(isCredentialFailureMessage("登录已失效，请重新绑定")).toBe(true);
    expect(isCredentialFailureMessage("网络超时")).toBe(false);
  });
});

describe("isBindTokenBroken", () => {
  it("requires bound", () => {
    expect(isBindTokenBroken({ bound: false, token_ok: false })).toBe(false);
    expect(isBindTokenBroken(null)).toBe(false);
  });

  it("uses token_ok only (row errors stay on the list)", () => {
    expect(isBindTokenBroken({ bound: true, token_ok: false })).toBe(true);
    expect(isBindTokenBroken({ bound: true, token_ok: true })).toBe(false);
    expect(
      isBindTokenBroken({
        bound: true,
        token_ok: true,
        today_results: [
          { status: "error", message: "登录已失效，请重新绑定" },
        ],
      }),
    ).toBe(false);
  });
});

describe("hasCredentialRowError", () => {
  it("detects credential failure rows", () => {
    expect(
      hasCredentialRowError({
        today_results: [
          { status: "pending", message: "今日未签到" },
          { status: "error", message: "登录已失效，请重新绑定" },
        ],
      }),
    ).toBe(true);
    expect(
      hasCredentialRowError({
        today_results: [{ status: "error", message: "网络超时" }],
      }),
    ).toBe(false);
  });
});

describe("bindTokenErrorMessage", () => {
  it("prefers token_error then row message", () => {
    expect(
      bindTokenErrorMessage({
        bound: true,
        token_error: "Cookie 无效，请重新绑定",
        today_results: [{ status: "error", message: "登录已失效，请重新绑定" }],
      }),
    ).toBe("Cookie 无效，请重新绑定");
    expect(
      bindTokenErrorMessage({
        bound: true,
        today_results: [{ status: "error", message: "登录已失效，请重新绑定" }],
      }),
    ).toBe("登录已失效，请重新绑定");
  });
});
