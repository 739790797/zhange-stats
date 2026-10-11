import { useQuery } from "@tanstack/react-query";
import { normalizeAppVersion } from "@/lib/appVersionCheck";

export const APP_VERSION_QUERY_KEY = ["app-version"] as const;

/** 长开着的标签页隔一阵再问一次，才能发现期间的发版（后台标签页不轮询）。 */
const APP_VERSION_POLL_MS = 10 * 60_000;

async function fetchAppVersion(): Promise<string> {
  // 探活公开 /health（无 Cookie / CSRF）；不走 *Api
  const res = await fetch("/health", { cache: "no-store" });
  // degraded 时后端返回 503，仍带 version 字段；重启中代理回的不是 JSON，抛错以保留上次的版本号
  const data = (await res.json()) as { version?: string };
  return normalizeAppVersion(data.version);
}

/** 服务端当前运行的版本。watch：切回标签页、每隔一阵再问，用来提示刷新。 */
export function useServerAppVersion({ watch = false }: { watch?: boolean } = {}) {
  return useQuery({
    queryKey: APP_VERSION_QUERY_KEY,
    queryFn: fetchAppVersion,
    staleTime: 60_000,
    refetchOnWindowFocus: watch,
    refetchInterval: watch ? APP_VERSION_POLL_MS : false,
  });
}
