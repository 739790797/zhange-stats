import { Fragment } from "react";
import { Avatar, Button, Select, Tag, Typography } from "antd";
import { CloseOutlined } from "@ant-design/icons";
import type { ArknightsCompareRow } from "@/api/types";
import { LABEL_W, RARITY_ACCENT, RARITY_CN } from "./constants";
import { formatProgressPct, type RarityProgress } from "./progress";

export function RowLabel({
  row,
  progress,
  selectedUid,
  canRemove,
  onUidChange,
  onRemove,
}: {
  row: ArknightsCompareRow;
  progress: RarityProgress[] | null;
  selectedUid?: string;
  canRemove?: boolean;
  onUidChange?: (uid: string) => void;
  onRemove?: () => void;
}) {
  const roles = row.roles || [];
  const currentUid = selectedUid || row.uid || undefined;
  const selectedRole = roles.find((r) => r.uid === currentUid);
  const gameId = selectedRole?.role_name || row.role_name || null;
  return (
    <div
      style={{
        width: LABEL_W,
        flex: "0 0 auto",
        padding: "10px 10px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 8,
        borderRight: "1px solid rgba(0,0,0,0.06)",
        background: "#fff",
        position: "sticky",
        left: 0,
        zIndex: 8,
        isolation: "isolate",
        boxShadow: "4px 0 10px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          minWidth: 0,
        }}
      >
        <Avatar src={row.avatar_url || undefined} size="small">
          {(row.nickname || "?").slice(0, 1)}
        </Avatar>
        <Typography.Text strong ellipsis style={{ flex: 1, minWidth: 0 }}>
          {row.nickname}
        </Typography.Text>
        {canRemove ? (
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={onRemove}
            style={{ color: "#999", flex: "0 0 auto" }}
            aria-label="移除对比"
          />
        ) : null}
      </div>

      {roles.length > 0 ? (
        <Select
          size="small"
          style={{ width: "100%" }}
          value={currentUid}
          placeholder="渠道服"
          options={roles.map((r) => ({
            value: r.uid,
            label: r.channel_name || r.role_name,
            title: `${r.role_name} · ${r.channel_name}`,
          }))}
          onChange={(uid: string) => onUidChange?.(uid)}
          popupMatchSelectWidth={false}
        />
      ) : null}

      {row.status === "ok" ? (
        <>
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12 }}
            ellipsis
            title={
              gameId && row.player_level != null
                ? `${gameId} Lv.${row.player_level}`
                : gameId || undefined
            }
          >
            {gameId
              ? row.player_level != null
                ? `${gameId} Lv.${row.player_level}`
                : gameId
              : row.player_level != null
                ? `Lv.${row.player_level}`
                : "已绑定"}
          </Typography.Text>
          {progress ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "32px minmax(0, 1fr) 52px",
                columnGap: 4,
                rowGap: 3,
                fontSize: 12,
                lineHeight: 1.35,
                color: "#444",
                alignItems: "baseline",
              }}
            >
              {progress.map((p) => (
                <Fragment key={p.rarity}>
                  <span
                    style={{
                      color: RARITY_ACCENT[p.rarity] || "#888",
                      fontWeight: 700,
                    }}
                  >
                    {RARITY_CN[p.rarity]}
                  </span>
                  <span
                    style={{
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                    }}
                  >
                    {p.owned}/{p.total}
                  </span>
                  <span
                    style={{
                      color: "#999",
                      fontSize: 11,
                      fontVariantNumeric: "tabular-nums",
                      textAlign: "right",
                    }}
                  >
                    {formatProgressPct(p.owned, p.total)}
                  </span>
                </Fragment>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <Tag
          color={row.status === "unbound" ? "default" : "warning"}
          style={{ margin: 0, width: "fit-content" }}
        >
          {row.message || row.status}
        </Tag>
      )}
    </div>
  );
}
