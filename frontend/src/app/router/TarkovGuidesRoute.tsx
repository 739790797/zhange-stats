import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { PlatformRoute } from "@/app/router/PlatformRoute";
import { RouteErrorBoundary } from "@/app/router/RouteErrorBoundary";
import { RouteFallback } from "@/app/router/RouteFallback";
import { PageMotion } from "@/shared/ui/PageMotion";
import TarkovGuidesOutlet from "@/features/guides/tarkov/pages/TarkovGuidesOutlet";

/** app/router 保留攻略路由权限、加载与错误边界，并注入 feature 页面壳。 */
export default function TarkovGuidesRoute() {
  const { pathname } = useLocation();
  return (
    <PlatformRoute featureId="guides.tarkov" allowGuest>
      <TarkovGuidesOutlet>
        <Suspense fallback={<RouteFallback />}>
          <RouteErrorBoundary resetKey={pathname}>
            <PageMotion motionKey={pathname}>
              <Outlet />
            </PageMotion>
          </RouteErrorBoundary>
        </Suspense>
      </TarkovGuidesOutlet>
    </PlatformRoute>
  );
}
