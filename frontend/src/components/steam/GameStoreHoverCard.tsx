import { useQuery } from "@tanstack/react-query";

import { fetchSteamAppStore } from "@/api/client";

export function GameStoreHoverCard({
  appId,
  fallbackName,
}: {
  appId: string;
  fallbackName: string;
}) {
  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["steam-app-store", appId],
    queryFn: () => fetchSteamAppStore(appId),
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });

  const title = card?.name || fallbackName;

  return (
    <div
      style={{
        width: 240,
        boxSizing: "border-box",
        overflow: "hidden",
        background: "#fff",
        color: "rgba(0,0,0,0.88)",
        lineHeight: 1.4,
      }}
    >
      <div
        style={{
          width: "100%",
          height: 112,
          background: "#1b2838",
          overflow: "hidden",
          lineHeight: 0,
        }}
      >
        {card?.header_image ? (
          <img
            src={card.header_image}
            alt={title}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center",
              display: "block",
            }}
          />
        ) : (
          <div
            style={{
              height: "100%",
              minHeight: 80,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "rgba(255,255,255,0.65)",
              fontSize: 12,
              lineHeight: 1.4,
            }}
          >
            {isLoading ? "加载中…" : isError ? "暂无宣传图" : "加载中…"}
          </div>
        )}
      </div>
      <div style={{ padding: "10px 12px 12px", boxSizing: "border-box" }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: 13,
            lineHeight: 1.35,
            marginBottom: 6,
            wordBreak: "break-word",
          }}
        >
          {title}
        </div>
        {card?.short_description ? (
          <div
            style={{
              fontSize: 12,
              color: "rgba(0,0,0,0.55)",
              lineHeight: 1.45,
              marginBottom: 10,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              wordBreak: "break-word",
            }}
          >
            {card.short_description}
          </div>
        ) : null}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 8,
            minHeight: 22,
          }}
        >
          {isLoading && !card ? (
            <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>获取价格…</span>
          ) : card?.is_free ? (
            <span style={{ fontSize: 14, fontWeight: 700, color: "#2ecc71" }}>免费</span>
          ) : card?.final_formatted ? (
            <>
              {(card.discount_percent ?? 0) > 0 ? (
                <span
                  style={{
                    background: "#4c6b22",
                    color: "#beee11",
                    fontWeight: 700,
                    fontSize: 12,
                    padding: "1px 6px",
                    borderRadius: 2,
                  }}
                >
                  -{card.discount_percent}%
                </span>
              ) : null}
              {(card.discount_percent ?? 0) > 0 && card.initial_formatted ? (
                <span
                  style={{
                    fontSize: 12,
                    color: "rgba(0,0,0,0.45)",
                    textDecoration: "line-through",
                  }}
                >
                  {card.initial_formatted}
                </span>
              ) : null}
              <span style={{ fontSize: 14, fontWeight: 700, color: "#acbf2f" }}>
                {card.final_formatted}
              </span>
            </>
          ) : (
            <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>暂无价格信息</span>
          )}
        </div>
      </div>
    </div>
  );
}
