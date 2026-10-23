export const UPSTREAM_REPO_NOT_SYNCED_CODE = "UPSTREAM_REPO_NOT_SYNCED";
export const UPSTREAM_REPO_NOT_SYNCED_EVENT = "zhange:upstream-repo-not-synced";

type ApiErrorLike = {
  response?: {
    data?: { detail?: { code?: unknown } };
    headers?: Record<string, unknown>;
  };
};

export function isUpstreamRepoNotSyncedError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const response = (error as ApiErrorLike).response;
  const detailCode = response?.data?.detail?.code;
  const repoState = response?.headers?.["x-upstream-repo-state"];
  return (
    detailCode === UPSTREAM_REPO_NOT_SYNCED_CODE || repoState === "not-synced"
  );
}

export function upstreamRepoForResourcePath(pathname: string): string | null {
  if (pathname.startsWith("/api/skland/arknights/assets/")) {
    return "arknights-game-resource";
  }
  if (pathname.startsWith("/api/guides/tarkov/map-svg/")) {
    return "tarkov-dev-svg-maps";
  }
  return null;
}
