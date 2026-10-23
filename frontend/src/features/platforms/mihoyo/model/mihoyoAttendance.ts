const CALENDAR_GAME_CODES = new Set([
  "genshin",
  "bh3",
  "starrail",
  "zzz",
  "bh2",
]);

export function hasMihoyoAttendanceCalendar(gameCode?: string | null): boolean {
  return Boolean(gameCode && CALENDAR_GAME_CODES.has(gameCode));
}
