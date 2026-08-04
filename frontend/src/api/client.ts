import axios from "axios";
import { useAuthStore } from "@/stores/authStore";
import type {
  ArknightsBox,
  ArknightsBoxCompare,
  ArknightsCompareCandidate,
  EndfieldBox,
  Member,
  MemberPlayStats,
  MemberProfile,
  SklandCheckinLog,
  SklandCheckinResponse,
  SklandQrPoll,
  SklandQrStart,
  SklandStatus,
  TaygedoCheckinLog,
  TaygedoCheckinResponse,
  TaygedoStatus,
  ExiliumCheckinResponse,
  ExiliumExchangeResult,
  ExiliumExchangeShop,
  ExiliumSmsSendResponse,
  ExiliumStatus,
  KujiequCheckinResponse,
  KujiequSmsSendResponse,
  KujiequStatus,
  SteamBindPreview,
  SteamCalendarData,
  SteamDayData,
  SteamFriendsData,
  SteamNowItem,
  SteamOverviewData,
  SteamPollResult,
  SteamAppStoreCard,
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

export async function sendBindEmailCode(email: string) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery?: string;
  }>("/auth/send-bind-email-code", { email });
  return data;
}

export async function bindEmail(payload: {
  email: string;
  code: string;
  password?: string;
}) {
  const { data } = await client.post<{
    message: string;
    user: User;
  }>("/auth/bind-email", payload);
  return data;
}

export async function linkExistingAccount(payload: {
  email: string;
  password: string;
}) {
  const { data } = await client.post<{
    message: string;
    access_token: string;
    token_type: string;
    user: User;
  }>("/auth/link-existing-account", payload);
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
    params: {
      date,
      ...(end ? { end } : {}),
    },
  });
  return data;
}

export async function fetchSteamNow() {
  const { data } = await client.get<SteamNowItem[]>("/steam/now");
  return data;
}

export async function fetchSteamAppStore(appId: string) {
  const { data } = await client.get<SteamAppStoreCard>(`/steam/apps/${appId}`);
  return data;
}

export async function fetchSteamAppIcon(appId: string) {
  const { data } = await client.get<{ steam_app_id: string; icon_url: string | null }>(
    `/steam/apps/${encodeURIComponent(appId)}/icon`,
  );
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
  smtp_password?: string;
  smtp_password_set: boolean;
  display_name: string;
  smtp_host: string;
  smtp_port: number;
  encryption: "SSL" | "STARTTLS" | "NONE" | string;
  code_expire_minutes: number;
  configured: boolean;
}

export interface ScheduledJobLastRun {
  status?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  message?: string | null;
}

export interface ScheduledJob {
  id: string;
  name: string;
  description: string;
  kind?: string;
  registered: boolean;
  scheduler_running: boolean;
  trigger_type?: string | null;
  schedule?: string | null;
  next_run_at?: string | null;
  config_enabled?: boolean | null;
  interval_minutes?: number | null;
  hour?: number | null;
  minute?: number | null;
  last_run?: ScheduledJobLastRun | null;
}

export interface ScheduledJobsResponse {
  scheduler_running: boolean;
  timezone: string;
  steam_fake_poll?: boolean;
  steam_fake_available?: boolean;
  jobs: ScheduledJob[];
}

export interface IntegrationsSettings {
  steam_api_key?: string;
  steam_api_key_set: boolean;
  qq_app_id: string;
  qq_app_key?: string;
  qq_app_key_set: boolean;
  qq_configured: boolean;
  steam_configured: boolean;
  qq_callback_url?: string;
  napcat_base_url?: string;
  napcat_token?: string;
  napcat_token_set: boolean;
  napcat_configured: boolean;
}

export interface AuthSettings {
  access_token_expire_minutes: number;
  access_token_expire_days: number;
}

export async function fetchEmailSettings() {
  const { data } = await client.get<EmailSettings>("/settings/email");
  return data;
}

export async function fetchScheduledJobs() {
  const { data } = await client.get<ScheduledJobsResponse>("/settings/jobs");
  return data;
}

export async function updateScheduledJobs(payload: {
  jobs: Record<
    string,
    {
      enabled?: boolean;
      interval_minutes?: number;
      hour?: number;
      minute?: number;
    }
  >;
  steam_fake_poll?: boolean;
}) {
  const { data } = await client.put<ScheduledJobsResponse>(
    "/settings/jobs",
    payload,
  );
  return data;
}

export async function fetchIntegrationsSettings() {
  const { data } = await client.get<IntegrationsSettings>(
    "/settings/integrations",
  );
  return data;
}

export async function updateIntegrationsSettings(payload: {
  steam_api_key?: string | null;
  qq_app_id?: string | null;
  qq_app_key?: string | null;
  clear_steam_api_key?: boolean;
  clear_qq_app_key?: boolean;
  napcat_base_url?: string | null;
  napcat_token?: string | null;
  clear_napcat_token?: boolean;
}) {
  const { data } = await client.put<IntegrationsSettings>(
    "/settings/integrations",
    payload,
  );
  return data;
}

export async function fetchAuthSettings() {
  const { data } = await client.get<AuthSettings>("/settings/auth");
  return data;
}

export async function updateAuthSettings(payload: {
  access_token_expire_minutes: number;
}) {
  const { data } = await client.put<AuthSettings>("/settings/auth", payload);
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
  code_expire_minutes: number;
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
  check_error?: string | null;
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

export async function startQqOAuthBind(memberId?: number) {
  const { data } = await client.get<{ url: string }>("/profile/qq/oauth/start", {
    params: memberId != null ? { member_id: memberId } : undefined,
  });
  return data;
}

export async function startQqOAuthLogin() {
  const { data } = await client.get<{ url: string }>("/auth/qq/oauth/start");
  return data;
}

export async function unbindQq(memberId?: number) {
  const { data } = await client.delete<MemberProfile>("/profile/qq", {
    params: memberId != null ? { member_id: memberId } : undefined,
  });
  return data;
}

export async function updateMyProfile(payload: {
  display_name?: string;
  steam_id?: string | null;
  qq_number?: string | null;
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
    qq_number?: string | null;
  },
) {
  const { data } = await client.patch<MemberProfile>(
    `/members/${memberId}/profile`,
    payload,
  );
  return data;
}

export async function fetchSklandStatus(includeRoles = true, force = false) {
  const { data } = await client.get<SklandStatus>("/skland/status", {
    params: {
      include_roles: includeRoles,
      ...(force ? { force: true } : {}),
    },
  });
  return data;
}

export async function fetchArknightsBox(uid?: string) {
  const { data } = await client.get<ArknightsBox>("/skland/arknights/box", {
    params: uid ? { uid } : undefined,
    timeout: 60000,
  });
  return data;
}

export async function fetchEndfieldBox(uid?: string, force = false) {
  const { data } = await client.get<EndfieldBox>("/skland/endfield/box", {
    params: {
      ...(uid ? { uid } : {}),
      ...(force ? { force: true } : {}),
    },
    timeout: 60000,
  });
  return data;
}

export async function fetchArknightsCompareCandidates() {
  const { data } = await client.get<ArknightsCompareCandidate[]>(
    "/skland/arknights/box/compare-candidates",
  );
  return data;
}

export async function fetchArknightsBoxCompare(
  memberIds: number[],
  roleUids?: Record<number, string>,
) {
  const roleUidParam =
    roleUids &&
    Object.entries(roleUids)
      .filter(([, uid]) => Boolean(uid))
      .map(([memberId, uid]) => `${memberId}:${uid}`)
      .join(",");
  const { data } = await client.get<ArknightsBoxCompare>(
    "/skland/arknights/box/compare",
    {
      params: {
        member_ids: memberIds.join(","),
        ...(roleUidParam ? { role_uids: roleUidParam } : {}),
      },
      timeout: 120000,
    },
  );
  return data;
}

export async function fetchSklandLogs(limit = 30) {
  const { data } = await client.get<SklandCheckinLog[]>("/skland/logs", {
    params: { limit },
  });
  return data;
}

export async function bindSkland(token: string) {
  const { data } = await client.post<SklandStatus>("/skland/bind", { token });
  return data;
}

export async function bindSklandPassword(phone: string, password: string) {
  const { data } = await client.post<SklandStatus>("/skland/bind/password", {
    phone,
    password,
  });
  return data;
}

export async function sendSklandSms(phone: string) {
  const { data } = await client.post<{ message: string }>(
    "/skland/bind/sms/send",
    { phone },
  );
  return data;
}

export async function bindSklandSms(phone: string, code: string) {
  const { data } = await client.post<SklandStatus>("/skland/bind/sms", {
    phone,
    code,
  });
  return data;
}

export async function unbindSkland() {
  const { data } = await client.delete<SklandStatus>("/skland/bind");
  return data;
}

export async function updateSklandBind(payload: { auto_checkin: boolean }) {
  const { data } = await client.patch<SklandStatus>("/skland/bind", payload);
  return data;
}

export async function triggerSklandCheckin() {
  const { data } = await client.post<SklandCheckinResponse>("/skland/checkin");
  return data;
}

export async function startSklandQrBind() {
  const { data } = await client.post<SklandQrStart>("/skland/qr/start");
  return data;
}

export async function pollSklandQrBind(scanId: string) {
  const { data } = await client.get<SklandQrPoll>("/skland/qr/poll", {
    params: { scan_id: scanId },
  });
  return data;
}

export async function fetchTaygedoStatus(includeRoles = true, force = false) {
  const { data } = await client.get<TaygedoStatus>("/taygedo/status", {
    params: {
      include_roles: includeRoles,
      ...(force ? { force: true } : {}),
    },
  });
  return data;
}

export async function fetchTaygedoLogs(limit = 30) {
  const { data } = await client.get<TaygedoCheckinLog[]>("/taygedo/logs", {
    params: { limit },
  });
  return data;
}

export async function bindTaygedoPassword(phone: string, password: string) {
  const { data } = await client.post<TaygedoStatus>("/taygedo/bind/password", {
    phone,
    password,
  });
  return data;
}

export async function sendTaygedoSms(phone: string, deviceId?: string | null) {
  const { data } = await client.post<{ device_id: string; message: string }>(
    "/taygedo/bind/sms/send",
    { phone, device_id: deviceId || undefined },
  );
  return data;
}

export async function bindTaygedoSms(
  phone: string,
  captcha: string,
  deviceId: string,
) {
  const { data } = await client.post<TaygedoStatus>("/taygedo/bind/sms", {
    phone,
    captcha,
    device_id: deviceId,
  });
  return data;
}

export async function unbindTaygedo() {
  const { data } = await client.delete<TaygedoStatus>("/taygedo/bind");
  return data;
}

export async function updateTaygedoBind(payload: { auto_checkin: boolean }) {
  const { data } = await client.patch<TaygedoStatus>("/taygedo/bind", payload);
  return data;
}

export async function triggerTaygedoCheckin() {
  const { data } = await client.post<TaygedoCheckinResponse>("/taygedo/checkin");
  return data;
}

export async function fetchExiliumStatus(includeRoles = true, force = false) {
  const { data } = await client.get<ExiliumStatus>("/exilium/status", {
    params: {
      include_roles: includeRoles,
      ...(force ? { force: true } : {}),
    },
  });
  return data;
}

export async function bindExiliumPassword(account: string, password: string) {
  const { data } = await client.post<ExiliumStatus>("/exilium/bind/password", {
    account,
    password,
  });
  return data;
}

export async function sendExiliumSms(phone: string, graphCode?: string | null) {
  const { data } = await client.post<ExiliumSmsSendResponse>(
    "/exilium/bind/sms/send",
    { phone, graph_code: graphCode || null },
  );
  return data;
}

export async function bindExiliumSms(phone: string, captcha: string) {
  const { data } = await client.post<ExiliumStatus>("/exilium/bind/sms", {
    phone,
    captcha,
  });
  return data;
}

export async function unbindExilium() {
  const { data } = await client.delete<ExiliumStatus>("/exilium/bind");
  return data;
}

export async function updateExiliumBind(payload: { auto_checkin: boolean }) {
  const { data } = await client.patch<ExiliumStatus>("/exilium/bind", payload);
  return data;
}

export async function triggerExiliumCheckin() {
  const { data } = await client.post<ExiliumCheckinResponse>("/exilium/checkin");
  return data;
}

export async function fetchKujiequStatus(includeRoles = true, force = false) {
  const { data } = await client.get<KujiequStatus>("/kujiequ/status", {
    params: {
      include_roles: includeRoles,
      ...(force ? { force: true } : {}),
    },
  });
  return data;
}

export async function sendKujiequSms(
  phone: string,
  geeTestData?: string | null,
) {
  const { data } = await client.post<KujiequSmsSendResponse>(
    "/kujiequ/bind/sms/send",
    { phone, gee_test_data: geeTestData || null },
  );
  return data;
}

export async function bindKujiequSms(phone: string, captcha: string) {
  const { data } = await client.post<KujiequStatus>("/kujiequ/bind/sms", {
    phone,
    captcha,
  });
  return data;
}

export async function unbindKujiequ() {
  const { data } = await client.delete<KujiequStatus>("/kujiequ/bind");
  return data;
}

export async function updateKujiequBind(payload: { auto_checkin: boolean }) {
  const { data } = await client.patch<KujiequStatus>("/kujiequ/bind", payload);
  return data;
}

export async function triggerKujiequCheckin() {
  const { data } = await client.post<KujiequCheckinResponse>("/kujiequ/checkin");
  return data;
}

export async function fetchExiliumExchange() {
  const { data } = await client.get<ExiliumExchangeShop>("/exilium/exchange", {
    timeout: 60000,
  });
  return data;
}

export async function exchangeExiliumItem(exchangeId: number) {
  const { data } = await client.post<ExiliumExchangeResult>(
    "/exilium/exchange",
    { exchange_id: exchangeId },
    { timeout: 60000 },
  );
  return data;
}

export interface NapCatGroup {
  group_id: string;
  group_name: string;
  member_count?: number | null;
  max_member_count?: number | null;
}

export interface NapCatSiteMember {
  id: number;
  nickname: string;
  user_id?: number | null;
  qq_number?: string | null;
}

export interface NapCatGroupMember {
  user_id: string;
  nickname: string;
  card: string;
  role: string;
  title: string;
  site_member: NapCatSiteMember | null;
}

export interface NapCatGroupsResponse {
  configured: boolean;
  groups: NapCatGroup[];
}

export interface NapCatGroupMembersResponse {
  group_id: string;
  members: NapCatGroupMember[];
  site_bound_count: number;
}

export async function fetchNapCatGroups(force = false) {
  const { data } = await client.get<NapCatGroupsResponse>("/napcat/groups", {
    params: force ? { force: true } : undefined,
    timeout: 60000,
  });
  return data;
}

export async function fetchNapCatGroupMembers(groupId: string, force = false) {
  const { data } = await client.get<NapCatGroupMembersResponse>(
    `/napcat/groups/${encodeURIComponent(groupId)}/members`,
    {
      params: force ? { force: true } : undefined,
      timeout: 60000,
    },
  );
  return data;
}
