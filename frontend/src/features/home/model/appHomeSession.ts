/** `/app` 启动时根据 `/auth/me` 的结果决定去向。无状态码视为网络失败，不当成未登录。 */

export type AppHomePhase = "in" | "out" | "error";

export function appHomePhase(status: number | undefined): AppHomePhase {
  if (status === 401) return "out";
  if (status == null || status >= 400) return "error";
  return "in";
}
