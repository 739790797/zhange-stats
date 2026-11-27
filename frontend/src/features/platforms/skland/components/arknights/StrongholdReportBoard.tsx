import { FlagOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Empty } from "antd";
import { useId, useState } from "react";
import type {
  StrongholdMatch,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { formatBeijing } from "@/shared/lib/time";
import { BattleIcon, BattleScope, EffectPopup } from "./StrongholdBattleUI";
import { ReportOverview } from "./StrongholdReportData";
import { ReportEffect } from "./StrongholdReportEffects";
import { ReportRoster } from "./StrongholdReportRoster";
import { roleLabel } from "./strongholdLabels";
import { groupReportPlayers, initialReportView, isOwnView } from "./strongholdReportModel";
import styles from "./StrongholdReport.module.css";

const jointSeats = 4;

function Strategy({ record }: { record: StrongholdRecordDetail }) {
  const name = record.strategy_name ?? record.strategy_id;
  const icon = (
    <BattleIcon
      className={styles.reportIcon}
      src={record.strategy_icon_url}
      fallback={<FlagOutlined />}
    />
  );
  if (!name && !record.strategy_icon_url && !record.strategy_description) {
    return (
      <div className={styles.seatStrategy}>
        {icon}
        <span>策略未记录</span>
      </div>
    );
  }
  return (
    <EffectPopup
      className={styles.seatStrategy}
      label={`${roleLabel(record.role_name)}的策略：${name ?? "名称未记录"}`}
      placement="right"
      tone="paper"
      content={
        <ReportEffect
          icon={icon}
          name={name ?? "策略名称未记录"}
          eyebrow={record.strategy_promoter ? `发起 · ${record.strategy_promoter}` : null}
          description={record.strategy_description || "同版本策略效果未收录"}
        >
          {record.strategy_initial_hp != null ? (
            <p className={styles.paperCaption}>初始生命值 {record.strategy_initial_hp}</p>
          ) : null}
        </ReportEffect>
      }
    >
      {icon}
      <span>{name ?? "策略名称未记录"}</span>
    </EffectPopup>
  );
}

function ReportMeta({
  match,
  record,
}: {
  match: StrongholdMatch;
  record?: StrongholdRecordDetail;
}) {
  const ended = record?.ended_at ?? match.ended_at;
  const started = record?.battle.started_at;
  const date = formatBeijing(ended, "YYYY-MM-DD");
  const endClock = formatBeijing(ended, "HH:mm:ss");
  const startClock = formatBeijing(
    started,
    formatBeijing(started, "YYYY-MM-DD") === date ? "HH:mm:ss" : "YYYY-MM-DD HH:mm:ss",
  );
  return (
    <div className={styles.matchMeta}>
      <BattleScope scope={match} version={match.version?.label} />
      <div className={styles.matchClock}>
        <span>{date}</span>
        <div>
          {started && startClock !== "—" ? (
            <>
              <time dateTime={started}>{startClock}</time> –{" "}
            </>
          ) : null}
          <time dateTime={ended}>{endClock}</time> <small>UTC+8</small>
        </div>
      </div>
    </div>
  );
}

export function StrongholdReportBoard({
  match,
  requestedView,
}: {
  match: StrongholdMatch;
  requestedView: string | null;
}) {
  const overviewPanel = useId();
  const rosterPanel = useId();
  const variantSelect = useId();
  const [selected, setSelected] = useState(() => initialReportView(match, requestedView)?.id);
  const record =
    match.views?.find(({ id }) => id === selected) ?? initialReportView(match, requestedView);
  const players = groupReportPlayers(match);
  if (!record)
    return (
      <>
        <ReportMeta match={match} />
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无角色战报" />
      </>
    );
  const activePlayer = players.find(({ records }) => records.includes(record))!;
  const joint = match.mode_type === "multi";
  const seatsPerPage = joint ? jointSeats : players.length;
  const pageCount = Math.ceil(players.length / seatsPerPage);
  const page = Math.floor(players.indexOf(activePlayer) / seatsPerPage);
  const seats = players.slice(page * seatsPerPage, (page + 1) * seatsPerPage);
  const representative = (player: (typeof players)[number]) =>
    player === activePlayer
      ? record
      : (player.records.find((view) => isOwnView(match, view)) ?? player.records[0]);
  const changeSeatPage = (next: number) =>
    setSelected(representative(players[next * seatsPerPage]).id);
  return (
    <div className={styles.board}>
      <ReportMeta match={match} record={record} />
      <div className={styles.reportLayout}>
        <div className={styles.sidebar}>
          <aside className={styles.seats} aria-label="对局玩家">
            <header className={`${styles.sectionHeading} ${styles.seatHeading}`}>
              <h4>{joint ? "玩家席位" : "玩家视角"}</h4>
              <span>
                {seats.length} / {seatsPerPage}
              </span>
            </header>
            <ol className={styles.seatList}>
              {Array.from({ length: seatsPerPage }, (_, index) => {
                const player = seats[index];
                const number = String(page * seatsPerPage + index + 1).padStart(2, "0");
                if (!player) {
                  return (
                    <li className={styles.emptySeat} key={`empty-${index}`}>
                      <span className={styles.seatNumber}>{number}</span>
                      <span>无可用战报</span>
                    </li>
                  );
                }
                const view = representative(player);
                const name = roleLabel(view.role_name);
                return (
                  <li
                    className={styles.seat}
                    key={player.id}
                    data-own={player.own}
                    data-selected={player === activePlayer}
                  >
                    <button
                      className={styles.seatSelect}
                      type="button"
                      aria-pressed={player === activePlayer}
                      aria-controls={`${overviewPanel} ${rosterPanel}`}
                      onClick={() => setSelected(view.id)}
                    >
                      <span className={styles.seatNumber}>{number}</span>
                      <strong>{name}</strong>
                      {player.own ? <span className={styles.ownMark}>本人</span> : null}
                    </button>
                    <Strategy key={view.id} record={view} />
                  </li>
                );
              })}
            </ol>
            {pageCount > 1 ? (
              <div className={styles.seatPager} aria-label="玩家席分页">
                <button
                  type="button"
                  aria-label="上一组玩家"
                  disabled={page === 0}
                  onClick={() => changeSeatPage(page - 1)}
                >
                  <LeftOutlined />
                </button>
                <span>
                  {page + 1} / {pageCount}
                </span>
                <button
                  type="button"
                  aria-label="下一组玩家"
                  disabled={page + 1 === pageCount}
                  onClick={() => changeSeatPage(page + 1)}
                >
                  <RightOutlined />
                </button>
              </div>
            ) : null}
          </aside>
          <ReportOverview
            key={record.id}
            id={overviewPanel}
            record={record}
            result={joint ? match.success : (record.completed ?? match.success)}
          />
        </div>
        <ReportRoster
          key={record.id}
          id={rosterPanel}
          record={record}
          selection={
            activePlayer.records.length > 1 ? (
              <label className={styles.variant} htmlFor={variantSelect}>
                <span>战报视角</span>
                <select
                  id={variantSelect}
                  value={record.id}
                  onChange={(event) => setSelected(event.target.value)}
                >
                  {activePlayer.records.map((view, i) => (
                    <option key={view.id} value={view.id}>
                      视角 {i + 1}
                      {isOwnView(match, view) ? " · 本人" : ""}
                    </option>
                  ))}
                </select>
              </label>
            ) : null
          }
        />
      </div>
    </div>
  );
}
