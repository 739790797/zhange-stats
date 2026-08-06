import { client } from "./http";
import type {
  TaygedoAttendanceCalendar,
  TaygedoCheckinResponse,
  TaygedoStatus,
} from "./types";

export async function fetchTaygedoStatus(includeRoles = true, force = false) {
  const { data } = await client.get<TaygedoStatus>("/taygedo/status", {
    params: {
      include_roles: includeRoles,
      ...(force ? { force: true } : {}),
    },
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

export async function updateTaygedoBind(payload: {
  auto_checkin?: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<TaygedoStatus>("/taygedo/bind", payload);
  return data;
}

export async function updateTaygedoRolePref(payload: {
  game_code: string;
  role_uid: string;
  enabled: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<TaygedoStatus>("/taygedo/role-prefs", payload);
  return data;
}

export async function triggerTaygedoCheckin() {
  const { data } = await client.post<TaygedoCheckinResponse>("/taygedo/checkin");
  return data;
}

export async function fetchTaygedoAttendanceCalendar(
  gameCode: string,
  roleUid?: string,
  force = false,
) {
  const { data } = await client.get<TaygedoAttendanceCalendar>(
    "/taygedo/attendance-calendar",
    {
      params: {
        game_code: gameCode,
        ...(roleUid ? { role_uid: roleUid } : {}),
        ...(force ? { force: true } : {}),
      },
      timeout: 60000,
    },
  );
  return data;
}
