import type { ReactNode } from "react";
import { TarkovGuideShell } from "@/features/guides/tarkov/components/TarkovGuideShell";

/** Tarkov 页面壳；权限、懒加载与路由错误边界由 app/router 装配。 */
export default function TarkovGuidesOutlet({ children }: { children: ReactNode }) {
  return <TarkovGuideShell>{children}</TarkovGuideShell>;
}
