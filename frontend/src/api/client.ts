import axios from "axios";
import { useAuthStore } from "@/stores/authStore";
import type {
  Game,
  LeaderboardData,
  MatchRecord,
  Member,
  MemberStats,
  OverviewData,
  User,
} from "./types";

const client = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);

export async function login(username: string, password: string) {
  const { data } = await client.post<{ access_token: string; token_type: string }>(
    "/auth/login",
    { username, password },
  );
  return data;
}

export async function fetchMe() {
  const { data } = await client.get<User>("/auth/me");
  return data;
}

export async function fetchMembers() {
  const { data } = await client.get<Member[]>("/members");
  return data;
}

export async function createMember(payload: {
  nickname: string;
  avatar_url?: string | null;
}) {
  const { data } = await client.post<Member>("/members", payload);
  return data;
}

export async function updateMember(
  id: number,
  payload: { nickname?: string; avatar_url?: string | null },
) {
  const { data } = await client.patch<Member>(`/members/${id}`, payload);
  return data;
}

export async function deleteMember(id: number) {
  await client.delete(`/members/${id}`);
}

export async function fetchGames() {
  const { data } = await client.get<Game[]>("/games");
  return data;
}

export async function createGame(payload: {
  name: string;
  platform?: string;
  icon_url?: string | null;
}) {
  const { data } = await client.post<Game>("/games", payload);
  return data;
}

export async function updateGame(
  id: number,
  payload: { name?: string; platform?: string; icon_url?: string | null },
) {
  const { data } = await client.patch<Game>(`/games/${id}`, payload);
  return data;
}

export async function deleteGame(id: number) {
  await client.delete(`/games/${id}`);
}

export async function fetchRecords(params?: {
  member_id?: number;
  game_id?: number;
  limit?: number;
}) {
  const { data } = await client.get<MatchRecord[]>("/records", { params });
  return data;
}

export async function createRecord(payload: {
  member_id: number;
  game_id: number;
  played_at: string;
  result: string;
  mode?: string | null;
  stats?: Record<string, unknown> | null;
  raw_text?: string | null;
  source?: string;
}) {
  const { data } = await client.post<MatchRecord>("/records", payload);
  return data;
}

export async function deleteRecord(id: number) {
  await client.delete(`/records/${id}`);
}

export async function fetchOverview() {
  const { data } = await client.get<OverviewData>("/stats/overview");
  return data;
}

export async function fetchLeaderboard(params?: {
  game_id?: number;
  range?: string;
}) {
  const { data } = await client.get<LeaderboardData>("/stats/leaderboard", {
    params,
  });
  return data;
}

export async function fetchMemberStats(memberId: number) {
  const { data } = await client.get<MemberStats>(`/stats/member/${memberId}`);
  return data;
}
