import type {
  StrongholdMatch,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";

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

export function pickedChessIds(roster: StrongholdRecordDetail["roster"]) {
  // Without the version mapping only an exact chess ID is safe to mark.
  return new Set(roster?.map((operator) => operator.normal_chess_id ?? operator.id));
}

export function bondLayerScale(peak: number) {
  let step = 250;
  if (peak > 1000) {
    const target = peak / 4;
    const magnitude = 10 ** Math.floor(Math.log10(target));
    step = ([1, 2, 2.5, 5, 10].find((value) => value * magnitude >= target) ?? 10) * magnitude;
  }
  const ticks = [4, 3, 2, 1, 0].map((multiple) => multiple * step);
  return { ceiling: ticks[0], ticks };
}
