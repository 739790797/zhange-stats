import { useCallback, useMemo } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovRaidPrep,
  type TarkovRaidPrepTask,
} from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  mergeRaidPrepGeometryItems,
  missingRaidPrepGeometryIds,
  raidPrepGeometryQueryKey,
  selectedTasksFromCatalog,
} from "@/lib/tarkovRaidPrep";

const EMPTY_GEOMETRY: Record<string, TarkovRaidPrepTask> = {};

export function useRaidPrepGeometry(mapId: string, ids: readonly string[]) {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const cacheKey = raidPrepGeometryQueryKey(gameMode, mapId);
  const uniqueIds = useMemo(() => {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const raw of ids) {
      const id = (raw || "").trim();
      if (!id || seen.has(id)) continue;
      seen.add(id);
      out.push(id);
    }
    return out;
  }, [ids]);
  const cacheQuery = useQuery({
    queryKey: cacheKey,
    queryFn: () => ({}) as Record<string, TarkovRaidPrepTask>,
    enabled: false,
    initialData: {},
    staleTime: Infinity,
  });
  const cached = cacheQuery.data ?? EMPTY_GEOMETRY;
  const missing = useMemo(
    () => missingRaidPrepGeometryIds(cached, uniqueIds),
    [cached, uniqueIds],
  );
  const fetchQuery = useQuery({
    queryKey: [...cacheKey, "fetch", missing.join(",")],
    queryFn: async () => {
      const data = await fetchTarkovRaidPrep({
        map: mapId,
        geometry: true,
        ids: missing,
      });
      queryClient.setQueryData(
        cacheKey,
        (prev: Record<string, TarkovRaidPrepTask> | undefined) =>
          mergeRaidPrepGeometryItems(prev, data.items),
      );
      return data.items.length;
    },
    enabled: Boolean(mapId) && missing.length > 0,
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });
  const items = useMemo(
    () => selectedTasksFromCatalog(Object.values(cached), uniqueIds),
    [cached, uniqueIds],
  );
  const ensure = useCallback(
    async (id: string) => {
      const taskId = (id || "").trim();
      if (!taskId || !mapId) return undefined;
      const have = queryClient.getQueryData<Record<string, TarkovRaidPrepTask>>(
        cacheKey,
      );
      if (have?.[taskId]) return have[taskId];
      const extra = await fetchTarkovRaidPrep({
        map: mapId,
        geometry: true,
        ids: [taskId],
      });
      const rich = extra.items.find((item) => item.id === taskId);
      if (!rich) return undefined;
      queryClient.setQueryData(
        cacheKey,
        (prev: Record<string, TarkovRaidPrepTask> | undefined) =>
          mergeRaidPrepGeometryItems(prev, [rich]),
      );
      return rich;
    },
    [cacheKey, mapId, queryClient],
  );
  return useMemo(
    () => ({
      items,
      byId: cached,
      isFetching: fetchQuery.isFetching,
      ensure,
    }),
    [cached, ensure, fetchQuery.isFetching, items],
  );
}
