import { ConfigProvider } from "antd";
import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTaskDetail } from "@/api/guidesApi";
import { TarkovGuideShell } from "@/components/guides/tarkov/TarkovGuideShell";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TarkovTaskDetailPanel } from "@/components/guides/tarkov/TarkovTaskDetailPanel";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";
import { TARKOV_HOME_PATH, TARKOV_TASKS_PATH } from "@/lib/tarkovHomeNav";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovTaskDetailPage() {
  const { taskId = "" } = useParams<{ taskId: string }>();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-task-detail", taskId],
    queryFn: () => fetchTarkovTaskDetail(taskId),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(taskId),
  });
  const title = detailQuery.data?.name || taskId;

  if (!taskId) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <TarkovGuideShell>
      <div className={styles.inner}>
        <TarkovItemsBreadcrumb
          items={[
            { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
            { label: "任务", to: TARKOV_TASKS_PATH },
            { label: title },
          ]}
        />
        <ConfigProvider theme={TARKOV_ANTD_DARK}>
          <TarkovTaskDetailPanel taskId={taskId} />
        </ConfigProvider>
      </div>
    </TarkovGuideShell>
  );
}
