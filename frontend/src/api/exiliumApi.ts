import { client } from "./http";
import type { components } from "./generated/schema";
import type {
  ExiliumCheckinResponse,
  ExiliumExchangeResult,
  ExiliumExchangeShop,
  ExiliumSmsSendResponse,
  ExiliumStatus,
} from "./types";

/** 签到 status：后端 force 默认 true；此处默认 true 且始终显式传参（勿省略）。 */
export async function fetchExiliumStatus(includeRoles = true, force = true) {
  const { data } = await client.get<ExiliumStatus>("/exilium/status", {
    params: {
      include_roles: includeRoles,
      force,
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

export async function updateExiliumRolePref(
  payload: components["schemas"]["CheckinRolePrefUpdate"],
) {
  const { data } = await client.patch<ExiliumStatus>("/exilium/role-prefs", payload);
  return data;
}

export async function triggerExiliumCheckin(
  payload?: components["schemas"]["CheckinNowBody"],
) {
  const { data } = await client.post<ExiliumCheckinResponse>(
    "/exilium/checkin",
    payload ?? {},
  );
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
