import { FlagOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import { Empty } from "antd";
import { useId, useState } from "react";
import type {
  StrongholdMatch,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { BattleIcon, EffectPopup } from "./StrongholdBattleUI";
import { ReportBondChart, ReportOtherFacts, ReportRoster } from "./StrongholdReportData";
import { roleLabel } from "./strongholdLabels";
import { groupReportPlayers, initialReportView, isOwnView } from "./strongholdReportModel";
import styles from "./StrongholdReport.module.css";

const jointSeats = 4;

function Strategy({ record }: { record: StrongholdRecordDetail }) {
  const name = record.strategy_name ?? record.strategy_id;
  const icon = (
    <BattleIcon kind="strategy" src={record.strategy_icon_url} fallback={<FlagOutlined />} />
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
      content={
        <>
          <div className={styles.effectHeading}>
            {icon}
            <div>
              <strong>{name ?? "策略名称未记录"}</strong>
              {record.strategy_promoter ? <small>发起 · {record.strategy_promoter}</small> : null}
            </div>
          </div>
          {record.strategy_initial_hp != null ? (
            <div className={styles.effectStats}>
              <strong>初始生命值 {record.strategy_initial_hp}</strong>
            </div>
          ) : null}
          <p className={styles.effectText}>
            {record.strategy_description || "同版本策略效果未收录"}
          </p>
        </>
      }
    >
      {icon}
      <span>{name ?? "策略名称未记录"}</span>
    </EffectPopup>
  );
}

export function StrongholdReportBoard({
  match,
  requestedView,
}: {
  match: StrongholdMatch;
  requestedView: string | null;
}) {
  const perspectivePanel = useId();
  const variantSelect = useId();
  const [selected, setSelected] = useState(() => initialReportView(match, requestedView)?.id);
  const record =
    match.views?.find(({ id }) => id === selected) ?? initialReportView(match, requestedView);
  const players = groupReportPlayers(match);
  if (!record) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无角色战报" />;
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
      <aside className={styles.seats} aria-label="对局玩家">
        <header className={styles.seatHeading}>
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
                  aria-controls={perspectivePanel}
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
      <div
        id={perspectivePanel}
        className={styles.perspective}
        aria-label={`${roleLabel(record.role_name)}的战报`}
      >
        <ReportRoster
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
        <ReportBondChart key={`bonds-${record.id}`} record={record} />
        <ReportOtherFacts key={`facts-${record.id}`} record={record} />
      </div>
    </div>
  );
}
