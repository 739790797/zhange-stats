import axios from "axios";
import { useAuthStore } from "@/stores/authStore";
import type {
  Member,
  MemberPlayStats,
  MemberProfile,
  SteamBindPreview,
  SteamCalendarData,
  SteamDayData,
  SteamFriendsData,
  SteamNowItem,
  SteamOverviewData,
  SteamPollResult,
  User,
  UserBrief,
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

export async function register(payload: {
  email: string;
  password: string;
  code: string;
}) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery?: string;
    access_token?: string;
    token_type?: string;
  }>("/auth/register", payload);
  return data;
}

export async function sendRegisterCode(email: string) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery?: string;
  }>("/auth/send-register-code", { email });
  return data;
}

export async function verifyEmail(email: string, code: string) {
  const { data } = await client.post<{ message: string }>("/auth/verify-email", {
    email,
    code,
  });
  return data;
}

export async function resendCode(email: string) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery: string;
  }>("/auth/resend-code", { email });
  return data;
}

export async function fetchMe() {
  const { data } = await client.get<User>("/auth/me");
  return data;
}

export async function fetchSteamFriends(force = false) {
  const { data } = await client.get<SteamFriendsData>("/steam/friends", {
    params: { force },
    timeout: 60000,
  });
  return data;
}

export async function fetchMembers() {
  const { data } = await client.get<Member[]>("/members");
  return data;
}

export async function fetchSteamOverview() {
  const { data } = await client.get<SteamOverviewData>("/steam/overview");
  return data;
}

export async function fetchMemberPlayStats(memberId: number) {
  const { data } = await client.get<MemberPlayStats>(
    `/steam/members/${memberId}`,
  );
  return data;
}

export async function fetchSteamCalendar(params: {
  granularity: string;
  date: string;
}) {
  const { data } = await client.get<SteamCalendarData>("/steam/calendar", {
    params,
  });
  return data;
}

export async function fetchSteamDay(date: string, end?: string) {
  const { data } = await client.get<SteamDayData>("/steam/day", {
    params: end ? { date, end } : { date },
  });
  return data;
}

export async function fetchSteamNow() {
  const { data } = await client.get<SteamNowItem[]>("/steam/now");
  return data;
}

export async function triggerSteamPoll() {
  const { data } = await client.post<SteamPollResult>("/steam/poll");
  return data;
}

export async function fetchUsers() {
  const { data } = await client.get<UserBrief[]>("/users");
  return data;
}

export async function createUser(payload: {
  email: string;
  display_name: string;
  password: string;
  steam_id?: string | null;
}) {
  const { data } = await client.post<UserBrief>("/users", payload);
  return data;
}

export async function updateUser(
  userId: number,
  payload: {
    email?: string;
    display_name?: string;
    password?: string;
    steam_id?: string | null;
  },
) {
  const { data } = await client.patch<UserBrief>(`/users/${userId}`, payload);
  return data;
}

export async function deleteUser(userId: number) {
  await client.delete(`/users/${userId}`);
}

export interface EmailSettings {
  enabled: boolean;
  smtp_user: string;
  smtp_from: string;
  smtp_password_set: boolean;
  display_name: string;
  smtp_host: string;
  smtp_port: number;
  encryption: "SSL" | "STARTTLS" | "NONE" | string;
  configured: boolean;
}

export async function fetchEmailSettings() {
  const { data } = await client.get<EmailSettings>("/settings/email");
  return data;
}

export async function updateEmailSettings(payload: {
  enabled: boolean;
  smtp_user: string;
  smtp_from: string;
  smtp_password?: string | null;
  display_name: string;
  smtp_host: string;
  smtp_port: number;
  encryption: string;
}) {
  const { data } = await client.put<EmailSettings>("/settings/email", payload);
  return data;
}

export async function testEmailSettings(to_email: string) {
  const { data } = await client.post<{ ok: boolean; message: string }>(
    "/settings/email/test",
    { to_email },
  );
  return data;
}

export interface UpdateCheckResult {
  current_version: string;
  latest_version: string | null;
  has_update: boolean;
  update_enabled: boolean;
  image: string;
  repo: string;
}

export interface UpdateStatusResult {
  state: string;
  message: string;
  current_version: string;
  target_version: string;
  started_at: number | null;
  finished_at: number | null;
  error: string | null;
  update_enabled: boolean;
}

export async function checkUpdate() {
  const { data } = await client.get<UpdateCheckResult>("/update/check");
  return data;
}

export async function fetchUpdateStatus() {
  const { data } = await client.get<UpdateStatusResult>("/update/status");
  return data;
}

export async function triggerUpdate() {
  const { data } = await client.post<UpdateStatusResult>("/update/do");
  return data;
}

export async function fetchMyProfile() {
  const { data } = await client.get<MemberProfile>("/profile/me");
  return data;
}

export async function previewSteamBind(steam_input: string) {
  const { data } = await client.post<SteamBindPreview>("/profile/steam/preview", {
    steam_input,
  });
  return data;
}

export async function startSteamOpenIdBind(memberId?: number) {
  const { data } = await client.get<{ url: string }>("/profile/steam/openid/start", {
    params: memberId != null ? { member_id: memberId } : undefined,
  });
  return data;
}

export async function updateMyProfile(payload: {
  display_name?: string;
  steam_id?: string | null;
}) {
  const { data } = await client.patch<MemberProfile>("/profile/me", payload);
  return data;
}

export async function uploadMyAvatar(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<MemberProfile>("/profile/me/avatar", form, {
    timeout: 30000,
  });
  return data;
}

export async function uploadMemberAvatar(memberId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<MemberProfile>(
    `/members/${memberId}/avatar`,
    form,
    { timeout: 30000 },
  );
  return data;
}

export async function deleteMyAvatar() {
  const { data } = await client.delete<MemberProfile>("/profile/me/avatar");
  return data;
}

export async function fetchMemberProfile(memberId: number) {
  const { data } = await client.get<MemberProfile>(
    `/members/${memberId}/profile`,
  );
  return data;
}

export async function updateMemberProfile(
  memberId: number,
  payload: {
    display_name?: string;
    steam_id?: string | null;
  },
) {
  const { data } = await client.patch<MemberProfile>(
    `/members/${memberId}/profile`,
    payload,
  );
  return data;
}
