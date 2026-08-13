const CALENDAR_GAME_CODES = new Set(["1289", "1256"]);

export function hasTaygedoAttendanceCalendar(gameCode?: string | null): boolean {
  return Boolean(gameCode && CALENDAR_GAME_CODES.has(gameCode));
}
