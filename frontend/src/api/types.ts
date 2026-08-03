export interface User {
  id: number;
  username: string;
  email?: string | null;
  display_name: string;
  role: string;
  is_admin: boolean;
  email_verified?: boolean;
  avatar_url?: string | null;
  steam_id?: string | null;
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
  steam_id?: string | null;
}

export interface MemberProfile {
  member_id: number;
  nickname: string;
  avatar_url: string | null;
  steam_id: string | null;
  steam_persona_name?: string | null;
  steam_friends_public?: boolean | null;
  steam_friends_synced_at?: string | null;
  skland_bound?: boolean;
  skland_auto_checkin?: boolean | null;
  taygedo_bound?: boolean;
  taygedo_auto_checkin?: boolean | null;
  taygedo_phone_mask?: string | null;
  qq_bound?: boolean;
  qq_nickname?: string | null;
  qq_avatar_url?: string | null;
  user_id: number | null;
  username: string | null;
  email?: string | null;
  display_name: string | null;
  joined_at: string;
}

export interface SklandRole {
  game_code: string;
  game_name: string;
  uid: string;
  role_name: string;
  channel_name: string;
}

export interface ArknightsChar {
  char_id: string;
  name: string;
  rarity: number;
  profession: string;
  profession_label: string;
  level: number;
  evolve_phase: number;
  potential_rank: number;
  favor_percent?: number | null;
  skin_id?: string | null;
  avatar_url?: string | null;
  obtain_ts?: number | null;
}

export interface ArknightsBox {
  uid: string;
  name: string;
  level: number;
  register_ts?: number | null;
  ap_current?: number | null;
  ap_max?: number | null;
  char_count: number;
  channel_name?: string | null;
  role_name?: string | null;
  chars: ArknightsChar[];
  roles: SklandRole[];
}

export interface SklandCheckinLog {
  id: number;
  game_code: string;
  game_name: string;
  role_uid: string;
  role_name?: string | null;
  channel_name?: string | null;
  status: string;
  status_label?: string | null;
  message?: string | null;
  awards_text?: string | null;
  checkin_date: string;
  checked_at: string;
}

export interface SklandStatus {
  bound: boolean;
  auto_checkin?: boolean | null;
  bound_at?: string | null;
  last_checkin_at?: string | null;
  last_checkin_date?: string | null;
  last_checkin_ok?: boolean | null;
  last_checkin_summary?: string | null;
  token_ok?: boolean | null;
  token_error?: string | null;
  roles: SklandRole[];
  today_results?: SklandCheckinResultItem[];
  today_logs?: SklandCheckinLog[];
}

export interface SklandCheckinResultItem {
  game_code: string;
  game_name: string;
  role_uid: string;
  role_name: string;
  channel_name: string;
  status: string;
  status_label?: string | null;
  message: string;
  awards_text?: string | null;
}

export interface SklandCheckinResponse {
  skipped: boolean;
  ok?: boolean | null;
  summary: string;
  results: SklandCheckinResultItem[];
}

export interface SklandQrStart {
  scan_id: string;
  scan_url: string;
  qr_image: string;
  expires_in: number;
}

export interface SklandQrPoll {
  status: "waiting" | "scanned" | "ok" | "expired" | "error" | string;
  message: string;
  bound?: boolean;
  auto_checkin?: boolean | null;
  roles?: SklandRole[];
}

export interface TaygedoRole {
  game_code: string;
  game_name: string;
  uid: string;
  role_name: string;
  channel_name: string;
}

export interface TaygedoCheckinLog {
  id: number;
  game_code: string;
  game_name: string;
  role_uid: string;
  role_name?: string | null;
  channel_name?: string | null;
  status: string;
  status_label?: string | null;
  message?: string | null;
  awards_text?: string | null;
  checkin_date: string;
  checked_at: string;
}

export interface TaygedoStatus {
  bound: boolean;
  auto_checkin?: boolean | null;
  phone_mask?: string | null;
  bound_at?: string | null;
  last_checkin_at?: string | null;
  last_checkin_date?: string | null;
  last_checkin_ok?: boolean | null;
  last_checkin_summary?: string | null;
  token_ok?: boolean | null;
  token_error?: string | null;
  roles: TaygedoRole[];
  today_results?: TaygedoCheckinResultItem[];
  today_logs?: TaygedoCheckinLog[];
}

export interface TaygedoCheckinResultItem {
  game_code: string;
  game_name: string;
  role_uid: string;
  role_name: string;
  channel_name: string;
  status: string;
  status_label?: string | null;
  message: string;
  awards_text?: string | null;
}

export interface TaygedoCheckinResponse {
  skipped: boolean;
  ok?: boolean | null;
  summary: string;
  results: TaygedoCheckinResultItem[];
}


export interface SteamVisibilityMeta {
  mode: string;
  self_member_id: number;
  steam_bound: boolean;
  friends_list_public: boolean | null;
  friends_synced_at: string | null;
  visible_friend_count: number;
  hint: string | null;
}

export interface SteamFriendItem {
  steam_id: string;
  persona_name: string;
  steam_persona_name?: string | null;
  friend_nickname?: string | null;
  avatar_url: string | null;
  profile_url?: string | null;
  status: "offline" | "online" | "playing" | string;
  game_name: string | null;
  steam_app_id?: string | null;
  friend_since: number | null;
  member_id: number | null;
  is_registered: boolean;
}

export interface SteamFriendsData {
  steam_bound: boolean;
  friends_list_public: boolean | null;
  friends_synced_at: string | null;
  friend_count: number;
  sync_ok: boolean;
  synced?: boolean;
  sync_interval_seconds?: number;
  hint: string | null;
  friends: SteamFriendItem[];
}

export interface SteamBindPreview {
  steam_id: string;
  persona_name: string | null;
  avatar_url: string | null;
  profile_url: string | null;
  is_public: boolean;
  privacy_label: string;
  message: string | null;
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
  members?: SteamCalendarMemberSeries[];
  visibility?: SteamVisibilityMeta | null;
}

export interface SteamCalendarMemberSeries {
  member_id: number;
  member_nickname: string;
  avatar_url?: string | null;
  total_seconds: number;
  cells: SteamCalendarCell[];
}

export interface SteamDaySession {
  id: number;
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  steam_app_id: string;
  game_name: string;
  icon_url?: string | null;
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
  range_start?: string;
  range_end?: string;
  span_seconds?: number;
  sessions: SteamDaySession[];
  by_member: SteamDayMemberSummary[];
  total_seconds: number;
  timeline?: SteamTimelineRow[];
  games_legend?: SteamGameLegendItem[];
  visibility?: SteamVisibilityMeta | null;
}

export interface SteamTimelineSegment {
  status: "offline" | "online" | "playing" | string;
  steam_app_id?: string | null;
  game_name?: string | null;
  icon_url?: string | null;
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
  icon_url?: string | null;
}

export interface SteamNowItem {
  id: number;
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  steam_app_id: string;
  game_name: string;
  icon_url?: string | null;
  started_at: string;
  last_seen_at: string;
  duration_seconds: number;
}

export interface SteamAppStoreCard {
  steam_app_id: string;
  name?: string | null;
  header_image?: string | null;
  capsule_image?: string | null;
  icon_url?: string | null;
  short_description?: string | null;
  is_free: boolean;
  currency?: string | null;
  initial_price?: number | null;
  final_price?: number | null;
  discount_percent: number;
  initial_formatted?: string | null;
  final_formatted?: string | null;
  store_url: string;
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
  visibility?: SteamVisibilityMeta | null;
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
