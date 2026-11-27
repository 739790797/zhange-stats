import type {
  StrongholdBond,
  StrongholdMatch,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";

import { parseBeijing } from "@/shared/lib/time";
import { portraitSrc } from "./assets";

export type ReportPlayer = { id: string; own: boolean; records: StrongholdRecordDetail[] };

export function isOwnView(match: StrongholdMatch, record: StrongholdRecordDetail) {
  return record.is_own || record.id === match.my_record_id;
}

export function groupReportPlayers(match: StrongholdMatch): ReportPlayer[] {
  const players = new Map<string, ReportPlayer>();
  for (const record of match.views ?? []) {
    const id = record.player_group_id ?? record.id;
    const own = isOwnView(match, record);
    const existing = players.get(id);
    if (existing) {
      existing.records.push(record);
      existing.own ||= own;
    } else {
      players.set(id, { id, own, records: [record] });
    }
  }
  return [...players.values()];
}

export function initialReportView(match: StrongholdMatch, requestedView?: string | null) {
  const views = match.views ?? [];
  return (
    views.find(({ id }) => id === requestedView) ??
    views.find(({ id }) => id === match.my_record_id) ??
    views.find((record) => isOwnView(match, record)) ??
    views[0]
  );
}

type Operator = NonNullable<StrongholdRecordDetail["roster"]>[number];

export function chessKey(operator: Pick<Operator, "id" | "normal_chess_id">) {
  return operator.normal_chess_id ?? operator.id;
}

export function belongsToBond(operator: Operator, bond: StrongholdBond) {
  if (bond.activation_rule === "golden") return operator.is_elite === true;
  return bond.operators?.some(({ id }) => id === chessKey(operator)) ?? false;
}

export function reportBondBars(bonds: readonly StrongholdBond[]) {
  const ordered = [...bonds].sort((a, b) => (b.layer ?? -1) - (a.layer ?? -1));
  const peak = Math.max(0, ...ordered.map(({ layer }) => layer ?? 0));
  return ordered.map((bond) => ({
    bond,
    fill: peak ? Math.max(0, bond.layer ?? 0) / peak : 0,
  }));
}

export function reportDuration(start?: string | null, end?: string | null) {
  const elapsed = (parseBeijing(end).valueOf() - parseBeijing(start).valueOf()) / 1000;
  if (!Number.isFinite(elapsed) || elapsed < 0) return null;
  return { minutes: Math.floor(elapsed / 60), seconds: Math.floor(elapsed % 60) };
}

export function reportPortraits(id?: string | null, phase?: number | null) {
  if (!id) return [];
  const key = encodeURIComponent(id);
  const base = portraitSrc(key, 0);
  return phase === 2 ? [portraitSrc(key, 2), base] : [base];
}

export function bondStatus(active?: boolean | null) {
  return active == null ? "点亮状态未知" : active ? "本局已点亮" : "本局未点亮";
}
