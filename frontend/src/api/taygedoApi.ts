import { client } from "./http";
import type { components } from "./generated/schema";
import type {
  ExastrisBox,
  TaygedoAttendanceCalendar,
  TaygedoCheckinResponse,
  TaygedoExchangeResult,
  TaygedoExchangeShop,
  TaygedoStatus,
} from "./types";

/** 签到 status：后端 force 默认 true；此处默认 true 且始终显式传参（勿省略）。 */
export async function fetchTaygedoStatus(includeRoles = true, force = true) {
  const { data } = await client.get<TaygedoStatus>("/taygedo/status", {
    params: {
      include_roles: includeRoles,
      force,
    },
    // force 回源社区 + 多游戏角色，默认 15s 易被网关/客户端掐断
    timeout: 60000,
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

export async function updateTaygedoRolePref(
  payload: components["schemas"]["CheckinRolePrefUpdate"],
) {
  const { data } = await client.patch<TaygedoStatus>("/taygedo/role-prefs", payload);
  return data;
}

export async function triggerTaygedoCheckin(
  payload?: components["schemas"]["CheckinNowBody"],
) {
  const { data } = await client.post<TaygedoCheckinResponse>(
    "/taygedo/checkin",
    payload ?? {},
  );
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
        force,
      },
      timeout: 60000,
    },
  );
  return data;
}

export async function fetchExastrisBox(uid?: string, force = false) {
  const { data } = await client.get<ExastrisBox>("/taygedo/exastris/box", {
    params: {
      ...(uid ? { uid } : {}),
      force,
    },
    timeout: 60000,
  });
  return data;
}

export async function fetchTaygedoExchange(tab?: string | null) {
  const { data } = await client.get<TaygedoExchangeShop>("/taygedo/exchange", {
    params: tab ? { tab } : undefined,
    timeout: 60000,
  });
  return data;
}

export async function exchangeTaygedoItem(payload: {
  goods_id: string;
  game_id: string;
  role_id: string;
}) {
  const { data } = await client.post<TaygedoExchangeResult>(
    "/taygedo/exchange",
    {
      goods_id: payload.goods_id,
      game_id: payload.game_id,
      role_id: payload.role_id,
    },
    { timeout: 60000 },
  );
  return data;
}
