import { client } from "./http";
import type {
  ExiliumCheckinResponse,
  ExiliumExchangeResult,
  ExiliumExchangeShop,
  ExiliumSmsSendResponse,
  ExiliumStatus,
} from "./types";

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

export async function updateExiliumBind(payload: {
  auto_checkin?: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<ExiliumStatus>("/exilium/bind", payload);
  return data;
}

export async function updateExiliumRolePref(payload: {
  game_code: string;
  role_uid: string;
  enabled: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<ExiliumStatus>("/exilium/role-prefs", payload);
  return data;
}

export async function triggerExiliumCheckin() {
  const { data } = await client.post<ExiliumCheckinResponse>("/exilium/checkin");
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
