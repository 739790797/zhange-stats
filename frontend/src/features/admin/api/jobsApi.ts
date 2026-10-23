import { client } from "@/shared/api/http";
import type { UserCheckinTasksPage } from "@/features/daily/api/types";
import type { components } from "@/shared/api/generated/schema";

export type JobTriggerResult = components["schemas"]["JobTriggerOut"];

export type JobTriggerRequest = components["schemas"]["JobTriggerRequest"];

export type JobRun = components["schemas"]["JobRunOut"];

export type JobRunsPage = components["schemas"]["JobRunsPageOut"];

export type JobRunEvents = components["schemas"]["JobRunEventsOut"];

export type JobRunLog = components["schemas"]["JobRunLogOut"];

export type ScheduledJobs = components["schemas"]["ScheduledJobsOut"];

export type JobMemberOption = components["schemas"]["JobMemberOptionOut"];

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

export async function fetchJobRuns(
  jobId: string,
  params?: { page?: number; page_size?: number; run_id?: number },
) {
  const { data } = await client.get<JobRunsPage>(
    `/settings/jobs/${encodeURIComponent(jobId)}/runs`,
    { params },
  );
  return data;
}

export async function fetchJobRunEvents(
  jobId: string,
  runId: number,
  afterId: number,
) {
  const { data } = await client.get<JobRunEvents>(
    `/settings/jobs/${encodeURIComponent(jobId)}/runs/${runId}/events`,
    { params: { after_id: afterId } },
  );
  return data;
}

export async function fetchScheduledJobs() {
  const { data } = await client.get<ScheduledJobs>("/settings/jobs");
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
