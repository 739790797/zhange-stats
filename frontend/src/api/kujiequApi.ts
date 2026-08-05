import { client } from "./http";
import type {
  KujiequCheckinResponse,
  KujiequSmsSendResponse,
  KujiequStatus,
} from "./types";

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

export async function updateKujiequBind(payload: {
  auto_checkin?: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<KujiequStatus>("/kujiequ/bind", payload);
  return data;
}

export async function triggerKujiequCheckin() {
  const { data } = await client.post<KujiequCheckinResponse>("/kujiequ/checkin");
  return data;
}
