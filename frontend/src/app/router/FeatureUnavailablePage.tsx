import { GUIDE_NAV, flattenGuideLeaves } from "@/features/guides/shared/model/guideNav";
import { PLATFORM_NAV } from "@/features/platforms/shared/model/platformFeatures";
import { FeatureUnavailableResult } from "@/shared/ui/FeatureUnavailableResult";

function featureLabel(featureId: string): string {
  const platform = PLATFORM_NAV.find((item) => item.featureId === featureId);
  if (platform) return platform.label;
  if (featureId === "tavern") return "战鸽酒馆";
  const guide = flattenGuideLeaves(GUIDE_NAV).find(
    (item) => item.featureId === featureId,
  );
  return guide?.label || "该功能";
}

export function FeatureUnavailablePage({
  featureId,
  loadError = false,
}: {
  featureId: string;
  loadError?: boolean;
}) {
  return (
    <FeatureUnavailableResult
      featureName={featureLabel(featureId)}
      loadError={loadError}
    />
  );
}
