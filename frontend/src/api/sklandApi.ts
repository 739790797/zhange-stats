import { client } from "./http";
import type { components } from "./generated/schema";
import type {
  ArknightsAttendanceCalendar,
  ArknightsBoxCompare,
  ArknightsCompareCandidate,
  ArknightsRogue,
  EndfieldBox,
  EndfieldAttendanceCalendar,
  GameScheduleCalendar,
  SklandCheckinResponse,
  SklandQrPoll,
  SklandQrStart,
  SklandStatus,
} from "./types";

/** 签到 status：后端 force 默认 true；此处默认 true 且始终显式传参（勿省略）。 */
export async function fetchSklandStatus(includeRoles = true, force = true) {
  const { data } = await client.get<SklandStatus>("/skland/status", {
    params: {
      include_roles: includeRoles,
      force,
    },
    timeout: 60000,
  });
  return data;
}

export async function fetchEndfieldBox(uid?: string, force = false) {
  const { data } = await client.get<EndfieldBox>("/skland/endfield/box", {
    params: {
      ...(uid ? { uid } : {}),
      force,
    },
    timeout: 60000,
  });
  return data;
}

export async function fetchEndfieldAttendanceCalendar(
  uid?: string,
  force = false,
) {
  const { data } = await client.get<EndfieldAttendanceCalendar>(
    "/skland/endfield/attendance-calendar",
    {
      params: {
        ...(uid ? { uid } : {}),
        force,
      },
      timeout: 60000,
    },
  );
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

export async function fetchArknightsAttendanceCalendar(
  uid?: string,
  force = false,
) {
  const { data } = await client.get<ArknightsAttendanceCalendar>(
    "/skland/arknights/attendance-calendar",
    {
      params: {
        ...(uid ? { uid } : {}),
        force,
      },
      timeout: 60000,
    },
  );
  return data;
}

/** 活动日历（game-schedule 代理）；force 回源。 */
export async function fetchSklandGameEvents(
  game: "arknights" | "endfield",
  force = false,
) {
  const { data } = await client.get<GameScheduleCalendar>(
    "/skland/game-events",
    {
      params: { game, force },
      timeout: 60000,
    },
  );
  return data;
}

export async function fetchArknightsRogue(
  uid?: string,
  topicId?: string,
  force = false,
) {
  const { data } = await client.get<ArknightsRogue>(
    "/skland/arknights/rogue",
    {
      params: {
        ...(uid ? { uid } : {}),
        ...(topicId ? { topic_id: topicId } : {}),
        force,
      },
      timeout: 60000,
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

export async function updateSklandRolePref(
  payload: components["schemas"]["CheckinRolePrefUpdate"],
) {
  const { data } = await client.patch<SklandStatus>("/skland/role-prefs", payload);
  return data;
}

export async function triggerSklandCheckin(
  payload?: components["schemas"]["CheckinNowBody"],
) {
  const { data } = await client.post<SklandCheckinResponse>(
    "/skland/checkin",
    payload ?? {},
  );
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
