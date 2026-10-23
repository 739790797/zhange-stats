/** 拼进 innerHTML 的字符串（Leaflet tooltip / popup / divIcon、G2 tooltip 标题）先转义。 */
export function escapeHtml(text: string | null | undefined): string {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
