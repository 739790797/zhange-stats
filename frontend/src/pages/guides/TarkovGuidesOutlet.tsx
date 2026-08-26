import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { PlatformRoute } from "@/components/PlatformRoute";
import { RouteFallback } from "@/components/RouteFallback";
import { TarkovGuideShell } from "@/components/guides/tarkov/TarkovGuideShell";

export default function TarkovGuidesOutlet() {
  return (
    <PlatformRoute featureId="guides.tarkov">
      <TarkovGuideShell>
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </TarkovGuideShell>
    </PlatformRoute>
  );
}
