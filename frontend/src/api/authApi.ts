import { client } from "./http";
import type { TokenResponse, User } from "./types";
import type { components } from "./generated/schema";

type RegisterResponse = components["schemas"]["RegisterResponse"];
type BindEmailResponse = components["schemas"]["BindEmailResponse"];
type LinkExistingAccountResponse =
  components["schemas"]["LinkExistingAccountResponse"];
type ResetPasswordResponse = components["schemas"]["ResetPasswordResponse"];

export async function login(username: string, password: string) {
  const { data } = await client.post<TokenResponse>("/auth/login", {
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
    access_token: string;
    token_type: string;
    username: string;
  }>("/auth/change-username", payload);
  return data;
}

export async function startQqOAuthLogin() {
  const { data } = await client.get<{ url: string }>("/auth/qq/oauth/start");
  return data;
}

/** QQ 回调一次性 ticket → JWT（不经 URL 传递 access_token）。 */
export async function exchangeQqTicket(ticket: string) {
  const { data } = await client.post<TokenResponse>("/auth/qq/exchange", {
    ticket,
  });
  return data;
}
