/** 价格文案：轻模块，钥匙包等外壳常驻代码用，不拖 tarkovItemFormat 与格子 JSON。 */

export function formatMoney(
  value: number | null | undefined,
  currency = "RUB",
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const code = (currency || "RUB").toUpperCase();
  const symbol = code === "USD" ? "$" : code === "EUR" ? "€" : "₽";
  return `${Math.round(value).toLocaleString("zh-CN")} ${symbol}`;
}
