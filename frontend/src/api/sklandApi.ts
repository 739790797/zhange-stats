import { client } from "./http";
import type {
  ArknightsBoxCompare,
  ArknightsCompareCandidate,
  EndfieldBox,
  SklandCheckinResponse,
  SklandQrPoll,
  SklandQrStart,
  SklandStatus,
} from "./types";

export async function fetchSklandStatus(includeRoles = true, force = false) {
  const { data } = await client.get<SklandStatus>("/skland/status", {
    params: {
      include_roles: includeRoles,
      ...(force ? { force: true } : {}),
    },
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

export async function updateSklandBind(payload: {
  auto_checkin?: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
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
