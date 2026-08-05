import type { ArknightsOperator, ArknightsOwnedChar } from "@/api/types";
import { evolveLabel, moduleEquips, POTENTIAL_ROMAN } from "./operatorUtils";

export function OwnedDetailTooltip({
  ownerName,
  channelName,
  roleName,
  op,
  owned,
}: {
  ownerName: string;
  channelName?: string | null;
  roleName?: string | null;
  op: ArknightsOperator;
  owned: ArknightsOwnedChar;
}) {
  const potential = Math.max(0, Math.min(5, owned.potential_rank | 0));
  const mods = moduleEquips(owned);
  const skills = owned.skills || [];
  return (
    <div style={{ maxWidth: 260, lineHeight: 1.55 }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>
        {ownerName}
        {channelName ? (
          <span style={{ fontWeight: 400, opacity: 0.85 }}> · {channelName}</span>
        ) : null}
      </div>
      {roleName ? (
        <div style={{ opacity: 0.85, marginBottom: 6 }}>{roleName}</div>
      ) : null}
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{op.name}</div>
      <div>
        {evolveLabel(owned.evolve_phase)} Lv.{owned.level}
        {potential > 0 ? ` · 潜能${POTENTIAL_ROMAN[potential]}` : ""}
        {owned.favor_percent != null ? ` · 信赖 ${owned.favor_percent}%` : ""}
      </div>
      {skills.length > 0 ? (
        <div style={{ marginTop: 6 }}>
          <div style={{ opacity: 0.75, fontSize: 12 }}>技能</div>
          {skills.map((s) => (
            <div key={s.skill_id}>{s.label}</div>
          ))}
        </div>
      ) : null}
      {mods.length > 0 ? (
        <div style={{ marginTop: 6 }}>
          <div style={{ opacity: 0.75, fontSize: 12 }}>模组</div>
          {mods.map((e) => (
            <div key={e.equip_id}>
              {e.name}
              {e.type_icon ? `（${e.type_icon.split("-").pop()?.toUpperCase() || e.type_icon}）` : ""}
              {` Lv.${e.level}`}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginTop: 6, opacity: 0.7 }}>暂无已解锁模组</div>
      )}
    </div>
  );
}
