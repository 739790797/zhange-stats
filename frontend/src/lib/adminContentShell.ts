/** 内容区宽度：表单页窄栏，列表/控制台宽栏，阅读页仿刊物栏，酒馆大厅 / 读写文铺底。 */

import { TAVERN_ADMIN_PATH, TAVERN_PATH } from "@/lib/tavernNav";

export type AdminContentShell = "form" | "wide" | "reading" | "flush";

export function adminContentShell(
  pathname: string,
): AdminContentShell | null {
  if (pathname === "/guides/minecraft" || pathname.startsWith("/guides/minecraft/")) {
    return "wide";
  }
  if (pathname === TAVERN_ADMIN_PATH || pathname.startsWith(`${TAVERN_ADMIN_PATH}/`)) {
    return "wide";
  }
  if (
    pathname === "/" ||
    pathname === TAVERN_PATH ||
    pathname.startsWith(`${TAVERN_PATH}/`)
  ) {
    return "flush";
  }
  if (pathname === "/settings" || pathname.startsWith("/settings/")) {
    return "wide";
  }
  return null;
}
