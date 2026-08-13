import { Alert, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovBosses } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { tarkovBossHref } from "@/lib/tarkovHomeNav";
import styles from "./TarkovBossPanel.module.css";

export function TarkovBossesHubPanel() {
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-bosses"],
    queryFn: fetchTarkovBosses,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  if (catalogQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="BOSS 列表加载失败"
        description={apiError(catalogQuery.error, "BOSS 列表加载失败")}
      />
    );
  }

  const rows = catalogQuery.data?.items ?? [];

  return (
    <div className={styles.grid}>
      {rows.map((item) => (
        <Link
          key={item.id || item.slug}
          to={tarkovBossHref(item.slug)}
          className={styles.card}
        >
          <div className={styles.english}>{item.name}</div>
          {item.nickname ? <div className={styles.zh}>{item.nickname}</div> : null}
          {item.portrait_link ? (
            <img
              className={styles.avatar}
              src={item.portrait_link}
              alt=""
              width={96}
              height={96}
            />
          ) : (
            <span className={styles.avatar} />
          )}
        </Link>
      ))}
    </div>
  );
}
