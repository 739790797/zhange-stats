import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiError } from "@/lib/apiError";
import { Alert, Button } from "antd";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  fetchExiliumStatus,
  fetchKujiequStatus,
  fetchMihoyoStatus,
  fetchMyDailyTasks,
  fetchSklandStatus,
  fetchTaygedoStatus,
} from "@/api/client";
import { MyDailyBoard } from "@/components/daily/MyDailyBoard";
import { PageHeader } from "@/components/PageHeader";
import {
  buildDailyPlatformGroups,
  overlayDailyLiveStatus,
  summarizeDailyTasks,
  type DailyLivePlatformStatus,
} from "@/lib/myDaily";
import { nowBeijing } from "@/lib/time";

const DAILY_STATUS_FETCHERS: Record<
  string,
  {
    queryKey: string[];
    fetch: () => Promise<DailyLivePlatformStatus>;
  }
> = {
  skland: {
    queryKey: ["skland-status"],
    fetch: () => fetchSklandStatus(true, true),
  },
  taygedo: {
    queryKey: ["taygedo-status"],
    fetch: () => fetchTaygedoStatus(true, true),
  },
  exilium: {
    queryKey: ["exilium-status"],
    fetch: () => fetchExiliumStatus(true, true),
  },
  kujiequ: {
    queryKey: ["kujiequ-status"],
    fetch: () => fetchKujiequStatus(true, true),
  },
  mihoyo: {
    queryKey: ["mihoyo-status"],
    fetch: () => fetchMihoyoStatus(true, true),
  },
};

export default function MyDailyPage() {
  const queryClient = useQueryClient();
  const tasksQuery = useQuery({
    queryKey: ["my-daily-tasks"],
    queryFn: async () => {
      const pageSize = 100;
      const first = await fetchMyDailyTasks({ page: 1, page_size: pageSize });
      const items = [...(first.items || [])];
      const totalPages = Math.max(1, Math.ceil((first.total || 0) / pageSize));
      for (let p = 2; p <= totalPages; p += 1) {
        const next = await fetchMyDailyTasks({ page: p, page_size: pageSize });
        items.push(...(next.items || []));
      }
      return { ...first, items, page: 1, page_size: items.length };
    },
    refetchInterval: 30_000,
  });

  const included = useMemo(
    () => (tasksQuery.data?.items || []).filter((task) => task.included !== false),
    [tasksQuery.data?.items],
  );
  const statusPlatforms = useMemo(() => {
    const seen = new Set<string>();
    const list: string[] = [];
    for (const task of included) {
      if (!DAILY_STATUS_FETCHERS[task.platform] || seen.has(task.platform)) {
        continue;
      }
      seen.add(task.platform);
      list.push(task.platform);
    }
    return list;
  }, [included]);

  const statusQueries = useQueries({
    queries: statusPlatforms.map((platform) => {
      const spec = DAILY_STATUS_FETCHERS[platform];
      return {
        queryKey: spec.queryKey,
        queryFn: spec.fetch,
        retry: false,
        staleTime: 30_000,
      };
    }),
  });

  const liveByPlatform = useMemo(() => {
    const out: Record<string, DailyLivePlatformStatus | undefined> = {};
    statusPlatforms.forEach((platform, index) => {
      const data = statusQueries[index]?.data;
      if (data) out[platform] = data;
    });
    return out;
  }, [statusPlatforms, statusQueries]);

  const overlaid = useMemo(
    () => overlayDailyLiveStatus(included, liveByPlatform),
    [included, liveByPlatform],
  );
  const groups = useMemo(
    () => buildDailyPlatformGroups(overlaid),
    [overlaid],
  );
  const summary = useMemo(() => summarizeDailyTasks(overlaid), [overlaid]);
  const todayLabel = nowBeijing().format("M月D日 dddd");
  const statusFetching = statusQueries.some((query) => query.isFetching);

  return (
    <div>
      <PageHeader
        title="我的日常"
        subtitle={todayLabel}
        extra={
          <Link to="/profile">
            <Button>管理角色</Button>
          </Link>
        }
      />

      {tasksQuery.isError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="加载日常任务失败"
          description={apiError(tasksQuery.error, "请稍后重试")}
        />
      ) : null}

      <MyDailyBoard
        groups={groups}
        summary={summary}
        loading={tasksQuery.isLoading}
        refreshing={tasksQuery.isFetching || statusFetching}
        onRefresh={() => {
          void tasksQuery.refetch();
          for (const platform of statusPlatforms) {
            void queryClient.invalidateQueries({
              queryKey: DAILY_STATUS_FETCHERS[platform].queryKey,
            });
          }
        }}
      />
    </div>
  );
}
