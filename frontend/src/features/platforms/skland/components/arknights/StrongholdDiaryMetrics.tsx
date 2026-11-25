import { CaretRightOutlined, DeploymentUnitOutlined, TrophyOutlined } from "@ant-design/icons";
import {
  type StrongholdCommunity,
  type StrongholdMember,
} from "@/features/platforms/skland/api/strongholdApi";
import { Link } from "react-router-dom";
import { EffectLabel } from "./StrongholdBattleUI";
import { roleNamesLabel } from "./strongholdLabels";
import styles from "./ArknightsStronghold.module.css";

type MemberLink = (id: number) => string;

export function DiaryMember({ member, link }: { member: StrongholdMember; link: MemberLink }) {
  return (
    <Link className={styles.member} to={link(member.id)} preventScrollReset>
      {roleNamesLabel(member.role_names)}
    </Link>
  );
}

export function StrongholdDiaryMetrics({
  data,
  link,
}: {
  data: StrongholdCommunity;
  link: MemberLink;
}) {
  const { ranking, popular_bonds: popular, layers, coverage } = data;
  return (
    <section className={styles.diaryStats} aria-label="日报统计">
      <header className={styles.diaryStatus}>
        <span>全站 · {coverage.matches} 局</span>
      </header>
      <div className={styles.diarySummary}>
        <section>
          <h4>
            <TrophyOutlined /> 卫戍大王
          </h4>
          {ranking.length ? (
            <ol className={styles.rankList}>
              {ranking.map(({ rank, member, wins, rounds }) => (
                <li key={member.id}>
                  <span className={styles.rankNumber}>{String(rank).padStart(2, "0")}</span>
                  <DiaryMember member={member} link={link} />
                  <strong>
                    {wins} <small>次通关</small>
                  </strong>
                  <span className={styles.rankRounds}>
                    {rounds ?? "—"}
                    {rounds != null ? " 回合" : ""}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className={styles.emptyLine}>当日暂无通关记录</p>
          )}
        </section>
        <section>
          <h4>
            <DeploymentUnitOutlined /> 今日轮椅
          </h4>
          {popular.length ? (
            <ul className={styles.popularList}>
              {popular.map((bond) => (
                <li key={`${bond.version_key ?? ""}:${bond.bond_id}`}>
                  <span className={styles.metricBond}>
                    <EffectLabel
                      icon={bond.icon_url}
                      name={bond.name ?? bond.bond_id}
                      description={bond.description}
                    />
                    {bond.version_label ? <small>{bond.version_label}</small> : null}
                  </span>
                  <strong>
                    {bond.matches} <small>局</small>
                  </strong>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.emptyLine}>当日暂无已激活盟约</p>
          )}
        </section>
      </div>
      <section className={styles.layerStats}>
        <header>
          <h4>成员视角叠层</h4>
          <span className={styles.muted}>
            计入叠层 {coverage.roles_with_layers} / {coverage.records} 份战报 · 有盟约记录{" "}
            {coverage.roles_with_bonds} 份
          </span>
        </header>
        {layers.length ? (
          <p className={styles.layerNote}>
            累计各角色战报的记录值，不等于队伍总叠层或个人实际产出。
          </p>
        ) : null}
        {coverage.roles_with_conflicting_layers ? (
          <p className={styles.layerNote}>
            {coverage.roles_with_conflicting_layers} 个对局视角存在叠层冲突，冲突值未计入。
          </p>
        ) : null}
        {layers.length ? (
          <div className={styles.layerList}>
            {layers.map((bond) => {
              const top = bond.contributors.filter(
                ({ layers }) => layers > 0 && layers === bond.contributors[0]?.layers,
              );
              return (
                <details key={`${bond.version_key ?? ""}:${bond.bond_id}`}>
                  <summary>
                    <CaretRightOutlined className={styles.chevron} />
                    <span className={styles.metricBond}>
                      <EffectLabel
                        icon={bond.icon_url}
                        name={bond.name ?? bond.bond_id}
                        description={bond.description}
                      />
                      {bond.version_label ? <small>{bond.version_label}</small> : null}
                    </span>
                    <span className={styles.layerLeader}>
                      {top.length
                        ? `视角累计最高 ${top.map(({ member }) => roleNamesLabel(member.role_names)).join("、")}`
                        : ""}
                    </span>
                    <strong>
                      {bond.layers} <small>层</small>
                    </strong>
                  </summary>
                  <ul className={styles.contributionList}>
                    {bond.contributors.map(({ member, layers }) => (
                      <li key={member.id}>
                        <DiaryMember member={member} link={link} />
                        <span>{layers} 层</span>
                      </li>
                    ))}
                    {bond.unattributed_layers > 0 ? (
                      <li>
                        <span>未归属成员</span>
                        <span>{bond.unattributed_layers} 层</span>
                      </li>
                    ) : null}
                    {bond.team_layers != null ? (
                      <li>
                        <span>队伍记录（单列）</span>
                        <span>{bond.team_layers} 层</span>
                      </li>
                    ) : null}
                    {!bond.contributors.length &&
                    bond.unattributed_layers === 0 &&
                    bond.team_layers == null ? (
                      <li>没有可归属到成员的记录</li>
                    ) : null}
                  </ul>
                </details>
              );
            })}
          </div>
        ) : (
          <p className={styles.emptyLine}>当日暂无可统计的叠层记录</p>
        )}
      </section>
    </section>
  );
}
