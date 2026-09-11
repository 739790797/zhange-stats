import { InputNumber, Select, Slider, Tooltip } from "antd";
import { useState, type ReactNode } from "react";
import type { TarkovWorkbenchStats } from "@/api/guidesApi";
import { formatMoney, formatWeight } from "@/lib/tarkovItemFormat";
import {
  clampWorkbenchEquipErgoPenaltyPct,
  clampWorkbenchStrengthLevel,
  formatWorkbenchAccuracyMoa,
  formatWorkbenchArmStamina,
  formatWorkbenchEed,
  formatWorkbenchErgo,
  formatWorkbenchMuzzleVelocity,
  loadWorkbenchEquipErgoPenaltyPct,
  loadWorkbenchStrengthLevel,
  saveWorkbenchEquipErgoPenaltyPct,
  saveWorkbenchStrengthLevel,
  WORKBENCH_EQUIP_ERGO_PENALTY_MAX,
  WORKBENCH_EQUIP_ERGO_PENALTY_MIN,
  WORKBENCH_STRENGTH_MAX,
  WORKBENCH_STRENGTH_MIN,
  workbenchArmStaminaSeconds,
  workbenchEquipErgoModifier,
  workbenchEvoErgoDelta,
  workbenchOverswing,
} from "@/lib/tarkovWorkbench";
import styles from "./TarkovWorkbenchBuild.module.css";

type AmmoOption = { value: string; label: string };

type Props = {
  stats: TarkovWorkbenchStats | null;
  ammoId: string | null;
  ammoOptions: AmmoOption[];
  hasConflicts: boolean;
  onAmmoChange: (ammoId: string) => void;
  lead?: ReactNode;
};

const EED_HINT =
  "与纸面人机不同，Evo人机工效将装备重量一并纳入计算。两把Evo人机相同的枪操纵性理论上完全一致（过摆行为与开镜速度均相同，除去技能等级等变量影响）。人物重量会影响开镜速度，但不影响过摆。请设置装备人机工效修正以获得准确结果。";

const OVERSWING_HINT =
  "表示开镜后准星是否会摆过中心点。当EED为负时发生。预计偏差 ±2 EED。";

const STRENGTH_HINT =
  "影响站立时手臂耐力耗尽所需秒数，预计偏差 ±0.5s";

const EQUIP_ERGO_HINT =
  "所佩戴装备（头盔、防弹衣、背包、战术背心、面罩、护目镜）的人机工效惩罚总和 - 请根据游戏中的实际装备进行设置。";

function StatInfoTip({
  label,
  children,
}: {
  label?: string;
  children: string;
}) {
  return (
    <Tooltip
      placement="left"
      mouseEnterDelay={0.12}
      mouseLeaveDelay={0.08}
      rootClassName={styles.statInfoTooltip}
      title={
        <div className={styles.statInfoBody}>
          {label ? <strong>{label}</strong> : null}
          {children}
        </div>
      }
    >
      <span
        className={styles.statInfo}
        tabIndex={0}
        aria-label={label ? `${label}说明` : "说明"}
      >
        i
      </span>
    </Tooltip>
  );
}

function StatRow({
  label,
  hintLabel,
  hint,
  children,
}: {
  label: string;
  hintLabel?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.statRow}>
      <span className={styles.statLabel}>
        {label}
        {hint ? <StatInfoTip label={hintLabel}>{hint}</StatInfoTip> : null}
      </span>
      <span className={styles.statValue}>{children}</span>
    </div>
  );
}

export function TarkovWorkbenchStatsPane({
  stats,
  ammoId,
  ammoOptions,
  hasConflicts,
  onAmmoChange,
  lead,
}: Props) {
  const [strength, setStrength] = useState(loadWorkbenchStrengthLevel);
  const [equipPenalty, setEquipPenalty] = useState(
    loadWorkbenchEquipErgoPenaltyPct,
  );

  const ergo = stats?.ergonomics ?? 0;
  const weight = stats?.weight ?? 0;
  const equipErgo = workbenchEquipErgoModifier(equipPenalty);
  const eed = stats
    ? workbenchEvoErgoDelta(ergo, weight, equipErgo)
    : null;
  const armStamina = stats
    ? workbenchArmStaminaSeconds(weight, ergo, strength, equipErgo)
    : null;
  const overswing = stats
    ? workbenchOverswing(ergo, weight, equipErgo)
    : false;

  const persistStrength = (value: number) => {
    const next = clampWorkbenchStrengthLevel(value);
    setStrength(next);
    saveWorkbenchStrengthLevel(next);
  };

  const persistEquipPenalty = (value: number) => {
    const next = clampWorkbenchEquipErgoPenaltyPct(value);
    setEquipPenalty(next);
    saveWorkbenchEquipErgoPenaltyPct(next);
  };

  return (
    <section className={`${styles.pane} ${styles.statsPane}`} aria-label="属性">
      {lead}
      <div className={styles.paneHead}>属性</div>
      <div className={styles.stats}>
        <StatRow label="人机">{formatWorkbenchErgo(stats?.ergonomics)}</StatRow>
        <StatRow label="垂直后坐">
          {stats?.recoil_vertical ?? "—"}
        </StatRow>
        <StatRow label="水平后坐">
          {stats?.recoil_horizontal ?? "—"}
        </StatRow>
        <StatRow label="精确度">
          {formatWorkbenchAccuracyMoa(stats?.accuracy_moa)}
        </StatRow>
        <StatRow label="重量">{formatWeight(stats?.weight)}</StatRow>
        <StatRow
          label="Evo人机Delta"
          hintLabel="Evo人机Delta（EED）： "
          hint={EED_HINT}
        >
          {eed == null ? (
            "—"
          ) : (
            <span className={eed >= 0 ? styles.statGood : styles.statBad}>
              {formatWorkbenchEed(eed)}
            </span>
          )}
        </StatRow>
        <StatRow label="过摆" hintLabel="过摆： " hint={OVERSWING_HINT}>
          {stats ? (
            <span className={overswing ? styles.statBad : styles.statGood}>
              {overswing ? "是" : "否"}
            </span>
          ) : (
            "—"
          )}
        </StatRow>
        <StatRow label="手臂耐力">
          {formatWorkbenchArmStamina(armStamina)}
        </StatRow>
        <StatRow label="瞄具距离">
          {stats?.sighting_range != null ? `${stats.sighting_range} m` : "—"}
        </StatRow>
        <StatRow label="膛口初速">
          {ammoId
            ? formatWorkbenchMuzzleVelocity(stats?.muzzle_velocity)
            : "无弹药"}
        </StatRow>
        <StatRow label="弹匣容量">{stats?.mag_capacity ?? "—"}</StatRow>
        <StatRow label="估价">{formatMoney(stats?.price_rub)}</StatRow>

        {hasConflicts ? (
          <p className={styles.warn}>冲突件已标红，请卸下或更换</p>
        ) : null}

        <div className={styles.statTune}>
          <div className={styles.statTuneTitle}>自身情况</div>
          <div className={styles.statTuneBlock}>
            <div className={styles.statTuneHead}>
              <span className={styles.statLabel}>力量等级</span>
            </div>
            <p className={styles.statTuneHint}>{STRENGTH_HINT}</p>
            <div className={styles.statTuneRow}>
              <Slider
                min={WORKBENCH_STRENGTH_MIN}
                max={WORKBENCH_STRENGTH_MAX}
                value={strength}
                tooltip={{ formatter: null }}
                onChange={persistStrength}
              />
              <InputNumber
                className={styles.statTuneInput}
                size="small"
                controls={false}
                min={WORKBENCH_STRENGTH_MIN}
                max={WORKBENCH_STRENGTH_MAX}
                value={strength}
                onChange={(value) => {
                  if (value == null) return;
                  persistStrength(Number(value));
                }}
              />
            </div>
          </div>
          <div className={styles.statTuneBlock}>
            <div className={styles.statTuneHead}>
              <span className={styles.statLabel}>装备人机工效修正</span>
            </div>
            <p className={styles.statTuneHint}>{EQUIP_ERGO_HINT}</p>
            <div className={styles.statTuneRow}>
              <Slider
                min={WORKBENCH_EQUIP_ERGO_PENALTY_MIN}
                max={WORKBENCH_EQUIP_ERGO_PENALTY_MAX}
                value={equipPenalty}
                tooltip={{ formatter: null }}
                onChange={persistEquipPenalty}
              />
              <InputNumber
                className={styles.statTuneInputWide}
                size="small"
                controls={false}
                min={WORKBENCH_EQUIP_ERGO_PENALTY_MIN}
                max={WORKBENCH_EQUIP_ERGO_PENALTY_MAX}
                value={equipPenalty}
                prefix={equipPenalty ? "-" : undefined}
                suffix="%"
                onChange={(value) => {
                  if (value == null) return;
                  persistEquipPenalty(Number(value));
                }}
              />
            </div>
          </div>
        </div>

        {ammoOptions.length ? (
          <div className={styles.ammo}>
            <div className={styles.statLabel}>弹药</div>
            <Select
              size="small"
              showSearch
              optionFilterProp="label"
              style={{ width: "100%", marginTop: 6 }}
              value={ammoId || undefined}
              options={ammoOptions}
              onChange={onAmmoChange}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
