import { Typography } from "antd";
import type { ArknightsCompareRow, ArknightsOperator } from "@/api/types";
import { CARD_GAP, CARD_H, CARD_W } from "./constants";
import { MissingCard } from "./MissingCard";
import { OwnedCard } from "./OwnedCard";
import { computeRarityProgress } from "./progress";
import { RowLabel } from "./RowLabel";

export function SyncCompareBoard({
  rows,
  orderedOps,
  catalog,
  selfId,
  roleUidByMember,
  onRoleUidChange,
  onRemoveMember,
}: {
  rows: ArknightsCompareRow[];
  orderedOps: ArknightsOperator[];
  catalog: ArknightsOperator[];
  selfId?: number;
  roleUidByMember: Record<number, string>;
  onRoleUidChange: (memberId: number, uid: string) => void;
  onRemoveMember: (memberId: number) => void;
}) {
  return (
    <div
      style={{
        overflowX: "auto",
        overflowY: "hidden",
        WebkitOverflowScrolling: "touch",
        border: "1px solid rgba(0,0,0,0.06)",
        borderRadius: 10,
        background: "#f0f0f0",
      }}
    >
      {rows.map((row, idx) => {
        const progress =
          row.status === "ok" ? computeRarityProgress(row, catalog) : null;
        return (
          <div
            key={row.member_id}
            style={{
              display: "flex",
              alignItems: "stretch",
              minHeight: CARD_H * 2 + CARD_GAP + 24,
              borderBottom:
                idx === rows.length - 1
                  ? "none"
                  : "1px solid rgba(0,0,0,0.06)",
              background: idx % 2 ? "#f7f7f7" : "#fafafa",
            }}
          >
            <RowLabel
              row={row}
              progress={progress}
              selectedUid={roleUidByMember[row.member_id]}
              canRemove={row.member_id !== selfId}
              onUidChange={(uid) => onRoleUidChange(row.member_id, uid)}
              onRemove={() => onRemoveMember(row.member_id)}
            />
            <div
              style={{
                display: "grid",
                gridTemplateRows: `${CARD_H}px ${CARD_H}px`,
                gridAutoFlow: "column",
                gridAutoColumns: CARD_W,
                gap: CARD_GAP,
                padding: "10px 12px",
                alignItems: "start",
              }}
            >
              {row.status !== "ok" ? (
                <Typography.Text
                  type="secondary"
                  style={{ padding: "0 8px", gridRow: "1 / span 2" }}
                >
                  {row.message || "无法读取盒子"}
                </Typography.Text>
              ) : (
                orderedOps.map((op) => {
                  const owned = row.owned?.[op.char_id];
                  return owned ? (
                    <OwnedCard
                      key={op.char_id}
                      op={op}
                      owned={owned}
                      ownerName={row.nickname}
                      channelName={row.channel_name}
                      roleName={row.role_name}
                    />
                  ) : (
                    <MissingCard key={op.char_id} op={op} />
                  );
                })
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
