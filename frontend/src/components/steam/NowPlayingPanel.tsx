import { Avatar, Tooltip, Typography } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

import type { SteamNowItem } from "@/api/types";
import { formatDuration } from "@/components/steam/format";
import { GameStoreHoverCard } from "@/components/steam/GameStoreHoverCard";
import {
  groupNowPlaying,
  sessionDurationSeconds,
} from "@/components/steam/nowPlayingUtils";
import { GameIcon } from "@/components/steam/SteamClientIcon";
import { steamStoreUrl } from "@/components/steam/timelineUtils";

export function NowPlayingPanel({ items }: { items: SteamNowItem[] }) {
  const groups = useMemo(() => groupNowPlaying(items), [items]);
  const fetchedAtRef = useRef(Date.now());
  const [nowMs, setNowMs] = useState(Date.now());
  useEffect(() => {
    fetchedAtRef.current = Date.now();
    setNowMs(Date.now());
  }, [items]);
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div style={{ marginBottom: 16 }}>
      <Typography.Text type="secondary">正在游玩</Typography.Text>
      <div
        style={{
          marginTop: 10,
          display: "flex",
          flexDirection: "row",
          flexWrap: "nowrap",
          alignItems: "stretch",
          gap: 12,
          overflowX: "auto",
          overflowY: "hidden",
          paddingBottom: 6,
          WebkitOverflowScrolling: "touch",
        }}
      >
        {groups.map((group) => {
          const header = (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                background: "#fafafa",
                borderBottom: "1px solid #f0f0f0",
                cursor: group.steam_app_id ? "pointer" : "default",
              }}
              onClick={() => {
                if (group.steam_app_id) {
                  window.open(
                    steamStoreUrl(group.steam_app_id),
                    "_blank",
                    "noopener,noreferrer",
                  );
                }
              }}
            >
              <GameIcon
                appId={group.steam_app_id}
                iconUrl={group.icon_url}
                name={group.game_name}
                size={40}
              />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: 13,
                    lineHeight: 1.35,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={group.game_name}
                >
                  {group.game_name}
                </div>
                <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)", marginTop: 2 }}>
                  {group.players.length} 人在玩
                </div>
              </div>
            </div>
          );
          return (
          <div
            key={group.steam_app_id || group.game_name}
            style={{
              width: 260,
              flex: "0 0 260px",
              boxSizing: "border-box",
              border: "1px solid #f0f0f0",
              borderRadius: 10,
              background: "#fff",
              boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {group.steam_app_id ? (
              <Tooltip
                placement="top"
                autoAdjustOverflow={false}
                color="#ffffff"
                mouseEnterDelay={0.25}
                destroyTooltipOnHide
                overlayInnerStyle={{
                  padding: 0,
                  overflow: "hidden",
                  borderRadius: 8,
                  minHeight: 0,
                  minWidth: 0,
                  boxShadow: "0 6px 16px rgba(0,0,0,0.12)",
                }}
                title={
                  <GameStoreHoverCard
                    appId={group.steam_app_id}
                    fallbackName={group.game_name}
                  />
                }
              >
                {header}
              </Tooltip>
            ) : (
              header
            )}
            <div
              style={{
                padding: "8px 10px 10px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
                flex: 1,
              }}
            >
              {group.players.map((p) => (
                <div
                  key={p.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    minHeight: 36,
                  }}
                >
                  <Avatar size={28} src={p.avatar_url || undefined}>
                    {p.member_nickname[0]}
                  </Avatar>
                  <div style={{ minWidth: 0, flex: 1, lineHeight: 1.3 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={p.member_nickname}
                    >
                      {p.member_nickname}
                    </div>
                    <div style={{ fontSize: 12, color: "#52c41a" }}>
                      本次{" "}
                      {formatDuration(
                        sessionDurationSeconds(p, fetchedAtRef.current, nowMs),
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          );
        })}
      </div>
    </div>
  );
}
