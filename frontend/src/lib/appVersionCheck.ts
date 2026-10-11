/** /health 与构建注入的版本号统一去掉前缀 v 和空白。 */
export function normalizeAppVersion(raw: string | null | undefined): string {
  return (raw ?? "").trim().replace(/^v/i, "").trim();
}

/**
 * 本页的包和服务端版本对不上（升级或回滚都算），该刷新换包。
 * 任一边没有版本号，或是没读到 VERSION 的 dev 构建，就不比。
 */
export function appBundleOutdated(
  bundleVersion: string,
  serverVersion: string | null | undefined,
): boolean {
  const bundle = normalizeAppVersion(bundleVersion);
  const server = normalizeAppVersion(serverVersion);
  if (!bundle || !server || bundle === "dev") return false;
  return bundle !== server;
}
