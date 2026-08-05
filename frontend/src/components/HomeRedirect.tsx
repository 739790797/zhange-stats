import { useQuery } from "@tanstack/react-query";
import { Spin } from "antd";
import { Navigate } from "react-router-dom";
import { fetchPlatformFeaturesEffective } from "@/api/client";
import { firstEnabledPlatformPath } from "@/lib/platformFeatures";

export function HomeRedirect() {
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

  return (
    <Navigate
      to={firstEnabledPlatformPath(
        featuresQuery.isError ? null : featuresQuery.data,
      )}
      replace
    />
  );
}
