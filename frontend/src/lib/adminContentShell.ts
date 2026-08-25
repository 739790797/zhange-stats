/** 内容区宽度：表单页窄栏，列表/控制台宽栏，均在灰底上水平居中。 */

export type AdminContentShell = "form" | "wide";

/** 系统管理（安全 / 集成 / 邮箱 / 更新）：约 960px，贴近常见 SaaS 设置栏。 */
const FORM_PATHS = new Set([
  "/settings/auth",
  "/settings/integrations",
  "/settings/email",
  "/settings/system",
]);

export function adminContentShell(
  pathname: string,
): AdminContentShell | null {
  if (pathname === "/guides/minecraft" || pathname.startsWith("/guides/minecraft/")) {
    return "wide";
  }
  if (pathname !== "/settings" && !pathname.startsWith("/settings/")) {
    return null;
  }
  return FORM_PATHS.has(pathname) ? "form" : "wide";
}
