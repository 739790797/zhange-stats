/** 对齐 tarkov.dev wipe-details.json：补丁号 + 开始时间。 */

export type TarkovWipeStart = {
  name: string;
  start: string;
};

export type TarkovWipeRow = TarkovWipeStart & {
  end: string;
  lengthDays: number;
  ongoing: boolean;
};

/** 来源：https://github.com/the-hideout/tarkov-dev/blob/main/src/data/wipe-details.json */
export const TARKOV_WIPE_STARTS: TarkovWipeStart[] = [
  { name: "0.4.0", start: "2017-10-27T00:00:00.000Z" },
  { name: "0.5.0", start: "2017-12-26T00:00:00.000Z" },
  { name: "0.8.0", start: "2018-04-19T00:00:00.000Z" },
  { name: "0.9.0", start: "2018-07-19T00:00:00.000Z" },
  { name: "0.10.5", start: "2018-11-08T00:00:00.000Z" },
  { name: "0.11.7", start: "2019-04-09T00:00:00.000Z" },
  { name: "0.12.0", start: "2019-10-27T00:00:00.000Z" },
  { name: "0.12.6", start: "2020-05-28T00:00:00.000Z" },
  { name: "0.12.9", start: "2020-12-24T00:00:00.000Z" },
  { name: "0.12.11", start: "2021-06-30T08:00:00.000Z" },
  { name: "0.12.12", start: "2021-12-12T09:00:00.000Z" },
  { name: "0.12.12.30", start: "2022-06-29T08:00:00.000Z" },
  { name: "0.13.0.0", start: "2022-12-28T06:35:00.000Z" },
  { name: "0.13.5", start: "2023-08-10T08:00:00.000Z" },
  { name: "0.14.0.0", start: "2023-12-27T15:00:00.000Z" },
  { name: "0.15.0.0", start: "2024-08-20T06:00:00.000Z" },
  { name: "0.16.0.0", start: "2024-12-26T07:00:00.000Z" },
  { name: "0.16.8.0", start: "2025-07-09T07:00:00.000Z" },
  { name: "1.0.0.0", start: "2025-11-15T09:00:00.000Z" },
];

const LAST_N_WIPES_FOR_AVERAGE = 6;

export function buildWipeRows(
  starts: TarkovWipeStart[] = TARKOV_WIPE_STARTS,
  now: Date = new Date(),
): TarkovWipeRow[] {
  const rows: TarkovWipeRow[] = starts.map((wipe, index) => {
    const start = new Date(wipe.start);
    const next = starts[index + 1];
    const ongoing = !next;
    const end = next ? new Date(next.start) : now;
    const lengthDays = Math.max(
      0,
      Math.floor((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)),
    );
    return {
      ...wipe,
      end: end.toISOString(),
      lengthDays,
      ongoing,
    };
  });
  return rows.slice().reverse();
}

export function averageWipeLength(
  starts: TarkovWipeStart[] = TARKOV_WIPE_STARTS,
  now: Date = new Date(),
): number {
  const ended = buildWipeRows(starts, now).filter((row) => !row.ongoing);
  const recent = ended.slice(0, LAST_N_WIPES_FOR_AVERAGE);
  if (!recent.length) return 0;
  const sum = recent.reduce((acc, row) => acc + row.lengthDays, 0);
  return Math.floor(sum / recent.length);
}
