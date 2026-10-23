export const DEFAULT_REPO_SYNC_TIMEOUT_MINUTES = 30;
export const MAX_REPO_SYNC_TIMEOUT_MINUTES = 1440;

export const REPOSITORY_SYNC_TIMEOUT_JOBS = [
  {
    jobId: "arknights_repo_sync",
    label: "明日方舟资源仓",
    repository: "yuanyan3060/ArknightsGameResource",
  },
  {
    jobId: "endfield_repo_sync",
    label: "终末地数据仓",
    repository: "rmxlinux/EndfieldData",
  },
  {
    jobId: "tarkov_overlay_repo_sync",
    label: "逃离塔科夫数据图层",
    repository: "MiwiDots/tarkov-data-overlay",
  },
  {
    jobId: "tarkov_svg_repo_sync",
    label: "逃离塔科夫地图 SVG",
    repository: "the-hideout/tarkov-dev-svg-maps",
  },
] as const;

export interface ExternalRepository {
  name: string;
  url: string;
}

export const EXTERNAL_REPOSITORIES: Readonly<Record<string, ExternalRepository>> = {
  "skland.arknights.repo_sync": {
    name: "ArknightsGameResource",
    url: "https://github.com/yuanyan3060/ArknightsGameResource",
  },
  "skland.endfield.repo_sync": {
    name: "EndfieldData",
    url: "https://github.com/rmxlinux/EndfieldData",
  },
  "guides.tarkov.svg_repo_sync": {
    name: "tarkov-dev-svg-maps",
    url: "https://github.com/the-hideout/tarkov-dev-svg-maps",
  },
};

const HIDDEN_TASK_FEATURE_IDS = new Set(["guides.tarkov.overlay_repo_sync"]);

export function taskFeatureDisplayName(id: string, name: string): string {
  const repository = EXTERNAL_REPOSITORIES[id];
  return repository ? `${name}-${repository.name}` : name;
}

export function isTaskFeatureVisible(id: string): boolean {
  return !HIDDEN_TASK_FEATURE_IDS.has(id);
}
