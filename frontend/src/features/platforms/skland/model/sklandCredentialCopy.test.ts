import { describe, expect, it } from "vitest";
import {
  SKLAND_APP_LOGOUT_HINT,
  sklandBindDescription,
} from "./sklandCredentialCopy";

describe("sklandBindDescription", () => {
  it("always mentions not logging out of the app", () => {
    expect(sklandBindDescription(false)).toBe(SKLAND_APP_LOGOUT_HINT);
    expect(sklandBindDescription(true)).toContain("请重新绑定后再试");
    expect(sklandBindDescription(true)).toContain("退出登录");
  });
});
