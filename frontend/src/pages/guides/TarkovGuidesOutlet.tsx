import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { PageMotion } from "@/components/PageMotion";
import { RouteErrorBoundary } from "@/components/RouteErrorBoundary";
import { PlatformRoute } from "@/components/PlatformRoute";
import { RouteFallback } from "@/components/RouteFallback";
import { TarkovGuideShell } from "@/components/guides/tarkov/TarkovGuideShell";

export default function TarkovGuidesOutlet() {
  const { pathname } = useLocation();
  return (
    <PlatformRoute featureId="guides.tarkov">
      <TarkovGuideShell>
        <Suspense fallback={<RouteFallback />}>
          <RouteErrorBoundary resetKey={pathname}>
            <PageMotion motionKey={pathname}>
              <Outlet />
            </PageMotion>
          </RouteErrorBoundary>
        </Suspense>
      </TarkovGuideShell>
    </PlatformRoute>
  );
}
