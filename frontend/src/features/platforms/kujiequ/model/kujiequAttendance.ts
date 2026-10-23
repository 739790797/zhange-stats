const CALENDAR_GAME_CODES = new Set(["game_3", "game_2"]);

export function hasKujiequAttendanceCalendar(gameCode?: string | null): boolean {
  return Boolean(gameCode && CALENDAR_GAME_CODES.has(gameCode));
}
