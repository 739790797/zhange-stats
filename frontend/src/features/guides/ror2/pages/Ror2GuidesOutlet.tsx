import type { ReactNode } from "react";
import { Ror2GuideShell } from "@/features/guides/ror2/components/Ror2GuideShell";

/** ROR2 页面壳；权限、懒加载与路由错误边界由 app/router 装配。 */
export default function Ror2GuidesOutlet({ children }: { children: ReactNode }) {
  return <Ror2GuideShell>{children}</Ror2GuideShell>;
}
