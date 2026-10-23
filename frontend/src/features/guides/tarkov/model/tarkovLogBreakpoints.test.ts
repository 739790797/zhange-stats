import { describe, expect, it } from "vitest";
import {
  collectLogBreakpoints,
  defaultLogBreakpoint,
  formatLogBreakpointLabel,
  latestIdentityForMode,
  sessionStubMatchesBreakpoint,
  type TarkovLogBreakpoint,
} from "./tarkovLogBreakpoints";
import type { TarkovLogIdentity } from "./tarkovGameLogs";

function ident(
  extra: Partial<TarkovLogIdentity> &
    Pick<TarkovLogIdentity, "profileId" | "sessionMode" | "at">,
): TarkovLogIdentity {
  return {
    version: extra.version || "0.16.0.0",
    accountId: extra.accountId || "1",
    folder: extra.folder || "log_a",
    ...extra,
  };
}

describe("collectLogBreakpoints", () => {
  it("keeps the first sighting of version + profile + classified mode", () => {
    const rows = collectLogBreakpoints([
      ident({
        profileId: "aaa",
        sessionMode: "regular",
        at: "2026-01-02 10:00:00",
        version: "0.16.1.0",
      }),
      ident({
        profileId: "aaa",
        sessionMode: "pvp",
        at: "2026-01-03 10:00:00",
        version: "0.16.1.0",
      }),
      ident({
        profileId: "aaa",
        sessionMode: "regular",
        at: "2026-01-01 10:00:00",
        version: "0.16.1.0",
      }),
      ident({
        profileId: "bbb",
        sessionMode: "pve",
        at: "2026-01-01 11:00:00",
      }),
      ident({
        profileId: "ccc",
        sessionMode: "seasonal",
        at: "2026-01-01 12:00:00",
      }),
    ]);
    expect(rows.map((row) => `${row.profileId}:${row.sessionMode}:${row.at}`)).toEqual([
      "aaa:regular:2026-01-01 10:00:00",
      "bbb:pve:2026-01-01 11:00:00",
      "ccc:seasonal:2026-01-01 12:00:00",
    ]);
  });
});

describe("defaultLogBreakpoint", () => {
  const rows: TarkovLogBreakpoint[] = [
    {
      version: "0.15.0.0",
      profileId: "old",
      accountId: "1",
      sessionMode: "regular",
      at: "2025-01-01 10:00:00",
      folder: "old",
    },
    {
      version: "0.16.0.0",
      profileId: "aaa",
      accountId: "1",
      sessionMode: "regular",
      at: "2026-01-01 10:00:00",
      folder: "a",
    },
    {
      version: "0.16.1.0",
      profileId: "aaa",
      accountId: "1",
      sessionMode: "regular",
      at: "2026-02-01 10:00:00",
      folder: "a2",
    },
    {
      version: "0.16.0.0",
      profileId: "bbb",
      accountId: "1",
      sessionMode: "pve",
      at: "2026-01-02 10:00:00",
      folder: "b",
    },
  ];

  it("picks the current wipe earliest breakpoint for the latest profile of this mode", () => {
    const picked = defaultLogBreakpoint(rows, {
      gameMode: "pvp",
      wipeFrom: "2025-11-15 00:00:00",
      latest: ident({
        profileId: "aaa",
        sessionMode: "regular",
        at: "2026-03-01 10:00:00",
      }),
    });
    expect(picked?.at).toBe("2026-01-01 10:00:00");
    expect(picked?.profileId).toBe("aaa");
    expect(picked?.version).toBe("0.16.0.0");
  });

  it("does not default to seasonal", () => {
    expect(
      defaultLogBreakpoint(
        [
          {
            version: "0.16.0.0",
            profileId: "szn",
            accountId: "1",
            sessionMode: "seasonal",
            at: "2026-01-01 10:00:00",
            folder: "s",
          },
        ],
        { gameMode: "pvp" },
      ),
    ).toBeNull();
  });
});

describe("latestIdentityForMode", () => {
  it("skips seasonal identities when resolving the live profile", () => {
    expect(
      latestIdentityForMode(
        [
          ident({
            profileId: "pvp",
            sessionMode: "regular",
            at: "2026-01-01 10:00:00",
          }),
          ident({
            profileId: "szn",
            sessionMode: "SZN",
            at: "2026-03-01 10:00:00",
          }),
        ],
        "pvp",
      )?.profileId,
    ).toBe("pvp");
  });
});

describe("sessionStubMatchesBreakpoint", () => {
  const breakpoint = {
    profileId: "aaa",
    sessionMode: "regular",
    at: "2026-01-02 00:00:00",
  };

  it("keeps folders that have no identities so preview failure does not drop them", () => {
    expect(
      sessionStubMatchesBreakpoint(
        { folder: "log_x", startedAt: "2026-01-03 00:00:00" },
        breakpoint,
      ),
    ).toBe(true);
  });

  it("requires the same profile and mode at or after the breakpoint clock", () => {
    expect(
      sessionStubMatchesBreakpoint(
        {
          folder: "log_y",
          startedAt: "2026-01-03 00:00:00",
          identities: [
            ident({
              profileId: "aaa",
              sessionMode: "pve",
              at: "2026-01-03 00:00:00",
            }),
          ],
        },
        breakpoint,
      ),
    ).toBe(false);
    expect(
      sessionStubMatchesBreakpoint(
        {
          folder: "log_z",
          startedAt: "2026-01-03 00:00:00",
          identities: [
            ident({
              profileId: "aaa",
              sessionMode: "regular",
              at: "2026-01-03 00:00:00",
              version: "0.16.9.0",
            }),
          ],
        },
        breakpoint,
      ),
    ).toBe(true);
  });
});

describe("formatLogBreakpointLabel", () => {
  it("shortens the profile id", () => {
    expect(
      formatLogBreakpointLabel({
        version: "0.16.0.0",
        profileId: "aa11bb22cc33dd44",
        accountId: "1",
        sessionMode: "regular",
        at: "2026-01-01 10:00:00.123",
        folder: "log_a",
      }),
    ).toBe("0.16.0.0 · 正式 · aa11bb22… · 2026-01-01 10:00:00");
  });
});
