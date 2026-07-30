export interface User {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
  created_at: string;
}

export interface Member {
  id: number;
  nickname: string;
  avatar_url: string | null;
  user_id: number | null;
  joined_at: string;
}

export interface Game {
  id: number;
  name: string;
  platform: string;
  icon_url: string | null;
  created_at: string;
}

export interface MatchRecord {
  id: number;
  member_id: number;
  game_id: number;
  played_at: string;
  result: string;
  mode: string | null;
  stats: Record<string, unknown> | null;
  raw_text: string | null;
  source: string;
  created_at: string;
  member_nickname?: string | null;
  game_name?: string | null;
}

export interface OverviewData {
  recent_records: {
    id: number;
    member_nickname: string;
    game_name: string;
    result: string;
    played_at: string;
    mode?: string | null;
  }[];
  week_star: {
    member_id: number;
    member_nickname: string;
    wins: number;
    total: number;
    win_rate: number;
  } | null;
  win_rate: {
    total_matches: number;
    wins: number;
    losses: number;
    draws: number;
    win_rate: number;
  };
}

export interface LeaderboardItem {
  rank: number;
  member_id: number;
  member_nickname: string;
  avatar_url: string | null;
  wins: number;
  losses: number;
  draws: number;
  total: number;
  win_rate: number;
}

export interface LeaderboardData {
  items: LeaderboardItem[];
  game_id: number | null;
  range: string;
}

export interface MemberStats {
  member: Member;
  total_matches: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  recent_records: OverviewData["recent_records"];
  trend: { date: string; wins: number; total: number; win_rate: number }[];
}
