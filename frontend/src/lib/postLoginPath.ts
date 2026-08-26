/** 登录后回跳：避免回到认证页或空路径。 */

const AUTH_PREFIXES = [
  "/login",
  "/register",
  "/forgot-password",
  "/verify-email",
  "/setup",
];

const STORAGE_KEY = "zhange.postLoginPath";

export type LoginFromLocation = {
  pathname?: string;
  search?: string;
  hash?: string;
} | null;

export function postLoginPath(from?: LoginFromLocation): string {
  const pathname = (from?.pathname || "").trim();
  if (!pathname || pathname === "/") return "/";
  if (AUTH_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return "/";
  }
  return `${pathname}${from?.search || ""}${from?.hash || ""}`;
}

export function rememberPostLoginPath(path: string): void {
  if (typeof sessionStorage === "undefined") return;
  const next = (path || "").trim();
  if (!next || next === "/") {
    sessionStorage.removeItem(STORAGE_KEY);
    return;
  }
  sessionStorage.setItem(STORAGE_KEY, next);
}

export function consumePostLoginPath(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
  const path = (raw || "").trim();
  return path && path !== "/" ? path : null;
}
