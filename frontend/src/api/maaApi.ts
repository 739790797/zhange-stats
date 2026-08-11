import { client } from "./http";
import type { components } from "./generated/schema";

export type MaaSlot = components["schemas"]["MaaSlotOut"];
export type MaaAdminList = components["schemas"]["MaaAdminListOut"];
export type MaaResourceSummary = components["schemas"]["MaaResourceSummaryOut"];
export type MaaSlotAudit = components["schemas"]["MaaSlotAuditOut"];
export type MaaUserStatus = components["schemas"]["MaaUserStatusOut"];
export type MaaJob = components["schemas"]["MaaJobOut"];
export type MaaSlotLogs = components["schemas"]["MaaSlotLogsOut"];

export async function fetchMaaAdminList(includeDestroyed = false) {
  const { data } = await client.get<MaaAdminList>("/settings/maa", {
    params: { include_destroyed: includeDestroyed },
  });
  return data;
}

export async function createMaaSlot() {
  const { data } = await client.post<MaaSlot>("/settings/maa/slots");
  return data;
}

export async function startMaaSlot(slotId: number) {
  const { data } = await client.post<MaaSlot>(
    `/settings/maa/slots/${slotId}/start`,
  );
  return data;
}

export async function stopMaaSlot(slotId: number) {
  const { data } = await client.post<MaaSlot>(
    `/settings/maa/slots/${slotId}/stop`,
  );
  return data;
}

export async function destroyMaaSlot(slotId: number) {
  const { data } = await client.post<MaaSlot>(
    `/settings/maa/slots/${slotId}/destroy`,
  );
  return data;
}

export async function bindMaaSlot(slotId: number, memberId: number) {
  const { data } = await client.post<MaaSlot>(
    `/settings/maa/slots/${slotId}/bind`,
    { member_id: memberId },
  );
  return data;
}

export async function unbindMaaSlot(slotId: number) {
  const { data } = await client.post<MaaSlot>(
    `/settings/maa/slots/${slotId}/unbind`,
  );
  return data;
}

export async function fetchMaaSlotAudits(slotId: number, limit = 50) {
  const { data } = await client.get<MaaSlotAudit[]>(
    `/settings/maa/slots/${slotId}/audits`,
    { params: { limit } },
  );
  return data;
}

export async function triggerMaaReconcile() {
  const { data } = await client.post<{ ok: boolean; message: string }>(
    "/settings/maa/reconcile",
  );
  return data;
}

export async function fetchMaaSlotLogs(slotId: number) {
  const { data } = await client.get<MaaSlotLogs>(
    `/settings/maa/slots/${slotId}/logs`,
  );
  return data;
}

export async function fetchMaaMeLogs() {
  const { data } = await client.get<MaaSlotLogs>("/maa/me/logs");
  return data;
}

export function maaAdminScreenshotUrl(slotId: number) {
  return `/api/settings/maa/slots/${slotId}/screenshot?t=${Date.now()}`;
}

export async function fetchMaaMe() {
  const { data } = await client.get<MaaUserStatus>("/maa/me");
  return data;
}

export async function startMaaDaily() {
  const { data } = await client.post<MaaJob>("/maa/me/daily");
  return data;
}

export async function stopMaaDaily() {
  const { data } = await client.post<MaaJob>("/maa/me/stop");
  return data;
}

export function maaUserScreenshotUrl() {
  return `/api/maa/me/screenshot?t=${Date.now()}`;
}
