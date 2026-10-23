/** 盒子 / 资料卡同步时间展示（本地墙钟）。无效 ISO 原样返回。 */
export function formatSyncedAt(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}
