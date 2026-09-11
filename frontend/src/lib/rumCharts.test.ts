import { describe, expect, it } from "vitest";
import {
  rumAtToMs,
  rumBarHeight,
  rumBarPoints,
  rumChartLabel,
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
});

describe("rumTrendPoints / rumBarPoints", () => {
  it("melts series into two lines", () => {
    const points = rumTrendPoints([
      {
        at: "2026-09-11 12:00:00",
        api_count: 3,
        img_count: 8,
        api_p95_ms: 400,
        img_p95_ms: 80,
      },
    ]);
    expect(points).toHaveLength(2);
    expect(points[0]).toMatchObject({ series: "接口", count: 3, p95: 400 });
    expect(points[1]).toMatchObject({ series: "第三方图", count: 8, p95: 80 });
  });

  it("builds grouped bars and uniquifies labels", () => {
    const bars = rumBarPoints(
      [
        { url_key: "GET /api/a", host: "", count: 1, avg_ms: 1, p50_ms: 10, p95_ms: 20, error_count: 0 },
        { url_key: "GET /api/b", host: "", count: 1, avg_ms: 1, p50_ms: 30, p95_ms: 90, error_count: 0 },
      ],
      12,
    );
    expect(bars.map((b) => b.metric)).toEqual(["p50", "p95", "p50", "p95"]);
    expect(rumBarHeight(2)).toBeGreaterThan(200);
  });
});
