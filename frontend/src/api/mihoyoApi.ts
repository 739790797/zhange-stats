import { client } from "./http";
import type { components } from "./generated/schema";
import type {
  MihoyoBindPasswordResponse,
  MihoyoBindSmsSendResponse,
  MihoyoCheckinResponse,
  MihoyoExchangeResult,
  MihoyoExchangeShop,
  MihoyoQrPoll,
  MihoyoQrStart,
  MihoyoStatus,
} from "./types";

/** 签到 status：后端 force 默认 true；此处默认 true 且始终显式传参（勿省略）。 */
export async function fetchMihoyoStatus(includeRoles = true, force = true) {
  const { data } = await client.get<MihoyoStatus>("/mihoyo/status", {
    params: {
      include_roles: includeRoles,
      force,
    },
    timeout: 90000,
  });
  return data;
}

export async function sendMihoyoSms(
  phone: string,
  geetest?: string | null,
  mmtKey?: string | null,
) {
  const { data } = await client.post<MihoyoBindSmsSendResponse>(
    "/mihoyo/bind/sms/send",
    {
      phone,
      geetest: geetest || null,
      mmt_key: mmtKey || null,
    },
  );
  return data;
}

export async function bindMihoyoSms(phone: string, captcha: string) {
  const { data } = await client.post<MihoyoStatus>("/mihoyo/bind/sms", {
    phone,
    captcha,
  });
  return data;
}

export async function bindMihoyoPassword(
  account: string,
  password: string,
  geetest?: string | null,
  mmtKey?: string | null,
) {
  const { data } = await client.post<MihoyoBindPasswordResponse>(
    "/mihoyo/bind/password",
    {
      account,
      password,
      geetest: geetest || null,
      mmt_key: mmtKey || null,
    },
  );
  return data;
}

export async function startMihoyoQrBind() {
  const { data } = await client.post<MihoyoQrStart>("/mihoyo/qr/start");
  return data;
}

export async function pollMihoyoQrBind(scanId: string) {
  const { data } = await client.post<MihoyoQrPoll>("/mihoyo/qr/poll", {
    scan_id: scanId,
  });
  return data;
}

export async function unbindMihoyo() {
  const { data } = await client.delete<MihoyoStatus>("/mihoyo/bind");
  return data;
}

export async function updateMihoyoBind(payload: {
  auto_checkin?: boolean;
  checkin_hour?: number;
  checkin_minute?: number;
}) {
  const { data } = await client.patch<MihoyoStatus>("/mihoyo/bind", payload);
  return data;
}

export async function updateMihoyoRolePref(
  payload: components["schemas"]["CheckinRolePrefUpdate"],
) {
  const { data } = await client.patch<MihoyoStatus>("/mihoyo/role-prefs", payload);
  return data;
}

export async function triggerMihoyoCheckin(
  payload?: components["schemas"]["CheckinNowBody"],
) {
  const { data } = await client.post<MihoyoCheckinResponse>(
    "/mihoyo/checkin",
    payload ?? {},
    { timeout: 120000 },
  );
  return data;
}

export async function fetchMihoyoExchange() {
  const { data } = await client.get<MihoyoExchangeShop>("/mihoyo/exchange", {
    timeout: 60000,
  });
  return data;
}

export async function exchangeMihoyoItem(payload: {
  goods_id: string;
  game_biz?: string;
  region?: string;
  role_uid?: string;
}) {
  const { data } = await client.post<MihoyoExchangeResult>(
    "/mihoyo/exchange",
    payload,
    { timeout: 60000 },
  );
  return data;
}
