import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import type { ReactNode } from "react";
import { fetchPlatformFeaturesEffective } from "@/api/client";
import { FeatureUnavailablePage } from "@/components/FeatureUnavailablePage";
import { isFeatureOn } from "@/lib/platformFeatures";
import { LOCAL_QUERY_STALE_MS, isInitialQueryPending } from "@/lib/queryCache";
import { useAuthStore } from "@/stores/authStore";

export function PlatformRoute({
  featureId,
  children,
  allowGuest = false,
}: {
  featureId: string;
  children: ReactNode;
  allowGuest?: boolean;
}) {
  const token = useAuthStore((s) => s.token);
  const skipGate = allowGuest && !token;
  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
    enabled: !skipGate,
  });

  if (skipGate) return <>{children}</>;

  if (isInitialQueryPending(featuresQuery)) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin />
      </div>
    );
  }

  if (featuresQuery.isError || !isFeatureOn(featuresQuery.data, featureId)) {
    return (
      <FeatureUnavailablePage
        featureId={featureId}
        loadError={featuresQuery.isError}
      />
    );
  }

  return <>{children}</>;
}
