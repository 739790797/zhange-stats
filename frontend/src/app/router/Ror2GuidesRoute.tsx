import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { PlatformRoute } from "@/app/router/PlatformRoute";
import { RouteErrorBoundary } from "@/app/router/RouteErrorBoundary";
import { RouteFallback } from "@/app/router/RouteFallback";
import { PageMotion } from "@/shared/ui/PageMotion";
import Ror2GuidesOutlet from "@/features/guides/ror2/pages/Ror2GuidesOutlet";

/** ROR2 图鉴路由沿用公开 feature 门禁、页面壳和逐页错误边界。 */
export default function Ror2GuidesRoute() {
  const { pathname } = useLocation();
  return (
    <PlatformRoute featureId="guides.ror2" allowGuest>
      <Ror2GuidesOutlet>
        <Suspense fallback={<RouteFallback />}>
          <RouteErrorBoundary resetKey={pathname}>
            <PageMotion motionKey={pathname}>
              <Outlet />
            </PageMotion>
          </RouteErrorBoundary>
        </Suspense>
      </Ror2GuidesOutlet>
    </PlatformRoute>
  );
}
