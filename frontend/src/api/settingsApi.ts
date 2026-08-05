import { client } from "./http";

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

export interface JobExecutor {
  id: string;
  name: string;
}

export interface ScheduledJob {
  id: string;
  name: string;
  description: string;
  kind?: string;
  platform?: string | null;
  executor_id?: string;
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
  platforms?: JobExecutor[];
  executors?: JobExecutor[];
  jobs: ScheduledJob[];
}

export interface PlatformFeatureNode {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  effective: boolean;
  parent_effective: boolean;
  reserved?: boolean;
  job_id?: string | null;
  schedule?: string | null;
  interval_minutes?: number | null;
  hour?: number | null;
  minute?: number | null;
  children?: PlatformFeatureNode[];
}

export interface PlatformFeaturesResponse {
  /** 库内原始开关（节点自身） */
  raw: Record<string, boolean>;
  /** 含祖先的生效开关 */
  effective: Record<string, boolean>;
  tree: PlatformFeatureNode[];
}

export interface JobRunRecord {
  id: number;
  job_key: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  message?: string | null;
  stats?: Record<string, unknown> | null;
}

export interface JobRunsPage {
  total: number;
  page: number;
  page_size: number;
  items: JobRunRecord[];
}

export interface JobTriggerResult {
  accepted: boolean;
  job_id: string;
  message: string;
}

export interface CheckinLogItem {
  id: number;
  platform: string;
  member_id: number;
  user_label?: string | null;
  game_code: string;
  game_name: string;
  role_uid: string;
  role_name?: string | null;
  status: string;
  message?: string | null;
  awards_text?: string | null;
  checkin_date: string;
  checked_at?: string | null;
}

export interface CheckinLogsPage {
  total: number;
  page: number;
  page_size: number;
  items: CheckinLogItem[];
}

export interface JobMemberOption {
  member_id: number;
  user_id?: number | null;
  label: string;
}

export interface UserCheckinTask {
  task_key: string;
  job_id: string;
  platform: string;
  platform_name: string;
  member_id: number;
  user_label: string;
  auto_checkin: boolean;
  checkin_hour: number;
  checkin_minute: number;
  last_checkin_at?: string | null;
  last_checkin_date?: string | null;
  last_checkin_ok?: boolean | null;
  last_checkin_summary?: string | null;
  bound_at?: string | null;
}

export interface UserCheckinTasksPage {
  total: number;
  page: number;
  page_size: number;
  items: UserCheckinTask[];
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

export async function fetchEmailSettings() {
  const { data } = await client.get<EmailSettings>("/settings/email");
  return data;
}

export async function fetchScheduledJobs() {
  const { data } = await client.get<ScheduledJobsResponse>("/settings/jobs");
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

export async function updatePlatformFeatures(payload: {
  features: Record<string, boolean>;
  jobs?: Record<
    string,
    {
      interval_minutes?: number;
      hour?: number;
      minute?: number;
    }
  >;
}) {
  const { data } = await client.put<PlatformFeaturesResponse>(
    "/settings/platform-features",
    payload,
  );
  return data;
}

export async function triggerScheduledJob(
  jobId: string,
  payload?: { member_id?: number | null },
) {
  const { data } = await client.post<JobTriggerResult>(
    `/settings/jobs/${encodeURIComponent(jobId)}/trigger`,
    payload || {},
  );
  return data;
}

export async function fetchJobRuns(
  jobId: string,
  params?: { page?: number; page_size?: number },
) {
  const { data } = await client.get<JobRunsPage>(
    `/settings/jobs/${encodeURIComponent(jobId)}/runs`,
    { params },
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
