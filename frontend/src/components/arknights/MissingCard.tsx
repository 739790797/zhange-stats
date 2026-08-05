import type { ArknightsOperator } from "@/api/types";
import { professionIconSrc } from "./assets";
import { CARD_H, CARD_W, RARITY_ACCENT } from "./constants";
import { StarRow } from "./StarRow";

export function MissingCard({ op }: { op: ArknightsOperator }) {
  const accent = RARITY_ACCENT[op.rarity] || "#888";
  return (
    <div
      title={`${op.name}（未拥有）`}
      style={{
        width: CARD_W,
        height: CARD_H,
        flex: "0 0 auto",
        position: "relative",
        overflow: "hidden",
        background: "#e8e8e8",
        boxShadow: `inset 0 0 0 1.5px ${accent}66`,
        opacity: 0.8,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 5,
          left: 0,
          right: 0,
          padding: "0 6px",
        }}
      >
        <StarRow rarity={op.rarity} light={false} />
      </div>
      <img
        src={professionIconSrc(op.profession)}
        alt=""
        width={22}
        height={22}
        style={{
          position: "absolute",
          top: 4,
          left: 4,
          objectFit: "contain",
          opacity: 0.4,
        }}
        loading="lazy"
      />
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ fontSize: 40, fontWeight: 700, color: "#c4c4c4" }}>?</span>
      </div>
      <div
        style={{
          position: "absolute",
          right: 5,
          bottom: 6,
          left: 8,
          color: "#888",
          fontSize: 12,
          fontWeight: 600,
          textAlign: "right",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {op.name}
      </div>
    </div>
  );
}
