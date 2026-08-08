import { client } from "./http";
import type { components } from "./generated/schema";
import type {
  KujiequAttendanceCalendar,
  KujiequCheckinResponse,
  KujiequExchangeResult,
  KujiequExchangeShop,
  KujiequSmsSendResponse,
  KujiequStatus,
  WwBox,
} from "./types";

/** 签到 status：后端 force 默认 true；此处默认 true 且始终显式传参（勿省略）。 */
export async function fetchKujiequStatus(includeRoles = true, force = true) {
  const { data } = await client.get<KujiequStatus>("/kujiequ/status", {
    params: {
      include_roles: includeRoles,
      force,
    },
    timeout: 60000,
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

export async function updateKujiequRolePref(
  payload: components["schemas"]["CheckinRolePrefUpdate"],
) {
  const { data } = await client.patch<KujiequStatus>("/kujiequ/role-prefs", payload);
  return data;
}

export async function triggerKujiequCheckin(
  payload?: components["schemas"]["CheckinNowBody"],
) {
  const { data } = await client.post<KujiequCheckinResponse>(
    "/kujiequ/checkin",
    payload ?? {},
  );
  return data;
}

export async function fetchKujiequExchange(gameId?: number | null) {
  const { data } = await client.get<KujiequExchangeShop>("/kujiequ/exchange", {
    params: gameId != null ? { game_id: gameId } : undefined,
    timeout: 60000,
  });
  return data;
}

export async function exchangeKujiequItem(payload: {
  commodity_code: string;
  game_id: number;
  role_id?: string | null;
}) {
  const { data } = await client.post<KujiequExchangeResult>(
    "/kujiequ/exchange",
    {
      commodity_code: payload.commodity_code,
      game_id: payload.game_id,
      role_id: payload.role_id || null,
    },
    { timeout: 60000 },
  );
  return data;
}

export async function fetchKujiequAttendanceCalendar(
  gameCode: string,
  roleUid?: string | null,
  force = false,
) {
  const { data } = await client.get<KujiequAttendanceCalendar>(
    "/kujiequ/attendance-calendar",
    {
      params: {
        game_code: gameCode,
        ...(roleUid ? { role_uid: roleUid } : {}),
        force,
      },
    },
  );
  return data;
}

export async function fetchWwBox(uid?: string, force = false) {
  const { data } = await client.get<WwBox>("/kujiequ/ww/box", {
    params: {
      ...(uid ? { uid } : {}),
      force,
    },
  });
  return data;
}
