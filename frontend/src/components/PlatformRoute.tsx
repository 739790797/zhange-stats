import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { fetchPlatformFeaturesEffective } from "@/api/client";
import {
  firstEnabledPlatformPath,
  isFeatureOn,
} from "@/lib/platformFeatures";

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
    staleTime: 30_000,
  });

  if (featuresQuery.isLoading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin />
      </div>
    );
  }

  if (featuresQuery.isError || !isFeatureOn(featuresQuery.data, featureId)) {
    return (
      <Navigate
        to={firstEnabledPlatformPath(
          featuresQuery.isError ? null : featuresQuery.data,
        )}
        replace
      />
    );
  }

  return <>{children}</>;
}
