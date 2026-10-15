import { Suspense } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { PageMotion } from "@/components/PageMotion";
import { PlatformRoute } from "@/components/PlatformRoute";
import { RouteErrorBoundary } from "@/components/RouteErrorBoundary";
import { RouteFallback } from "@/components/RouteFallback";
import { Ror2GuideShell } from "@/components/guides/ror2/Ror2GuideShell";

export default function Ror2GuidesOutlet() {
  const { pathname } = useLocation();
  return (
    <PlatformRoute featureId="guides.ror2" allowGuest>
      <Ror2GuideShell>
        <Suspense fallback={<RouteFallback />}>
          <RouteErrorBoundary resetKey={pathname}>
            <PageMotion motionKey={pathname}>
              <Outlet />
            </PageMotion>
          </RouteErrorBoundary>
        </Suspense>
      </Ror2GuideShell>
    </PlatformRoute>
  );
}
