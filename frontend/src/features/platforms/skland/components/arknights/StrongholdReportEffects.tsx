import { LinkOutlined, UserOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";
import type {
  StrongholdBond,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { GAME_RES } from "./constants";
import { BattleIcon } from "./StrongholdBattleUI";
import { belongsToBond, bondStatus, chessKey } from "./strongholdReportModel";
import styles from "./StrongholdReport.module.css";

export function ReportBondIcon({ bond }: { bond: StrongholdBond }) {
  return (
    <span className={styles.bondEmblem} data-state={bond.active ?? "unknown"}>
      <BattleIcon className={styles.reportIcon} src={bond.icon_url} fallback={<LinkOutlined />} />
    </span>
  );
}

export function ReportEffect({
  icon,
  name,
  eyebrow,
  description,
  children,
}: {
  icon: ReactNode;
  name: string;
  eyebrow?: ReactNode;
  description: string;
  children?: ReactNode;
}) {
  return (
    <>
      <div className={styles.paperHeading}>
        {icon}
        <div>
          {eyebrow ? <small>{eyebrow}</small> : null}
          <strong>{name}</strong>
        </div>
      </div>
      <p className={styles.paperText}>{description}</p>
      {children}
    </>
  );
}

function activationLabel(bond: StrongholdBond) {
  if (bond.activation_count == null) return null;
  if (bond.activation_rule === "at_most") return `场上至多 ${bond.activation_count} 名所属干员`;
  if (bond.activation_rule === "golden") return `激活需 ${bond.activation_count} 名精锐干员`;
  return `激活需 ${bond.activation_count} 名所属干员`;
}

function BondMembers({
  bond,
  roster,
}: {
  bond: StrongholdBond;
  roster: StrongholdRecordDetail["roster"];
}) {
  const picked = (roster ?? []).filter((operator) => belongsToBond(operator, bond));
  const keys = new Set(picked.map(chessKey));
  const others = (bond.operators ?? []).filter(({ id }) => !keys.has(id));
  const groups = [
    { label: "本局上阵", picked: true, members: picked },
    {
      label: roster == null ? "所属干员（上阵未知）" : "其他成员",
      picked: false,
      members: others,
    },
  ];
  if (!picked.length && bond.show_operators === false) return null;
  return (
    <section className={styles.bondMembers} aria-label="盟约干员">
      <h5>盟约干员</h5>
      {groups.map(({ label, picked: onField, members }) =>
        members.length ? (
          <div key={label} className={styles.memberGroup} data-picked={onField}>
            <h6>{label}</h6>
            <ul>
              {members.map((operator, i) => (
                <li key={`${operator.id}-${i}`}>
                  <BattleIcon
                    className={styles.reportIcon}
                    src={
                      operator.char_id
                        ? `${GAME_RES}/avatar/${encodeURIComponent(operator.char_id)}.png`
                        : null
                    }
                    fallback={<UserOutlined />}
                  />
                  <span>{operator.name ?? "干员名未收录"}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
      {!picked.length && !others.length ? (
        <p className={styles.paperText}>
          {bond.operators ? "没有所属干员" : "同版本所属干员未收录"}
        </p>
      ) : null}
    </section>
  );
}

export function ReportBondEffect({
  bond,
  roster,
}: {
  bond: StrongholdBond;
  roster: StrongholdRecordDetail["roster"];
}) {
  const eyebrow = [
    bondStatus(bond.active),
    bond.layer == null ? "叠层未记录" : `${bond.layer} 层`,
    bond.layer_scope === "team" ? "队伍口径" : null,
  ].filter(Boolean);
  const activation = activationLabel(bond);
  return (
    <ReportEffect
      icon={<ReportBondIcon bond={bond} />}
      name={bond.name ?? bond.bond_id}
      eyebrow={eyebrow.join(" · ")}
      description={bond.description || "同版本盟约效果未收录"}
    >
      {bond.is_core || activation ? (
        <p className={styles.paperCaption}>
          {[bond.is_core ? "核心盟约" : null, activation].filter(Boolean).join(" · ")}
        </p>
      ) : null}
      <BondMembers bond={bond} roster={roster} />
    </ReportEffect>
  );
}
