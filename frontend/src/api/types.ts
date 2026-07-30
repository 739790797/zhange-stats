export interface User {
  id: number;
  username: string;
  email?: string | null;
  display_name: string;
  role: string;
  is_admin: boolean;
  email_verified?: boolean;
  created_at: string;
}

export interface Member {
  id: number;
  nickname: string;
  avatar_url: string | null;
  user_id: number | null;
  joined_at: string;
}

export interface UserBrief {
  id: number;
  username: string;
  email?: string | null;
  display_name: string;
  role: string;
  is_admin: boolean;
  email_verified?: boolean;
  member_id: number | null;
}

export interface MemberProfile {
  member_id: number;
  nickname: string;
  avatar_url: string | null;
  steam_id: string | null;
  user_id: number | null;
  username: string | null;
  email?: string | null;
  display_name: string | null;
  joined_at: string;
}

export interface SteamCalendarCell {
  date: string;
  total_seconds: number;
  session_count: number;
}

export interface SteamCalendarData {
  granularity: string;
  range_start: string;
  range_end: string;
  cells: SteamCalendarCell[];
  total_seconds: number;
}

export interface SteamDaySession {
  id: number;
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  steam_app_id: string;
  game_name: string;
  started_at: string;
  last_seen_at: string;
  ended_at: string | null;
  duration_seconds: number;
  is_ongoing: boolean;
}

export interface SteamDayMemberSummary {
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  total_seconds: number;
  games: string[];
}

export interface SteamDayData {
  date: string;
  sessions: SteamDaySession[];
  by_member: SteamDayMemberSummary[];
  total_seconds: number;
  timeline?: SteamTimelineRow[];
  games_legend?: SteamGameLegendItem[];
}

export interface SteamTimelineSegment {
  status: "offline" | "online" | "playing" | string;
  steam_app_id?: string | null;
  game_name?: string | null;
  start_sec: number;
  end_sec: number;
}

export interface SteamTimelineRow {
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  segments: SteamTimelineSegment[];
}

export interface SteamGameLegendItem {
  steam_app_id: string;
  game_name: string;
}

export interface SteamNowItem {
  id: number;
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  steam_app_id: string;
  game_name: string;
  started_at: string;
  last_seen_at: string;
  duration_seconds: number;
}

export interface SteamSessionBrief {
  id: number;
  member_id: number;
  member_nickname: string;
  avatar_url?: string | null;
  steam_app_id: string;
  game_name: string;
  started_at: string;
  ended_at?: string | null;
  duration_seconds: number;
  is_ongoing?: boolean;
}

export interface SteamOverviewData {
  member_count: number;
  steam_bound_count: number;
  week_play_seconds: number;
  now_playing: SteamNowItem[];
  recent_sessions: SteamSessionBrief[];
}

export interface PlayTrendPoint {
  date: string;
  total_seconds: number;
  session_count: number;
}

export interface MemberPlayStats {
  member: Member & { steam_id?: string | null };
  week_play_seconds: number;
  month_play_seconds: number;
  session_count: number;
  trend: PlayTrendPoint[];
  recent_sessions: SteamSessionBrief[];
}

export interface SteamPollResult {
  status: string;
  message?: string | null;
  stats?: Record<string, number> | null;
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h} 小时 ${m} 分`;
  if (m > 0) return `${m} 分钟`;
  return `${s} 秒`;
}
