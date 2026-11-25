import {
  AppstoreOutlined,
  BarChartOutlined,
  CheckOutlined,
  FlagOutlined,
  StarFilled,
  UserOutlined,
} from "@ant-design/icons";
import { useState, type CSSProperties, type ReactNode } from "react";
import type {
  StrongholdBond,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { eliteIconSrc, portraitSrc, professionIconSrc } from "./assets";
import { GAME_RES } from "./constants";
import { BattleIcon, EffectPopup } from "./StrongholdBattleUI";
import { bondLayerScale, pickedChessIds } from "./strongholdReportModel";
import styles from "./StrongholdReport.module.css";

const tierLabels = ["", "I", "II", "III", "IV", "V", "VI"];

function statusLabel(active?: boolean | null) {
  return active == null ? "激活状态未知" : active ? "已激活" : "未激活";
}

function activationLabel(bond: StrongholdBond) {
  if (bond.activation_count == null) return null;
  if (bond.activation_rule === "at_most") return `场上至多 ${bond.activation_count} 名所属干员`;
  if (bond.activation_rule === "golden") return `激活需 ${bond.activation_count} 名精锐干员`;
  return `激活需 ${bond.activation_count} 名所属干员`;
}

function BondEffect({ bond, picked }: { bond: StrongholdBond; picked: Set<string> }) {
  const activation = activationLabel(bond);
  return (
    <>
      <div className={styles.effectHeading}>
        <BattleIcon kind="bond" src={bond.icon_url} />
        <div>
          <strong>{bond.name ?? bond.bond_id}</strong>
          <small>
            {[bond.is_core ? "核心盟约" : null, activation].filter(Boolean).join(" · ")}
          </small>
        </div>
      </div>
      <div className={styles.effectStats}>
        <strong>{bond.layer == null ? "叠层未记录" : `${bond.layer} 层`}</strong>
        <span data-active={bond.active === true}>{statusLabel(bond.active)}</span>
        {bond.layer_scope === "team" ? <span>队伍口径</span> : null}
      </div>
      <p className={styles.effectText}>{bond.description || "同版本盟约效果未收录"}</p>
      {bond.active === true && bond.show_operators !== false ? (
        <div className={styles.affiliation}>
          <h5>盟约所属干员</h5>
          {bond.operators?.length ? (
            <ul className={styles.affiliates}>
              {bond.operators.map((operator) => {
                const present = picked.has(operator.id);
                return (
                  <li key={operator.id}>
                    <div className={styles.affiliatePortrait} data-picked={present}>
                      <BattleIcon
                        src={`${GAME_RES}/avatar/${encodeURIComponent(operator.char_id)}.png`}
                        fallback={<UserOutlined />}
                      />
                      {operator.tier != null && operator.tier > 0 ? (
                        <span className={styles.affiliateTier} aria-label={`${operator.tier} 阶`}>
                          {tierLabels[operator.tier] ?? operator.tier}
                        </span>
                      ) : null}
                      {present ? (
                        <span
                          className={styles.pickMark}
                          role="img"
                          aria-label="本视角出战"
                          title="本视角出战"
                        >
                          <CheckOutlined aria-hidden="true" />
                        </span>
                      ) : null}
                    </div>
                    <span>{operator.name ?? "干员名未收录"}</span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className={styles.effectText}>
              {bond.operators ? "没有所属干员" : "同版本所属干员未收录"}
            </p>
          )}
        </div>
      ) : null}
    </>
  );
}

export function ReportBondChart({ record }: { record: StrongholdRecordDetail }) {
  const ordered = [...(record.bonds ?? [])].sort(
    (left, right) => (right.layer ?? -1) - (left.layer ?? -1),
  );
  const peak = Math.max(0, ...ordered.map(({ layer }) => layer ?? 0));
  const { ceiling, ticks } = bondLayerScale(peak);
  const picked = pickedChessIds(record.roster);
  return (
    <section className={styles.dataBand} aria-label="盟约叠层统计">
      <header className={styles.dataHeading}>
        <h4>
          <BarChartOutlined /> 盟约叠层
        </h4>
        {ordered.length ? (
          <div className={styles.chartLegend}>
            <span data-legend="active">已激活</span>
            <span data-legend="other">未激活 / 未知</span>
            {ordered.some(({ layer }) => layer == null) ? <span>— 未记录叠层</span> : null}
          </div>
        ) : null}
      </header>
      {ordered.length ? (
        <figure
          className={styles.chart}
          aria-label={`盟约与叠层统计图，纵轴 0 至 ${ceiling} 层`}
          style={{ "--axis-digits": String(ceiling).length } as CSSProperties}
        >
          <div className={styles.chartAxisLabel}>层数</div>
          <div className={styles.chartBody}>
            <div className={styles.chartTicks} aria-hidden="true">
              {ticks.map((tick) => (
                <span key={tick}>{tick}</span>
              ))}
            </div>
            <div className={styles.chartScroll}>
              <div
                className={styles.chartColumns}
                style={{
                  minWidth: ordered.length * 64,
                  gridTemplateColumns: `repeat(${ordered.length}, minmax(0, 1fr))`,
                }}
              >
                <div className={styles.chartGrid} aria-hidden="true">
                  {ticks.map((tick) => (
                    <span key={tick} />
                  ))}
                </div>
                {ordered.map((bond) => {
                  const name = bond.name ?? bond.bond_id;
                  return (
                    <EffectPopup
                      key={bond.bond_id}
                      className={styles.chartColumn}
                      label={`${name}，${bond.layer == null ? "叠层未记录" : `${bond.layer} 层`}，${statusLabel(bond.active)}`}
                      content={<BondEffect bond={bond} picked={picked} />}
                    >
                      <span className={styles.barTrack} aria-hidden="true">
                        <span
                          className={styles.bar}
                          data-value={
                            bond.layer == null ? "missing" : bond.layer === 0 ? "zero" : "known"
                          }
                          data-active={bond.active === true}
                          style={
                            bond.layer ? { height: `${(bond.layer / ceiling) * 100}%` } : undefined
                          }
                        >
                          <span className={styles.barValue}>{bond.layer ?? "—"}</span>
                        </span>
                      </span>
                      <span className={styles.barLabel} aria-hidden="true">
                        <BattleIcon kind="bond" src={bond.icon_url} /> <span>{name}</span>
                      </span>
                    </EffectPopup>
                  );
                })}
              </div>
            </div>
          </div>
        </figure>
      ) : (
        <p className={styles.emptyLine}>
          {record.bonds ? "该视角没有盟约记录" : "盟约数据暂不可用"}
        </p>
      )}
    </section>
  );
}

function Gear({
  icon,
  name,
  description,
  tier,
  caption,
  missing = "暂无官方效果说明",
}: {
  icon?: string | null;
  name: string;
  description?: string | null;
  tier?: number | null;
  caption?: string;
  missing?: string;
}) {
  return (
    <EffectPopup
      className={styles.gear}
      label={name}
      content={
        <>
          <div className={styles.effectHeading}>
            <BattleIcon src={icon} fallback={<AppstoreOutlined />} />
            <div>
              <strong>{name}</strong>
              {tier != null && tier > 0 ? <small>{tier} 阶装备</small> : null}
              {caption ? <small>{caption}</small> : null}
            </div>
          </div>
          <p className={styles.effectText}>{description || missing}</p>
        </>
      }
    >
      <BattleIcon src={icon} fallback={<AppstoreOutlined />} />
    </EffectPopup>
  );
}

type Operator = NonNullable<StrongholdRecordDetail["roster"]>[number];

function effectCaption(effect: Operator["skill"], kind: "skill" | "module") {
  if (!effect) return undefined;
  const configured = effect.config_level;
  const level = effect.reference_level;
  return [
    kind === "skill" ? "技能" : "模组",
    configured != null && !(kind === "module" && configured === 0)
      ? `棋子配置 ${configured} 级`
      : null,
    kind === "module" && configured === 0 ? "棋子配置未启用" : null,
    effect.description ? `干员资料${level != null ? ` · ${level} 级` : ""}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function OperatorCard({ operator }: { operator: Operator }) {
  const [failed, setFailed] = useState(false);
  const name = operator.name || operator.char_id || operator.id;
  const elite = operator.is_elite == null ? "精锐未知" : operator.is_elite ? "精锐" : "普通";
  return (
    <li className={styles.operator} data-elite={operator.is_elite === true}>
      <div className={styles.portrait}>
        {operator.char_id && !failed ? (
          <img
            className={styles.operatorArt}
            src={portraitSrc(operator.char_id, operator.phase ?? 0)}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
          />
        ) : (
          <BattleIcon
            src={
              operator.char_id
                ? `${GAME_RES}/avatar/${encodeURIComponent(operator.char_id)}.png`
                : null
            }
            fallback={<UserOutlined />}
          />
        )}
        {operator.tier != null && operator.tier > 0 ? (
          <span className={styles.tier}>{tierLabels[operator.tier] ?? operator.tier} 阶</span>
        ) : null}
        {operator.profession ? (
          <img
            className={styles.profession}
            src={professionIconSrc(operator.profession)}
            alt=""
            loading="lazy"
          />
        ) : null}
      </div>
      <div className={styles.operatorMeta}>
        <strong>{name}</strong>
        <div className={styles.operatorFlags}>
          <span className={styles.eliteFlag} data-elite={operator.is_elite === true}>
            {operator.is_elite ? <StarFilled /> : null}
            {elite}
          </span>
          {operator.phase != null || operator.level != null ? (
            <span className={styles.operatorLevel}>
              {operator.phase != null ? (
                <img
                  src={eliteIconSrc(operator.phase)}
                  alt={`精英 ${operator.phase}`}
                  title={`精英 ${operator.phase}`}
                />
              ) : null}
              {operator.level != null ? `Lv.${operator.level}` : null}
            </span>
          ) : null}
          {operator.merge_level != null && operator.merge_level > 0 ? (
            <span title={`合成等级 ${operator.merge_level}`}>合成 {operator.merge_level}</span>
          ) : null}
        </div>
      </div>
      <div className={styles.operatorKit} role="group" aria-label={`${name}的装备`}>
        {operator.equipment?.length ? (
          <div className={styles.gearRow}>
            {operator.equipment.map((item, index) => (
              <Gear
                key={`${item.id}-${index}`}
                icon={item.icon_url}
                name={item.name ?? item.id}
                description={item.description}
                tier={item.tier}
              />
            ))}
          </div>
        ) : (
          <small>{operator.equipment ? "未装备" : "装备未记录"}</small>
        )}
        {operator.traits?.length || operator.skill_id || operator.module_id ? (
          <div className={styles.gearRow} role="group" aria-label={`${name}的技能、特质和模组`}>
            {operator.traits?.map((trait) => (
              <Gear
                key={trait.id}
                icon={trait.icon_url}
                name={trait.name ?? "干员特质"}
                description={trait.description}
              />
            ))}
            {operator.skill_id ? (
              <Gear
                icon={`${GAME_RES}/skill/skill_icon_${encodeURIComponent(operator.skill_id)}.png`}
                name={operator.skill?.name ?? `${name}的技能`}
                description={operator.skill?.description}
                caption={effectCaption(operator.skill, "skill")}
                missing="同版本技能效果未收录"
              />
            ) : null}
            {operator.module_id ? (
              <Gear
                icon={operator.module?.icon_url}
                name={operator.module?.name ?? `${name}的模组`}
                description={operator.module?.description}
                caption={effectCaption(operator.module, "module")}
                missing={
                  operator.module?.config_level === 0
                    ? "该棋子配置未启用模组效果"
                    : "同版本模组效果未收录"
                }
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}

export function ReportRoster({
  record,
  selection,
}: {
  record: StrongholdRecordDetail;
  selection?: ReactNode;
}) {
  return (
    <section className={styles.dataBand} aria-label="出战干员">
      <header className={styles.dataHeading}>
        <h4>
          <AppstoreOutlined /> 出战干员{" "}
          {record.roster ? <small>{record.roster.length} 名</small> : null}
        </h4>
        <div className={styles.rosterTools}>
          {selection}
          {record.pass_round != null ? <small>{record.pass_round} 回合</small> : null}
        </div>
      </header>
      {record.roster?.length ? (
        <ul className={styles.roster} key={record.id}>
          {record.roster.map((operator, i) => (
            <OperatorCard key={`${operator.id}-${i}`} operator={operator} />
          ))}
        </ul>
      ) : (
        <p className={styles.emptyLine}>
          {record.roster ? "该视角没有出战干员" : "阵容数据暂不可用"}
        </p>
      )}
    </section>
  );
}

function elapsed(start: string, end: string) {
  const seconds = Math.floor((new Date(end).getTime() - new Date(start).getTime()) / 1000);
  return Number.isFinite(seconds) && seconds >= 0
    ? `${Math.floor(seconds / 60)}分 ${String(seconds % 60).padStart(2, "0")}秒`
    : null;
}

export function ReportOtherFacts({ record }: { record: StrongholdRecordDetail }) {
  const { battle } = record;
  const duration = battle.started_at ? elapsed(battle.started_at, record.ended_at) : null;
  const trophyDelta =
    battle.trophy_before != null && battle.trophy_after != null
      ? battle.trophy_after - battle.trophy_before
      : null;
  const teamResult = record.mode_type === "multi" ? battle.team_completed : null;
  const facts = [
    ["个人结果", record.completed == null ? null : record.completed ? "模拟完成" : "模拟中断"],
    ["该视角的队伍结果", teamResult == null ? null : teamResult ? "模拟完成" : "模拟中断"],
    ["称号", battle.title],
    [
      "奖杯",
      trophyDelta == null
        ? null
        : `${trophyDelta > 0 ? "+" : ""}${trophyDelta}（${battle.trophy_before} → ${battle.trophy_after}）`,
    ],
    ["用时", duration],
    ["击杀", battle.kill_count],
    ["认证消耗", battle.coin_cost],
    ["同步次数", battle.sync_count],
  ].filter(([, value]) => value != null);
  if (!facts.length && !battle.bosses?.length) return null;
  return (
    <details className={styles.otherFacts}>
      <summary>其他战斗记录</summary>
      {facts.length ? (
        <dl>
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {battle.bosses?.length ? (
        <ul className={styles.bosses} aria-label="首领">
          {battle.bosses.map((boss, i) => (
            <li key={`${boss.id}-${i}`}>
              <BattleIcon
                src={
                  boss.enemy_id
                    ? `${GAME_RES}/enemy/${encodeURIComponent(boss.enemy_id)}.png`
                    : null
                }
                fallback={<FlagOutlined />}
              />
              <span>
                {boss.name ?? (boss.hidden ? "隐藏首领" : "首领")}{" "}
                {boss.hidden && boss.name ? <small>隐藏首领 · </small> : null}
                <small>
                  {boss.killed == null ? "击杀未知" : boss.killed ? "已击杀" : "未击杀"}
                </small>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </details>
  );
}
