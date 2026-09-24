import { describe, expect, it } from "vitest";
import { appHomePhase } from "./appHomeSession";

describe("appHomePhase", () => {
  it("sends 401 to the login page", () => {
    expect(appHomePhase(401)).toBe("out");
  });

  it("keeps a successful session on the demo home", () => {
    expect(appHomePhase(200)).toBe("in");
  });

  it("does not treat a network or server failure as logged out", () => {
    expect(appHomePhase(undefined)).toBe("error");
    expect(appHomePhase(500)).toBe("error");
    expect(appHomePhase(403)).toBe("error");
  });
});
