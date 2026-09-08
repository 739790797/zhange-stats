/** 401 是否整站登出。纯函数，便于单测。 */

export type LogoutOn401Input = {
  status: number;
  url: string;
  hasSession: boolean;
};

export function isAuthLoginUrl(url: string): boolean {
  return url.includes("/auth/login");
}

export function isAuthMeUrl(url: string): boolean {
  const path = url.split("?")[0] || "";
  return /\/auth\/me\/?$/.test(path) || path.endsWith("/auth/me");
}

export function shouldLogoutOn401(input: LogoutOn401Input): boolean {
  if (input.status === 403) return false;
  if (input.status !== 401) return false;
  if (isAuthLoginUrl(input.url)) return false;
  if (isAuthMeUrl(input.url)) return true;
  return input.hasSession;
}

let logoutInflight = false;

export function takeLogoutOnce(): boolean {
  if (logoutInflight) return false;
  logoutInflight = true;
  return true;
}

export function resetLogoutOnce(): void {
  logoutInflight = false;
}
