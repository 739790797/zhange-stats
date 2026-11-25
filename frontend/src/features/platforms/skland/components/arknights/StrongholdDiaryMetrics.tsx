import { FlagOutlined } from "@ant-design/icons";
import { Avatar } from "antd";
import type {
  StrongholdCommunity,
  StrongholdMember,
} from "@/features/platforms/skland/api/strongholdApi";
import { BattleIcon, EffectPopup } from "./StrongholdBattleUI";
import { roleNamesLabel } from "./strongholdLabels";
import sharedStyles from "./ArknightsStronghold.module.css";
import styles from "./StrongholdDiary.module.css";
import reportStyles from "./StrongholdReport.module.css";

type Strategy = StrongholdCommunity["strategies"][number];
type Covenant = StrongholdCommunity["covenants"][number];
type Layer = StrongholdCommunity["layers"][number];

const countFormat = new Intl.NumberFormat("zh-CN");
const shareFormat = new Intl.NumberFormat("zh-CN", { style: "percent", maximumFractionDigits: 1 });
const chartColors = [
  "#20896f",
  "#bd7240",
  "#536aa4",
  "#a14f6b",
  "#70813e",
  "#397c98",
  "#947249",
  "#74598f",
];

function covenantKey(covenant: Covenant | Layer) {
  return JSON.stringify([covenant.version_key, covenant.bond_id]);
}

const strategyName = (strategy: Strategy) => strategy.name || strategy.strategy_id;

export function DiaryMember({ member }: { member: StrongholdMember }) {
  return <span className={sharedStyles.member}>{roleNamesLabel(member.role_names)}</span>;
}

function Podium({
  ranking,
  matches,
}: {
  ranking: StrongholdCommunity["ranking"];
  matches: number;
}) {
  return (
    <section className={styles.podiumBand} aria-label="卫戍大王">
      <header className={styles.heading}>
        <h3>卫戍大王</h3>
        <span>共 {countFormat.format(matches)} 局</span>
      </header>
      {ranking.length ? (
        <ol className={styles.podium} aria-label="卫戍大王前三名">
          {ranking.slice(0, 3).map(({ rank, member, matches: played }) => {
            const name = roleNamesLabel(member.role_names);
            const count = countFormat.format(played);
            return (
              <li
                key={member.id}
                data-rank={rank}
                aria-label={`第 ${rank} 名，${name}，参战 ${count} 局`}
              >
                <div className={styles.podiumEntry}>
                  <span className={styles.portraitSlot} aria-hidden="true">
                    <span className={styles.portrait}>
                      <Avatar
                        shape="square"
                        src={member.avatar_url || undefined}
                        className={styles.avatar}
                      >
                        {Array.from(member.nickname || name)[0]}
                      </Avatar>
                      <span className={styles.medal}>{String(rank).padStart(2, "0")}</span>
                    </span>
                  </span>
                  <strong className={styles.roleName}>{name}</strong>
                  <small className={styles.rankCount}>参战 {count} 局</small>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className={styles.empty}>当前筛选暂无参战记录</p>
      )}
    </section>
  );
}

function StrategyIcon({ strategy }: { strategy: Strategy }) {
  return <BattleIcon kind="strategy" src={strategy.icon_url} fallback={<FlagOutlined />} />;
}

function StrategyDetail({ strategy, total }: { strategy: Strategy; total: number }) {
  return (
    <>
      <div className={reportStyles.effectHeading}>
        <StrategyIcon strategy={strategy} />
        <strong>{strategyName(strategy)}</strong>
      </div>
      <p className={reportStyles.effectText}>{strategy.description || "同版本策略效果未收录"}</p>
      <p className={styles.detailMeta}>
        {strategy.version_label ? `${strategy.version_label} · ` : ""}
        {countFormat.format(strategy.count)} 次 · {shareFormat.format(strategy.count / total)}
      </p>
    </>
  );
}

function slicePath(start: number, end: number) {
  if (end - start === 1) return "M 50 0 A 50 50 0 1 1 50 100 A 50 50 0 1 1 50 0 Z";
  const point = (fraction: number) => {
    const angle = fraction * 2 * Math.PI;
    return `${50 + 50 * Math.sin(angle)} ${50 - 50 * Math.cos(angle)}`;
  };
  return `M 50 50 L ${point(start)} A 50 50 0 ${end - start > 0.5 ? 1 : 0} 1 ${point(end)} Z`;
}

function StrategyBand({ strategies }: { strategies: readonly Strategy[] }) {
  const total = strategies.reduce((sum, strategy) => sum + strategy.count, 0);
  const showVersions = new Set(strategies.map(({ version_key }) => version_key)).size > 1;
  let start = 0;
  const series = strategies.map((strategy, index) => {
    const end = start + strategy.count;
    const path = slicePath(start / total, end / total);
    start = end;
    return {
      strategy,
      path,
      color: chartColors[index % chartColors.length],
      key: JSON.stringify([strategy.version_key, strategy.strategy_id]),
    };
  });
  return (
    <section className={styles.band} aria-label="策略统计">
      <header className={styles.heading}>
        <h3>策略</h3>
        {total > 0 ? (
          <span>
            {strategies.length} 种 · {countFormat.format(total)} 次使用
          </span>
        ) : null}
      </header>
      {total > 0 ? (
        <div className={styles.strategyLayout}>
          <div className={styles.strategyPie} role="group" aria-label="策略使用分布饼图">
            {series.map(({ strategy, path, color, key }) => (
              <EffectPopup
                key={key}
                className={styles.pieSlice}
                label={`${strategyName(strategy)}${showVersions && strategy.version_label ? ` · ${strategy.version_label}` : ""}，${countFormat.format(strategy.count)} 次，${shareFormat.format(strategy.count / total)}`}
                content={<StrategyDetail strategy={strategy} total={total} />}
              >
                <svg viewBox="-1 -1 102 102" aria-hidden="true" focusable="false">
                  <path d={path} fill={color} vectorEffect="non-scaling-stroke" />
                </svg>
              </EffectPopup>
            ))}
          </div>
          <ol className={styles.strategyRank} aria-label="策略使用前五名">
            {series.slice(0, 5).map(({ strategy, color, key }, index) => (
              <li key={key}>
                <EffectPopup
                  className={styles.strategyEntry}
                  label={`第 ${index + 1} 名，${strategyName(strategy)}${showVersions && strategy.version_label ? ` · ${strategy.version_label}` : ""}，${countFormat.format(strategy.count)} 次`}
                  content={<StrategyDetail strategy={strategy} total={total} />}
                  placement="right"
                >
                  <span className={styles.strategyPlace} aria-hidden="true">
                    {index + 1}
                    <span style={{ backgroundColor: color }} />
                  </span>
                  <StrategyIcon strategy={strategy} />
                  <span className={styles.strategyName}>
                    <strong>{strategyName(strategy)}</strong>
                    {showVersions && strategy.version_label ? (
                      <small>{strategy.version_label}</small>
                    ) : null}
                  </span>
                  <span className={styles.strategyCount}>
                    {countFormat.format(strategy.count)} <small>次</small>
                  </span>
                </EffectPopup>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <p className={styles.empty}>当前筛选暂无策略使用记录</p>
      )}
    </section>
  );
}

function CovenantDetail({ covenant, layer }: { covenant: Covenant; layer?: Layer }) {
  return (
    <>
      <div className={reportStyles.effectHeading}>
        <BattleIcon kind="bond" src={covenant.icon_url} />
        <strong>{covenant.name || covenant.bond_id}</strong>
      </div>
      <p className={reportStyles.effectText}>{covenant.description || "暂无官方效果说明"}</p>
      <p className={styles.detailMeta}>
        {covenant.version_label ? `${covenant.version_label} · ` : ""}
        {covenant.matches ? `${countFormat.format(covenant.matches)} 局激活` : "当前筛选无激活记录"}
        {covenant.matches > 0 && covenant.layers == null ? " · 视角叠层未记录或不可用" : ""}
      </p>
      {layer ? (
        <ul className={styles.contributions} aria-label="成员视角累计">
          {layer.contributors.map(({ member, layers }) => (
            <li key={member.id}>
              <DiaryMember member={member} />
              <span>{countFormat.format(layers)} 层</span>
            </li>
          ))}
          {layer.unattributed_layers > 0 ? (
            <li>
              <span>未归属视角</span>
              <span>{countFormat.format(layer.unattributed_layers)} 层</span>
            </li>
          ) : null}
          {layer.team_layers != null ? (
            <li>
              <span>另计团队口径</span>
              <span>{countFormat.format(layer.team_layers)} 层</span>
            </li>
          ) : null}
        </ul>
      ) : null}
    </>
  );
}

function CovenantBand({ data }: { data: StrongholdCommunity }) {
  const { covenants = [], layers, coverage } = data;
  const stats = new Map(layers.map((row) => [covenantKey(row), row]));
  const showVersions = new Set(covenants.map(({ version_key }) => version_key)).size > 1;
  return (
    <section className={styles.band} aria-label="盟约统计">
      <header className={styles.heading}>
        <h3>盟约</h3>
        {covenants.length ? <span>{covenants.length} 项 · 累计战报视角层数</span> : null}
      </header>
      {covenants.length ? (
        <ul className={styles.covenantGrid} aria-label="盟约目录">
          {covenants.map((covenant) => {
            const key = covenantKey(covenant);
            const name = covenant.name || covenant.bond_id;
            const version = showVersions ? covenant.version_label : null;
            return (
              <li key={key}>
                <EffectPopup
                  className={styles.covenantEntry}
                  label={`${name}${version ? ` · ${version}` : ""}，${covenant.layers == null ? "层数未知" : `总计 ${countFormat.format(covenant.layers)} 层`}`}
                  content={<CovenantDetail covenant={covenant} layer={stats.get(key)} />}
                >
                  <BattleIcon kind="bond" src={covenant.icon_url} />
                  <strong>{name}</strong>
                  <span className={styles.layerTotal}>
                    {covenant.layers == null ? (
                      "未知"
                    ) : (
                      <>
                        {countFormat.format(covenant.layers)} <small>层</small>
                      </>
                    )}
                  </span>
                  {version ? <small className={styles.covenantVersion}>{version}</small> : null}
                </EffectPopup>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={styles.empty}>当前版本暂无盟约资料</p>
      )}
      {coverage.roles_with_conflicting_layers ? (
        <p className={styles.note}>
          {coverage.roles_with_conflicting_layers} 个对局视角的冲突层数未计入。
        </p>
      ) : null}
    </section>
  );
}

export function StrongholdDiaryMetrics({ data }: { data: StrongholdCommunity }) {
  return (
    <section className={styles.metrics} aria-label="日报统计">
      <Podium ranking={data.ranking} matches={data.coverage.matches} />
      <StrategyBand strategies={data.strategies ?? []} />
      <CovenantBand data={data} />
    </section>
  );
}
