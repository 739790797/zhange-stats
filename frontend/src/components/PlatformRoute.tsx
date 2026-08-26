import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import type { ReactNode } from "react";
import { fetchPlatformFeaturesEffective } from "@/api/client";
import { FeatureUnavailablePage } from "@/components/FeatureUnavailablePage";
import { isFeatureOn } from "@/lib/platformFeatures";
import { LOCAL_QUERY_STALE_MS, isInitialQueryPending } from "@/lib/queryCache";

export function PlatformRoute({
  featureId,
  children,
}: {
  featureId: string;
  children: ReactNode;
}) {
  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
  });

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
