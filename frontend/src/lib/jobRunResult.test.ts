import { describe, expect, it } from "vitest";
import {
  JOB_RUN_WATCH_POLL_MS,
  isJobRunFinished,
  jobRunAlertType,
  jobRunAgeLabel,
  jobRunDomainLabel,
  jobRunDomainProgressText,
  jobRunDomainStatusLabel,
  jobRunDownloadProgress,
  jobRunFreshnessSummary,
  jobRunFreshnessText,
  jobRunPhaseLabel,
  jobRunProgressPercent,
  jobRunProgressRows,
  jobRunStatEntries,
  jobRunStatusLabel,
  jobRunSummaryText,
  jobRunSyncedText,
  jobRunWatchPollMs,
  parseJobRunMessage,
  pickWatchedJobRun,
  formatJobRunBytes,
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
    expect(parsed.domains[0].status).toBe("ok");
    expect(parsed.domains[1].status).toBe("error");
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
      jobRunSummaryText(
        { id: 1, status: "running", message: "正在下载 encoder_model.onnx（2/8）" },
        "已提交执行",
      ),
    ).toBe("正在下载 encoder_model.onnx（2/8）");
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
    ).toBe(JOB_RUN_WATCH_POLL_MS);
    expect(
      jobRunWatchPollMs({
        run: null,
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
    expect(jobRunSyncedText({ syncedAt: "2026-08-30T14:00:00+00:00" })).toContain(
      "2026-08-30",
    );
    expect(
      jobRunDomainProgressText(
        {
          status: "ok",
          upstreamAt: "2026-08-26T09:01:54+00:00",
        },
        now,
      ),
    ).toContain("上游");
    expect(
      jobRunDomainProgressText(
        {
          status: "ok",
          upstreamAt: "2026-08-26T09:01:54+00:00",
        },
        now,
      ),
    ).not.toContain("落库");
    expect(
      jobRunFreshnessSummary(
        [
          {
            id: "dump:items",
            label: "物品",
            ok: true,
            status: "ok",
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
    expect(
      jobRunStatEntries({
        percent: 40,
        phase: "download",
        file: "encoder_model.onnx",
        bytes: 1572864,
        updated: true,
      }),
    ).toEqual([
      { key: "file", label: "当前文件", value: "encoder_model.onnx" },
      { key: "bytes", label: "已下载", value: "1.5 MB" },
      { key: "updated", label: "已更新", value: "是" },
    ]);
    expect(formatJobRunBytes(512)).toBe("512 B");
    expect(jobRunProgressPercent({ percent: 40.2 })).toBe(40);
    expect(jobRunProgressPercent({ percent: "x" })).toBeNull();
    expect(
      jobRunStatEntries(
        {
          percent: 40,
          phase: "download",
          file: "items",
          bytes: 1024,
        },
        { omitDownload: true },
      ),
    ).toEqual([]);
  });

  it("reads live progress from stats.domains and download bytes", () => {
    expect(jobRunPhaseLabel("download")).toBe("下载 dump");
    expect(jobRunDomainStatusLabel("downloading")).toBe("下载中");
    const run = {
      id: 9,
      status: "running",
      message: "正在下载 items（1/12）",
      stats: {
        phase: "download",
        percent: 8,
        file: "items",
        bytes: 5 * 1024 * 1024,
        total_bytes: 10 * 1024 * 1024,
        files_done: 0,
        files_total: 12,
        domains: [
          {
            id: "dump:items",
            ok: false,
            status: "downloading",
            mode: "pvp",
            bytes: 5 * 1024 * 1024,
            total_bytes: 10 * 1024 * 1024,
          },
          { id: "dump:maps", ok: false, status: "pending", mode: "pvp" },
        ],
      },
    };
    const rows = jobRunProgressRows(run);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: "dump:items",
      status: "downloading",
      label: "dump · 物品 · PVP",
    });
    expect(jobRunDomainProgressText(rows[0])).toBe("5.0 MB / 10.0 MB");
    expect(jobRunDownloadProgress(run.stats)).toMatchObject({
      file: "items",
      filesText: "0 / 12 个文件",
      bytesText: "5.0 MB / 10.0 MB",
      filePercent: 50,
    });
  });
});
