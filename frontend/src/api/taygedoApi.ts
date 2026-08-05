import { client } from "./http";
import type {
  TaygedoCheckinLog,
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

export async function updateTaygedoBind(payload: {
  auto_checkin?: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<TaygedoStatus>("/taygedo/bind", payload);
  return data;
}

export async function triggerTaygedoCheckin() {
  const { data } = await client.post<TaygedoCheckinResponse>("/taygedo/checkin");
  return data;
}
