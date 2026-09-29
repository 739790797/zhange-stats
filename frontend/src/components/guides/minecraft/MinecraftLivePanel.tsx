import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Typography } from "antd";
import { useEffect, useState } from "react";
import { fetchMinecraftStatus } from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import {
  DEFAULT_SERVER_ICON,
  displayJoinHost,
  pingBadge,
} from "./minecraftUi";
import { parseMotdLines, motdColorOnLight } from "./minecraftMotd";
import styles from "./MinecraftLivePanel.module.css";

function MinecraftMotd({ raw, fallback }: { raw: string; fallback?: string }) {
  const lines = parseMotdLines(raw);
  if (!lines.length) {
    if (!fallback) return null;
    return (
      <div className={styles.motd}>
        <div className={styles.motdLine}>{fallback}</div>
      </div>
    );
  }
  return (
    <div className={styles.motd}>
      {lines.map((spans, lineIdx) => (
        <div key={lineIdx} className={styles.motdLine}>
          {spans.map((span, spanIdx) => (
            <span
              key={spanIdx}
              style={{
                color: motdColorOnLight(span.color),
                fontWeight: span.bold ? 700 : undefined,
                fontStyle: span.italic ? "italic" : undefined,
                textDecoration:
                  [span.underline ? "underline" : "", span.strike ? "line-through" : ""]
                    .filter(Boolean)
                    .join(" ") || undefined,
              }}
            >
              {span.text}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

export function MinecraftLivePanel() {
  const statusQuery = useQuery({
    queryKey: ["minecraft-status"],
    queryFn: fetchMinecraftStatus,
    refetchInterval: 10_000,
    retry: 1,
  });

  const status = statusQuery.data;
  const applied = status?.applied;
  const [iconFailed, setIconFailed] = useState(false);

  useEffect(() => {
    setIconFailed(false);
  }, [status?.favicon]);

  const badge = pingBadge(Boolean(status?.ping_online), status?.power_state);
  const iconSrc =
    !iconFailed && status?.favicon ? status.favicon : DEFAULT_SERVER_ICON;
  const motdRaw =
    status?.motd_raw || status?.motd || applied?.properties?.motd || "";
  const motdFallback = status?.ping_online
    ? "A Minecraft Server"
    : statusQuery.isLoading
      ? ""
      : "无法连接";
  const joinHost = displayJoinHost({
    publicHost: status?.public_host,
    address: status?.address,
  });
  const versionLabel = applied?.mc_version || status?.version_name || "";
  const onlineCount = status?.players_online || 0;

  return (
    <div className={styles.wrap}>
      {statusQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message={apiError(statusQuery.error, "无法读取服况")}
        />
      ) : null}
      {status && status.pelican_configured === false ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="服务器尚未接入"
          description="请联系管理员配置 Pelican 面板后即可查看服况。"
        />
      ) : null}

      <Card size="small" title="服况">
        {statusQuery.isLoading && !status ? (
          <div className={`${styles.hero} ${styles.heroLoading}`}>
            <div className={styles.skelIcon} />
            <div className={styles.skelBody}>
              <div className={styles.skelLine} />
              <div className={`${styles.skelLine} ${styles.skelLineShort}`} />
            </div>
          </div>
        ) : (
          <div className={styles.hero}>
            <img
              className={styles.icon}
              src={iconSrc}
              alt=""
              width={64}
              height={64}
              onError={() => setIconFailed(true)}
            />
            <div className={styles.body}>
              <div className={styles.titleBlock}>
                <MinecraftMotd raw={motdRaw} fallback={motdFallback} />
                {joinHost ? (
                  <div className={styles.joinHost}>{joinHost}</div>
                ) : null}
              </div>
              <div className={styles.badge}>
                <span
                  className={`${styles.dot} ${
                    badge.kind === "online"
                      ? styles.dotOnline
                      : badge.kind === "busy"
                        ? styles.dotBusy
                        : ""
                  }`}
                />
                {badge.text}
              </div>
              {status?.message && !status.ping_online ? (
                <span className={styles.version}>{status.message}</span>
              ) : null}
            </div>
            <div className={styles.side}>
              <div className={styles.players}>
                {status ? `${onlineCount} / ${status.players_max || "—"}` : "—"}
              </div>
              <div className={styles.latency}>
                {status?.latency_ms != null ? `${status.latency_ms} ms` : " "}
              </div>
              {versionLabel ? (
                <div className={styles.version}>{versionLabel}</div>
              ) : null}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
