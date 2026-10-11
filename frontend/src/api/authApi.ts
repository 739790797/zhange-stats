import { client } from "./http";
import type { SessionResponse, User } from "./types";
import type { components } from "./generated/schema";

type RegisterResponse = components["schemas"]["RegisterResponse"];
type BindEmailResponse = components["schemas"]["BindEmailResponse"];
type LinkExistingAccountResponse =
  components["schemas"]["LinkExistingAccountResponse"];
type ResetPasswordResponse = components["schemas"]["ResetPasswordResponse"];

export async function login(username: string, password: string) {
  const { data } = await client.post<SessionResponse>("/auth/login", {
    username,
    password,
  });
  return data;
}

export async function register(payload: {
  email: string;
  password: string;
  code: string;
}) {
  const { data } = await client.post<RegisterResponse>("/auth/register", payload);
  return data;
}

export async function sendRegisterCode(email: string) {
  const { data } = await client.post<RegisterResponse>(
    "/auth/send-register-code",
    { email },
  );
  return data;
}

export async function sendResetPasswordCode(email: string) {
  const { data } = await client.post<ResetPasswordResponse>(
    "/auth/send-reset-password-code",
    { email },
  );
  return data;
}

export async function resetPassword(payload: {
  email: string;
  code: string;
  new_password: string;
}) {
  const { data } = await client.post<ResetPasswordResponse>(
    "/auth/reset-password",
    payload,
  );
  return data;
}

export async function sendBindEmailCode(email: string) {
  const { data } = await client.post<RegisterResponse>(
    "/auth/send-bind-email-code",
    { email },
  );
  return data;
}

export async function bindEmail(payload: {
  email: string;
  code: string;
  password?: string;
}) {
  const { data } = await client.post<BindEmailResponse>(
    "/auth/bind-email",
    payload,
  );
  return data;
}

export async function linkExistingAccount(payload: {
  email: string;
  password: string;
}) {
  const { data } = await client.post<LinkExistingAccountResponse>(
    "/auth/link-existing-account",
    payload,
  );
  return data;
}

export async function verifyEmail(email: string, code: string) {
  const { data } = await client.post<{ message: string }>("/auth/verify-email", {
    email,
    code,
  });
  return data;
}

export async function resendCode(email: string) {
  const { data } = await client.post<RegisterResponse>("/auth/resend-code", {
    email,
  });
  return data;
}

export async function fetchMe() {
  const { data } = await client.get<User>("/auth/me");
  return data;
}

export async function fetchPasswordPolicy() {
  const { data } = await client.get<{ min_password_length: number }>(
    "/auth/password-policy",
  );
  return data;
}

export async function changeOwnPassword(payload: {
  current_password: string;
  new_password: string;
}) {
  const { data } = await client.post<{ ok: boolean; message: string }>(
    "/auth/change-password",
    payload,
  );
  return data;
}

export async function changeOwnUsername(payload: {
  new_username: string;
  current_password: string;
}) {
  const { data } = await client.post<{
    ok: boolean;
    message: string;
    username: string;
  }>("/auth/change-username", payload);
  return data;
}

export async function startQqOAuthLogin() {
  const { data } = await client.get<{ url: string }>("/auth/qq/oauth/start");
  return data;
}

/** QQ 回调一次性 ticket → 会话 Cookie（不经 URL 传递 access_token）。 */
export async function exchangeQqTicket(ticket: string) {
  const { data } = await client.post<SessionResponse>("/auth/qq/exchange", {
    ticket,
  });
  return data;
}

export async function logoutRequest() {
  await client.post("/auth/logout", {});
}

/** 作废本账号在所有设备上的会话（含本机），之后须重新登录。 */
export async function logoutAllRequest() {
  await client.post("/auth/logout-all", {});
}

export async function sendDeleteAccountCode() {
  const { data } = await client.post<RegisterResponse>("/auth/account/delete-code");
  return data;
}

export async function deleteOwnAccount(code: string) {
  const { data } = await client.post<{ ok: boolean; message: string }>(
    "/auth/account/delete",
    { code },
  );
  return data;
}
