import {
  TAVERN_ADMIN_PATH,
  TAVERN_PATH,
  TAVERN_WELCOME_SLUG,
  TAVERN_WRITE_PATH,
  tavernArticlePath,
  tavernEditPath,
} from "@/lib/tavernNav";
import { describe, expect, it } from "vitest";

describe("tavernNav", () => {
  it("encodes slug in public article path", () => {
    expect(tavernArticlePath("raid-kit")).toBe("/tavern/raid-kit");
    expect(tavernArticlePath("a/b")).toBe("/tavern/a%2Fb");
  });

  it("builds write and admin paths", () => {
    expect(tavernEditPath(12)).toBe("/tavern/write/12");
    expect(TAVERN_WRITE_PATH).toBe("/tavern/write");
    expect(TAVERN_ADMIN_PATH).toBe("/tavern/admin");
    expect(TAVERN_PATH).toBe("/tavern");
    expect(TAVERN_WELCOME_SLUG).toBe("welcome");
  });
});
