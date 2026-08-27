import { Alert, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTraders } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovTraderHref } from "@/lib/tarkovHomeNav";
import styles from "./TarkovTraderPanel.module.css";

export function TarkovTradersHubPanel() {
  const gameMode = useTarkovGameMode();
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-traders", gameMode],
    queryFn: fetchTarkovTraders,
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
        message="商人列表加载失败"
        description={apiError(catalogQuery.error, "商人列表加载失败")}
      />
    );
  }

  const rows = catalogQuery.data?.items ?? [];

  return (
    <div className={styles.grid}>
      {rows.map((item) => (
        <Link
          key={item.id}
          to={tarkovTraderHref(item.slug)}
          className={styles.card}
        >
          <img
            className={styles.avatar}
            src={item.portrait_link || item.image_link}
            alt=""
            width={72}
            height={72}
            onError={(event) => {
              if (item.image_link && event.currentTarget.src !== item.image_link) {
                event.currentTarget.src = item.image_link;
              }
            }}
          />
          <div className={styles.english}>{item.english}</div>
          {item.chinese ? <div className={styles.zh}>{item.chinese}</div> : null}
          <div className={styles.offers}>
            {item.offer_count ? `${item.offer_count} 条报价` : "无现金报价"}
          </div>
        </Link>
      ))}
    </div>
  );
}
