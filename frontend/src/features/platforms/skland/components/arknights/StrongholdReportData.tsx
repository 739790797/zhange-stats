import { FlagOutlined } from "@ant-design/icons";
import type { ReactNode } from "react";
import type { StrongholdRecordDetail } from "@/features/platforms/skland/api/strongholdApi";
import { GAME_RES } from "./constants";
import { BattleIcon, EffectPopup, ResultMark } from "./StrongholdBattleUI";
import { ReportBondEffect, ReportBondIcon } from "./StrongholdReportEffects";
import { bondStatus, reportBondBars, reportDuration } from "./strongholdReportModel";
import styles from "./StrongholdReport.module.css";

type Boss = NonNullable<StrongholdRecordDetail["battle"]["bosses"]>[number];

function BossList({ bosses }: { bosses?: Boss[] | null }) {
  if (bosses == null) return <span className={styles.missing}>未记录</span>;
  if (!bosses.length) return <span className={styles.missing}>未出现</span>;
  return (
    <ul className={styles.bossList}>
      {bosses.map((boss, index) => (
        <li key={`${boss.id}-${index}`}>
          <BattleIcon
            className={styles.reportIcon}
            src={
              boss.enemy_id ? `${GAME_RES}/enemy/${encodeURIComponent(boss.enemy_id)}.png` : null
            }
            fallback={<FlagOutlined />}
          />
          <strong>{boss.name ?? "名称未记录"}</strong>
          <small data-killed={boss.killed === true}>
            {boss.killed == null ? "击杀未知" : boss.killed ? "已击杀" : "未击杀"}
          </small>
        </li>
      ))}
    </ul>
  );
}

function SummaryRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function MatchFacts({
  record,
  result,
}: {
  record: StrongholdRecordDetail;
  result: boolean | null;
}) {
  const { battle } = record;
  const duration = reportDuration(battle.started_at, record.ended_at);
  const trophyDelta =
    battle.trophy_before != null && battle.trophy_after != null
      ? battle.trophy_after - battle.trophy_before
      : null;
  const uncategorized = battle.bosses?.filter(({ hidden }) => hidden == null);
  const bossesByType = (hidden: boolean) => {
    const bosses = battle.bosses?.filter((boss) => boss.hidden === hidden);
    return !bosses?.length && uncategorized?.length ? undefined : bosses;
  };
  return (
    <section aria-label="对局信息">
      <h4 className={styles.sectionHeading}>对局信息</h4>
      <dl className={styles.facts}>
        <SummaryRow label="通过回合">
          <div className={styles.round}>
            <b>{record.pass_round ?? "—"}</b>
            <span className={styles.outcome} data-result={result ?? "unknown"}>
              <ResultMark result={result} />
            </span>
          </div>
        </SummaryRow>
        <SummaryRow label="用时">
          {duration ? (
            <span className={styles.duration}>
              <b>{duration.minutes}</b> <small>分</small>{" "}
              <b>{String(duration.seconds).padStart(2, "0")}</b> <small>秒</small>
            </span>
          ) : (
            "—"
          )}
        </SummaryRow>
        <SummaryRow label="获得奖杯">
          {trophyDelta == null ? (
            "—"
          ) : (
            <div className={styles.trophy}>
              <b data-delta={Math.sign(trophyDelta)}>
                {trophyDelta > 0 ? `+${trophyDelta}` : trophyDelta}
              </b>
              <small>
                {battle.trophy_before} → {battle.trophy_after}
              </small>
            </div>
          )}
        </SummaryRow>
        <SummaryRow label="击杀数量">
          <b>{battle.kill_count ?? "—"}</b>
        </SummaryRow>
        <SummaryRow label="资金消耗">
          <b>{battle.coin_cost ?? "—"}</b>
        </SummaryRow>
        <SummaryRow label="普通首领">
          <BossList bosses={bossesByType(false)} />
        </SummaryRow>
        <SummaryRow label="隐秘核心">
          <BossList bosses={bossesByType(true)} />
        </SummaryRow>
        {uncategorized?.length ? (
          <SummaryRow label="分类未记录">
            <BossList bosses={uncategorized} />
          </SummaryRow>
        ) : null}
      </dl>
    </section>
  );
}

function ReportBonds({ record }: { record: StrongholdRecordDetail }) {
  const rows = reportBondBars(record.bonds ?? []);
  return (
    <section aria-label="盟约">
      <header className={`${styles.sectionHeading} ${styles.bondHeading}`}>
        <h4>盟约</h4>
        {record.bonds ? (
          <small>已点亮 {record.bonds.filter(({ active }) => active === true).length} 项</small>
        ) : null}
      </header>
      {rows.length ? (
        <ul className={styles.bondList}>
          {rows.map(({ bond, fill }) => {
            const name = bond.name ?? bond.bond_id;
            return (
              <li key={bond.bond_id}>
                <EffectPopup
                  tone="paper"
                  className={styles.bondRow}
                  label={`${name}，${bond.layer == null ? "叠层未记录" : `${bond.layer} 层`}，${bondStatus(bond.active)}`}
                  content={<ReportBondEffect bond={bond} roster={record.roster} />}
                >
                  <ReportBondIcon bond={bond} />
                  <span className={styles.bondName}>{name}</span>
                  <span
                    className={styles.barTrack}
                    data-state={bond.active ?? "unknown"}
                    aria-hidden="true"
                  >
                    <span style={{ width: `${fill * 100}%` }} />
                  </span>
                  <b className={styles.layers}>{bond.layer ?? "—"}</b>
                </EffectPopup>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={styles.emptyLine}>
          {record.bonds ? "该视角没有盟约记录" : "盟约数据暂不可用"}
        </p>
      )}
    </section>
  );
}

export function ReportOverview({
  id,
  record,
  result,
}: {
  id: string;
  record: StrongholdRecordDetail;
  result: boolean | null;
}) {
  return (
    <div id={id} className={styles.overview}>
      <MatchFacts record={record} result={result} />
      <ReportBonds record={record} />
    </div>
  );
}
