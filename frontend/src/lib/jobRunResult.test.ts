import { describe, expect, it } from "vitest";
import {
  JOB_RUN_WATCH_POLL_MS,
  isJobRunFinished,
  jobRunAlertType,
  jobRunAgeLabel,
  jobRunDomainLabel,
  jobRunFreshnessSummary,
  jobRunFreshnessText,
  jobRunStatEntries,
  jobRunStatusLabel,
  jobRunSummaryText,
  jobRunWatchPollMs,
  parseJobRunMessage,
  pickWatchedJobRun,
} from "./jobRunResult";

describe("jobRunResult", () => {
  it("picks the newest run after sinceRunId", () => {
    expect(pickWatchedJobRun([], 3)).toBeNull();
    expect(
      pickWatchedJobRun(
        [
          { id: 3, status: "ok" },
          { id: 2, status: "ok" },
        ],
        3,
      ),
    ).toBeNull();
    expect(
      pickWatchedJobRun(
        [
          { id: 5, status: "running" },
          { id: 3, status: "ok" },
        ],
        3,
      )?.id,
    ).toBe(5);
    expect(
      pickWatchedJobRun(
        [{ id: 2, status: "ok", started_at: "2026-01-01T00:00:00" }],
        0,
        Date.parse("2026-08-30T00:00:00Z"),
      ),
    ).toBeNull();
  });

  it("parses tarkov full-sync domain JSON", () => {
    const parsed = parseJobRunMessage(
      JSON.stringify({
        ok_count: 2,
        failed_count: 1,
        domains: [
          {
            id: "dump:items",
            ok: true,
            source: "json",
            mode: "pvp",
            synced_at: "2026-08-30T14:00:00+00:00",
            upstream_at: "2026-08-26T09:01:54+00:00",
          },
          { id: "maps", ok: false, error: "dump 缺少 maps" },
          { id: "items_zh", ok: true },
        ],
      }),
    );
    expect(parsed?.kind).toBe("domains");
    if (parsed?.kind !== "domains") return;
    expect(parsed.okCount).toBe(2);
    expect(parsed.failedCount).toBe(1);
    expect(parsed.domains[0]).toMatchObject({
      id: "dump:items",
      label: "dump · 物品 · PVP",
      ok: true,
      upstreamAt: "2026-08-26T09:01:54+00:00",
    });
    expect(parsed.domains[1]).toMatchObject({
      label: "地图 / BOSS",
      ok: false,
      error: "dump 缺少 maps",
    });
    expect(jobRunDomainLabel("items_zh")).toBe("物品（中文）");
  });

  it("keeps plain text and invalid JSON as text", () => {
    expect(parseJobRunMessage("完成：成功 1 / 失败 0 / 跳过 2（共 3）")).toEqual({
      kind: "text",
      text: "完成：成功 1 / 失败 0 / 跳过 2（共 3）",
    });
    expect(parseJobRunMessage("{not-json")).toEqual({
      kind: "text",
      text: "{not-json",
    });
    expect(parseJobRunMessage("")).toBeNull();
  });

  it("summarizes waiting and finished runs", () => {
    expect(jobRunSummaryText(null, "已提交执行")).toBe("已提交执行");
    expect(
      jobRunSummaryText({ id: 1, status: "running" }, "已提交执行"),
    ).toBe("已提交执行");
    expect(
      jobRunSummaryText({
        id: 1,
        status: "ok",
        message: JSON.stringify({
          ok_count: 4,
          failed_count: 0,
          domains: [],
        }),
      }),
    ).toBe("完成：成功 4 项");
    expect(jobRunSummaryText({ id: 1, status: "error" })).toBe("执行失败");
  });

  it("stops polling when finished or timed out", () => {
    expect(isJobRunFinished("ok")).toBe(true);
    expect(isJobRunFinished("running")).toBe(false);
    expect(
      jobRunWatchPollMs({
        run: { id: 1, status: "running" },
        startedAt: 0,
        now: 500,
      }),
    ).toBe(JOB_RUN_WATCH_POLL_MS);
    expect(
      jobRunWatchPollMs({
        run: { id: 1, status: "ok" },
        startedAt: 0,
        now: 500,
      }),
    ).toBe(false);
    expect(
      jobRunWatchPollMs({
        run: { id: 1, status: "running" },
        startedAt: 0,
        now: 11 * 60 * 1000,
      }),
    ).toBe(false);
  });

  it("formats upstream freshness", () => {
    const now = Date.parse("2026-08-30T14:00:00+00:00");
    expect(jobRunAgeLabel("2026-08-26T09:01:54+00:00", now)).toBe("4 天前");
    expect(
      jobRunFreshnessText(
        {
          syncedAt: "2026-08-30T14:00:00+00:00",
          upstreamAt: "2026-08-26T09:01:54+00:00",
        },
        now,
      ),
    ).toContain("上游");
    expect(
      jobRunFreshnessSummary(
        [
          {
            id: "dump:items",
            label: "物品",
            ok: true,
            upstreamAt: "2026-08-26T09:01:54+00:00",
          },
        ],
        now,
      ),
    ).toContain("4 天前");
  });

  it("maps status and scalar stats", () => {
    expect(jobRunStatusLabel("ok")).toBe("成功");
    expect(jobRunAlertType("error")).toBe("error");
    expect(
      jobRunStatEntries({
        ok: 2,
        failed: 1,
        nested: { skip: true },
        empty: null,
      }),
    ).toEqual([
      { key: "ok", label: "成功", value: "2" },
      { key: "failed", label: "失败", value: "1" },
    ]);
  });
});
