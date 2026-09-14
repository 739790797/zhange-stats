import { describe, expect, it } from "vitest";
import {
  rumAtToMs,
  rumBarHeight,
  rumBarPoints,
  rumBizBarPoints,
  rumBizFilterOptions,
  rumChartLabel,
  rumRowsForBiz,
  rumTrendDomain,
  rumTrendPoints,
} from "./rumCharts";

describe("rumChartLabel", () => {
  it("strips protocol and truncates from the left", () => {
    expect(rumChartLabel("GET /api/health")).toBe("GET /api/health");
    expect(
      rumChartLabel("https://assets.tarkov.dev/maps/{map}/**.png", 24),
    ).toBe("…v.dev/maps/{map}/**.png");
  });
});

describe("rumAtToMs", () => {
  it("parses Beijing naive timestamps", () => {
    expect(rumAtToMs("2026-09-11 12:00:00")).toBe(
      Date.parse("2026-09-11T12:00:00+08:00"),
    );
    expect(Number.isNaN(rumAtToMs(""))).toBe(true);
  });

  it("does not double-append timezone", () => {
    expect(rumAtToMs("2026-09-11 12:00:00+08:00")).toBe(
      Date.parse("2026-09-11T12:00:00+08:00"),
    );
  });
});

describe("rumTrendPoints / rumBarPoints", () => {
  it("keeps one row per bucket and drops empty hours", () => {
    const points = rumTrendPoints([
      {
        at: "2026-09-11 11:00:00",
        api_count: 0,
        img_count: 0,
      },
      {
        at: "2026-09-11 12:00:00",
        api_count: 3,
        img_count: 8,
        api_p95_ms: 400,
        img_p95_ms: 80,
      },
    ]);
    expect(points).toHaveLength(1);
    expect(points[0]).toMatchObject({
      count: 11,
      api_count: 3,
      img_count: 8,
      api_p95: 400,
      img_p95: 80,
    });
  });

  it("builds grouped bars and uniquifies labels", () => {
    const bars = rumBarPoints(
      [
        { url_key: "GET /api/a", host: "", biz: "other", biz_label: "其他", count: 1, avg_ms: 1, p50_ms: 10, p95_ms: 20, error_count: 0 },
        { url_key: "GET /api/b", host: "", biz: "other", biz_label: "其他", count: 1, avg_ms: 1, p50_ms: 30, p95_ms: 90, error_count: 0 },
      ],
      12,
    );
    expect(bars.map((b) => b.metric)).toEqual(["p50", "p95", "p50", "p95"]);
    expect(rumBarHeight(2)).toBeGreaterThan(200);
  });

  it("uses the full window for the x domain", () => {
    const domain = rumTrendDomain([
      { at: "2026-09-11 00:00:00" },
      { at: "2026-09-11 23:00:00" },
    ]);
    expect(domain.max! - domain.min!).toBe(23 * 3600_000);
  });
});

describe("rumRowsForBiz / rumBizBarPoints", () => {
  const rows = [
    {
      url_key: "GET /api/guides/tarkov/items/{id}",
      host: "",
      biz: "tarkov",
      biz_label: "逃离塔科夫",
      count: 3,
      avg_ms: 400,
      p50_ms: 200,
      p95_ms: 900,
      error_count: 0,
    },
    {
      url_key: "GET /api/setup/status",
      host: "",
      biz: "site",
      biz_label: "站点与运维",
      count: 8,
      avg_ms: 40,
      p50_ms: 30,
      p95_ms: 80,
      error_count: 0,
    },
    {
      url_key: "GET /api/auth/me",
      host: "",
      biz: "account",
      biz_label: "账号与资料",
      count: 10,
      avg_ms: 20,
      p50_ms: 15,
      p95_ms: 40,
      error_count: 0,
    },
  ];

  it("filters and keeps p95 order", () => {
    const all = rumRowsForBiz(rows, "all");
    expect(all.map((r) => r.biz)).toEqual(["tarkov", "site", "account"]);
    expect(rumRowsForBiz(rows, "site").map((r) => r.url_key)).toEqual([
      "GET /api/setup/status",
    ]);
  });

  it("builds business summary bars", () => {
    const bars = rumBizBarPoints([
      { biz: "tarkov", label: "逃离塔科夫", count: 3, avg_ms: 400, p50_ms: 200, p95_ms: 900, error_count: 0 },
      { biz: "site", label: "站点与运维", count: 8, avg_ms: 40, p50_ms: 30, p95_ms: 80, error_count: 0 },
    ]);
    expect(bars[0]).toMatchObject({ label: "逃离塔科夫（3）", metric: "p50", ms: 200 });
    expect(rumBizFilterOptions([
      { biz: "tarkov", label: "逃离塔科夫", count: 3, avg_ms: 400, error_count: 0 },
    ])).toEqual([{ label: "逃离塔科夫", value: "tarkov" }]);
  });
});
