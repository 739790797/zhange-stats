import { useState } from "react";
import { Tooltip } from "antd";
import type { ArknightsOperator, ArknightsOwnedChar } from "@/api/types";
import { eliteIconSrc, portraitSrc, professionIconSrc } from "./assets";
import { CARD_H, CARD_W, RARITY_ACCENT } from "./constants";
import { evolveLabel, POTENTIAL_ROMAN } from "./operatorUtils";
import { OwnedDetailTooltip } from "./OwnedDetailTooltip";
import { StarRow } from "./StarRow";

export function OwnedCard({
  op,
  owned,
  ownerName,
  channelName,
  roleName,
}: {
  op: ArknightsOperator;
  owned: ArknightsOwnedChar;
  ownerName: string;
  channelName?: string | null;
  roleName?: string | null;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const [useAvatar, setUseAvatar] = useState(false);
  const accent = RARITY_ACCENT[op.rarity] || "#888";
  const phase = owned.evolve_phase ?? 0;
  const potential = Math.max(0, Math.min(5, owned.potential_rank | 0));
  const avatar = owned.avatar_url || op.avatar_url;
  const src = useAvatar
    ? avatar || undefined
    : portraitSrc(op.char_id, phase);
  const eliteLabel = evolveLabel(phase);

  const card = (
    <div
      style={{
        width: CARD_W,
        height: CARD_H,
        flex: "0 0 auto",
        position: "relative",
        overflow: "hidden",
        background: "#1c1c1c",
        boxShadow: `inset 0 0 0 1.5px ${accent}`,
        cursor: "default",
      }}
    >
      <div style={{ position: "absolute", inset: 0 }}>
        {!imgFailed && src ? (
          <img
            src={src}
            alt={op.name}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center top",
            }}
            onError={() => {
              if (!useAvatar && avatar) {
                setUseAvatar(true);
                return;
              }
              setImgFailed(true);
            }}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#666",
              background: `linear-gradient(180deg, ${accent}44, #222)`,
            }}
          >
            {op.rarity}★
          </div>
        )}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 0,
            height: 64,
            background:
              "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.55) 35%, rgba(0,0,0,0.88) 100%)",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 0,
            height: 36,
            background:
              "linear-gradient(180deg, rgba(0,0,0,0.45) 0%, transparent 100%)",
            pointerEvents: "none",
          }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          top: 5,
          left: 0,
          right: 0,
          zIndex: 2,
          padding: "0 6px",
        }}
      >
        <StarRow rarity={op.rarity} />
      </div>
      <img
        src={professionIconSrc(op.profession)}
        alt={op.profession_label}
        width={22}
        height={22}
        style={{
          position: "absolute",
          top: 4,
          left: 4,
          zIndex: 3,
          objectFit: "contain",
          filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.85))",
        }}
        loading="lazy"
      />

      <div
        style={{
          position: "absolute",
          left: 4,
          bottom: 4,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 0,
        }}
      >
        <img
          src={eliteIconSrc(phase)}
          alt={eliteLabel}
          width={22}
          height={22}
          style={{
            objectFit: "contain",
            filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.8))",
            marginBottom: -2,
          }}
          loading="lazy"
        />
        <div
          style={{
            minWidth: 28,
            height: 28,
            borderRadius: "50%",
            background: "rgba(0,0,0,0.72)",
            border: "1px solid rgba(255,255,255,0.18)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontSize: owned.level >= 100 ? 12 : 14,
            fontWeight: 800,
            lineHeight: 1,
            fontVariantNumeric: "tabular-nums",
            textShadow: "0 1px 2px rgba(0,0,0,0.6)",
          }}
        >
          {owned.level}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          right: 5,
          bottom: 5,
          left: 40,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: 2,
          minWidth: 0,
        }}
      >
        {potential > 0 ? (
          <span
            style={{
              color: "#f3e2b0",
              fontSize: 12,
              fontWeight: 700,
              lineHeight: 1,
              letterSpacing: 0.5,
              textShadow: "0 1px 2px rgba(0,0,0,0.95)",
            }}
          >
            {POTENTIAL_ROMAN[potential]}
          </span>
        ) : (
          <span style={{ height: 12 }} />
        )}
        <div
          style={{
            color: "#fff",
            fontSize: 12,
            fontWeight: 700,
            lineHeight: 1.15,
            maxWidth: "100%",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            textAlign: "right",
            textShadow: "0 1px 2px rgba(0,0,0,0.95)",
          }}
        >
          {op.name}
        </div>
      </div>
    </div>
  );

  return (
    <Tooltip
      mouseEnterDelay={0.25}
      placement="top"
      title={
        <OwnedDetailTooltip
          ownerName={ownerName}
          channelName={channelName}
          roleName={roleName}
          op={op}
          owned={owned}
        />
      }
    >
      {card}
    </Tooltip>
  );
}
