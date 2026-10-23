import { ArrowLeftOutlined } from "@ant-design/icons";
import { Link, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTaskDetail } from "@/features/guides/tarkov/api/guidesApi";
import { TarkovItemsBreadcrumb } from "@/features/guides/tarkov/components/TarkovItemsBreadcrumb";
import { TarkovTaskDetailPanel } from "@/features/guides/tarkov/components/TarkovTaskDetailPanel";
import { TARKOV_HOME_PATH, TARKOV_TASKS_PATH } from "@/features/guides/tarkov/model/tarkovHomeNav";
import { useTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import styles from "@/features/guides/tarkov/components/TarkovItemsPageShell.module.css";

export default function TarkovTaskDetailPage() {
  const { taskId = "" } = useParams<{ taskId: string }>();
  const gameMode = useTarkovGameMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-task-detail", gameMode, taskId],
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
    <div className={styles.inner}>
      <div className={styles.taskDetail}>
        <div className={styles.taskTopBar}>
          <TarkovItemsBreadcrumb
            items={[
              { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
              { label: "任务", to: TARKOV_TASKS_PATH },
              { label: title },
            ]}
          />
          <Link className={styles.taskTopBarBack} to={TARKOV_TASKS_PATH}>
            <ArrowLeftOutlined />
            返回任务列表
          </Link>
        </div>
        <TarkovTaskDetailPanel taskId={taskId} />
      </div>
    </div>
  );
}
