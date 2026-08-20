import { client } from "./http";
import type { components } from "./generated/schema";

export type EmailSettings = components["schemas"]["EmailSettingsOut"];
export type EmailSettingsUpdate = components["schemas"]["EmailSettingsUpdate"];
export type PlatformFeatureNode = components["schemas"]["PlatformFeatureNodeOut"];
export type PlatformFeaturesResponse = components["schemas"]["PlatformFeaturesOut"];
export type PlatformFeaturesUpdate = components["schemas"]["PlatformFeaturesUpdate"];
export type JobTriggerResult = components["schemas"]["JobTriggerOut"];
export type JobTriggerRequest = components["schemas"]["JobTriggerRequest"];
export type CheckinLogItem = components["schemas"]["CheckinLogItemOut"];
export type CheckinLogsPage = components["schemas"]["CheckinLogsPageOut"];
export type JobMemberOption = components["schemas"]["JobMemberOptionOut"];
export type UserCheckinTask = components["schemas"]["UserCheckinTaskOut"];
export type UserCheckinTasksPage = components["schemas"]["UserCheckinTasksPageOut"];
export type IntegrationsSettings = components["schemas"]["IntegrationsOut"];
export type IntegrationsUpdate = components["schemas"]["IntegrationsUpdate"];
export type IntegrationsStatus = components["schemas"]["IntegrationsStatusOut"];
export type AuthSettings = components["schemas"]["AuthSettingsOut"];
export type AuthSettingsUpdate = components["schemas"]["AuthSettingsUpdate"];
export type AuthAdminBrief = components["schemas"]["AuthAdminBrief"];
export type PelicanTestRequest = components["schemas"]["PelicanTestRequest"];
export type PelicanTestResponse = components["schemas"]["PelicanTestResponse"];
export type MinecraftRconTestRequest =
  components["schemas"]["MinecraftRconTestRequest"];
export type MinecraftRconTestResponse =
  components["schemas"]["MinecraftRconTestResponse"];

export async function fetchEmailSettings() {
  const { data } = await client.get<EmailSettings>("/settings/email");
  return data;
}

export async function fetchPlatformFeaturesEffective() {
  const { data } = await client.get<Record<string, boolean>>(
    "/settings/platform-features/effective",
  );
  return data;
}

export async function fetchPlatformFeaturesAdmin() {
  const { data } = await client.get<PlatformFeaturesResponse>(
    "/settings/platform-features",
  );
  return data;
}

export async function updatePlatformFeatures(payload: PlatformFeaturesUpdate) {
  const { data } = await client.put<PlatformFeaturesResponse>(
    "/settings/platform-features",
    payload,
  );
  return data;
}

export async function triggerScheduledJob(
  jobId: string,
  payload?: JobTriggerRequest | null,
) {
  const { data } = await client.post<JobTriggerResult>(
    `/settings/jobs/${encodeURIComponent(jobId)}/trigger`,
    payload || {},
  );
  return data;
}

export async function fetchJobCheckinLogs(params?: {
  platform?: string | null;
  member_id?: number | null;
  page?: number;
  page_size?: number;
}) {
  const { data } = await client.get<CheckinLogsPage>(
    "/settings/jobs/checkin-logs",
    { params },
  );
  return data;
}

export async function fetchJobFilterMembers() {
  const { data } = await client.get<JobMemberOption[]>("/settings/jobs/members");
  return data;
}

export async function fetchUserCheckinTasks(params?: {
  platform?: string | null;
  member_id?: number | null;
  page?: number;
  page_size?: number;
}) {
  const { data } = await client.get<UserCheckinTasksPage>(
    "/settings/jobs/user-tasks",
    { params },
  );
  return data;
}

export async function fetchMyDailyTasks(params?: {
  platform?: string | null;
  page?: number;
  page_size?: number;
}) {
  const { data } = await client.get<UserCheckinTasksPage>(
    "/profile/daily-tasks",
    { params },
  );
  return data;
}

export async function fetchMyDailyTaskLogs(params?: {
  platform?: string | null;
  page?: number;
  page_size?: number;
}) {
  const { data } = await client.get<CheckinLogsPage>(
    "/profile/daily-task-logs",
    { params },
  );
  return data;
}

export async function fetchIntegrationsSettings() {
  const { data } = await client.get<IntegrationsSettings>(
    "/settings/integrations",
  );
  return data;
}

export async function fetchIntegrationsStatus() {
  const { data } = await client.get<IntegrationsStatus>(
    "/settings/integrations/status",
  );
  return data;
}

export async function updateIntegrationsSettings(payload: IntegrationsUpdate) {
  const { data } = await client.put<IntegrationsSettings>(
    "/settings/integrations",
    payload,
  );
  return data;
}

export async function testPelicanConnection(payload: PelicanTestRequest) {
  const { data } = await client.post<PelicanTestResponse>(
    "/settings/integrations/pelican-test",
    payload,
    { timeout: 15_000 },
  );
  return data;
}

export async function testMinecraftRconConnection(
  payload: MinecraftRconTestRequest,
) {
  const { data } = await client.post<MinecraftRconTestResponse>(
    "/settings/integrations/minecraft-rcon-test",
    payload,
    { timeout: 10_000 },
  );
  return data;
}

export async function fetchAuthSettings(params?: { check_weak?: boolean }) {
  const { data } = await client.get<AuthSettings>("/settings/auth", {
    params: params?.check_weak ? { check_weak: true } : undefined,
  });
  return data;
}

export async function updateAuthSettings(payload: AuthSettingsUpdate) {
  const { data } = await client.put<AuthSettings>("/settings/auth", payload);
  return data;
}

export async function updateEmailSettings(payload: EmailSettingsUpdate) {
  const { data } = await client.put<EmailSettings>("/settings/email", payload);
  return data;
}

export async function testEmailSettings(to_email: string) {
  const { data } = await client.post<{ ok: boolean; message: string }>(
    "/settings/email/test",
    { to_email } satisfies components["schemas"]["EmailTestRequest"],
  );
  return data;
}
