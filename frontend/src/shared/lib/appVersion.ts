/** /health 与构建注入的版本号统一去掉前缀 v 和空白。 */
export function normalizeAppVersion(raw: string | null | undefined): string {
  return (raw ?? "").trim().replace(/^v/i, "").trim();
}
