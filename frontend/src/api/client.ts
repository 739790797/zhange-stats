import axios from "axios";
import { useAuthStore } from "@/stores/authStore";
import type {
  Member,
  MemberPlayStats,
  MemberProfile,
  SteamCalendarData,
  SteamDayData,
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

export async function fetchSteamDay(date: string) {
  const { data } = await client.get<SteamDayData>("/steam/day", {
    params: { date },
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

export async function updateUserRole(userId: number, role: "user" | "admin") {
  const { data } = await client.patch<UserBrief>(`/users/${userId}/role`, {
    role,
  });
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

export async function fetchMyProfile() {
  const { data } = await client.get<MemberProfile>("/profile/me");
  return data;
}

export async function updateMyProfile(payload: {
  display_name?: string;
  steam_id?: string | null;
}) {
  const { data } = await client.patch<MemberProfile>("/profile/me", payload);
  return data;
}

export async function fetchMemberProfile(memberId: number) {
  const { data } = await client.get<MemberProfile>(
    `/members/${memberId}/profile`,
  );
  return data;
}
