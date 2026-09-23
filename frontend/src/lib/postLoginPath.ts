/** 登录后回跳：只允许站内路径，避免协议相对 / 反斜杠开重定向。 */

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

function splitInAppPath(raw: string): LoginFromLocation {
  let rest = raw.trim();
  if (!rest) return { pathname: "/" };
  let hash = "";
  const hashIdx = rest.indexOf("#");
  if (hashIdx >= 0) {
    hash = rest.slice(hashIdx);
    rest = rest.slice(0, hashIdx);
  }
  let search = "";
  const qIdx = rest.indexOf("?");
  if (qIdx >= 0) {
    search = rest.slice(qIdx);
    rest = rest.slice(0, qIdx);
  }
  return { pathname: rest, search, hash };
}

function isSafeInAppPathname(pathname: string): boolean {
  if (!pathname.startsWith("/")) return false;
  if (pathname.startsWith("//")) return false;
  if (pathname.includes("\\") || pathname.includes("://")) return false;
  return true;
}

export function postLoginPath(from?: LoginFromLocation): string {
  const parts = splitInAppPath(
    `${from?.pathname || ""}${from?.search || ""}${from?.hash || ""}`,
  );
  const pathname = (parts?.pathname || "").trim();
  if (!pathname || pathname === "/") return "/";
  if (!isSafeInAppPathname(pathname)) return "/";
  if (AUTH_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return "/";
  }
  return `${pathname}${parts?.search || ""}${parts?.hash || ""}`;
}

export function rememberPostLoginPath(path: string): void {
  if (typeof sessionStorage === "undefined") return;
  const next = postLoginPath({ pathname: path });
  if (next === "/") {
    sessionStorage.removeItem(STORAGE_KEY);
    return;
  }
  sessionStorage.setItem(STORAGE_KEY, next);
}

export function consumePostLoginPath(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
  const path = postLoginPath({ pathname: raw || "" });
  return path !== "/" ? path : null;
}
