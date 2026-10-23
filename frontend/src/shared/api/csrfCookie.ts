export const CSRF_COOKIE = "zhange_csrf";

export function readCookie(name: string, cookieSource = ""): string {
  const raw =
    cookieSource ||
    (typeof document !== "undefined" ? document.cookie : "");
  const parts = raw.split(";");
  for (const part of parts) {
    const [k, ...rest] = part.trim().split("=");
    if (k === name) {
      try {
        return decodeURIComponent(rest.join("="));
      } catch {
        return rest.join("=");
      }
    }
  }
  return "";
}

export function readCsrfToken(cookieSource = ""): string {
  return readCookie(CSRF_COOKIE, cookieSource);
}

export function isUnsafeHttpMethod(method: string | undefined): boolean {
  const m = (method || "get").toUpperCase();
  return m !== "GET" && m !== "HEAD" && m !== "OPTIONS" && m !== "TRACE";
}
