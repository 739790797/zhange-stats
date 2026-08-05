import { client } from "./http";
import type { User } from "./types";

export async function login(username: string, password: string) {
  const { data } = await client.post<{ access_token: string; token_type: string }>(
    "/auth/login",
    { username, password },
  );
  return data;
}

export async function register(payload: {
  email: string;
  password: string;
  code: string;
}) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery?: string;
    access_token?: string;
    token_type?: string;
  }>("/auth/register", payload);
  return data;
}

export async function sendRegisterCode(email: string) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery?: string;
  }>("/auth/send-register-code", { email });
  return data;
}

export async function sendBindEmailCode(email: string) {
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery?: string;
  }>("/auth/send-bind-email-code", { email });
  return data;
}

export async function bindEmail(payload: {
  email: string;
  code: string;
  password?: string;
}) {
  const { data } = await client.post<{
    message: string;
    user: User;
  }>("/auth/bind-email", payload);
  return data;
}

export async function linkExistingAccount(payload: {
  email: string;
  password: string;
}) {
  const { data } = await client.post<{
    message: string;
    access_token: string;
    token_type: string;
    user: User;
  }>("/auth/link-existing-account", payload);
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
  const { data } = await client.post<{
    message: string;
    email: string;
    delivery: string;
  }>("/auth/resend-code", { email });
  return data;
}

export async function fetchMe() {
  const { data } = await client.get<User>("/auth/me");
  return data;
}

export async function startQqOAuthLogin() {
  const { data } = await client.get<{ url: string }>("/auth/qq/oauth/start");
  return data;
}
