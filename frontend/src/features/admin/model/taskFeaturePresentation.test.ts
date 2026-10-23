import { describe, expect, it } from "vitest";
import {
  DEFAULT_REPO_SYNC_TIMEOUT_MINUTES,
  EXTERNAL_REPOSITORIES,
  MAX_REPO_SYNC_TIMEOUT_MINUTES,
  REPOSITORY_SYNC_TIMEOUT_JOBS,
  isTaskFeatureVisible,
  taskFeatureDisplayName,
} from "./taskFeaturePresentation";

describe("task feature presentation", () => {
  it("exposes independent timeout settings for all registered Git sync jobs", () => {
    expect(DEFAULT_REPO_SYNC_TIMEOUT_MINUTES).toBe(30);
    expect(MAX_REPO_SYNC_TIMEOUT_MINUTES).toBeGreaterThan(30);
    expect(REPOSITORY_SYNC_TIMEOUT_JOBS.map((job) => job.jobId)).toEqual([
      "arknights_repo_sync",
      "endfield_repo_sync",
      "tarkov_overlay_repo_sync",
      "tarkov_svg_repo_sync",
    ]);
  });
  it("adds the external repository name to repository update tasks", () => {
    expect(
      taskFeatureDisplayName("skland.arknights.repo_sync", "外部仓库更新"),
    ).toBe("外部仓库更新-ArknightsGameResource");
    expect(
      taskFeatureDisplayName("skland.endfield.repo_sync", "外部仓库更新"),
    ).toBe("外部仓库更新-EndfieldData");
    expect(
      taskFeatureDisplayName("guides.tarkov.svg_repo_sync", "外部仓库更新"),
    ).toBe("外部仓库更新-tarkov-dev-svg-maps");
  });

  it("keeps the matching GitHub repository links", () => {
    expect(EXTERNAL_REPOSITORIES["skland.arknights.repo_sync"].url).toBe(
      "https://github.com/yuanyan3060/ArknightsGameResource",
    );
    expect(EXTERNAL_REPOSITORIES["guides.tarkov.svg_repo_sync"].url).toBe(
      "https://github.com/the-hideout/tarkov-dev-svg-maps",
    );
    expect(EXTERNAL_REPOSITORIES["guides.tarkov.overlay_repo_sync"]).toBeUndefined();
  });

  it("hides the unused Tarkov overlay repository task only", () => {
    expect(isTaskFeatureVisible("guides.tarkov.overlay_repo_sync")).toBe(false);
    expect(isTaskFeatureVisible("guides.tarkov.svg_repo_sync")).toBe(true);
    expect(isTaskFeatureVisible("skland.arknights.repo_sync")).toBe(true);
  });
});
